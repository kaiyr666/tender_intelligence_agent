"""Turn raw OCDS releases into one reduced, contact-free Notice per tender.

Only the fields the screening needs are kept: parties are cut to the buyer's
organisation name, and emails and phone numbers in free text are masked.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from pydantic import BaseModel, field_validator

from app.sanitise import mask_contacts


def _zero_is_not_stated(value: float | None) -> float | None:
    """Buyers enter £0 as a placeholder, so it means "not stated", not a value under £100k."""
    return None if value == 0 else value


NOTICE_URL = "https://www.find-tender.service.gov.uk/Notice/{notice_id}"

TENDER_TAGS = {"tender", "tenderUpdate"}
PLANNING_TAGS = {"planning", "planningUpdate"}
CANCELLATION_TAGS = {"tenderCancellation"}
WITHDRAWN_STATUSES = {"cancelled", "withdrawn"}


class Lot(BaseModel):
    lot_id: str
    title: str | None
    description: str | None
    value_gbp: float | None
    contract_start: date | None
    contract_end: date | None
    cpv_codes: list[str]
    regions: list[str]
    selection_criteria: str | None

    _value = field_validator("value_gbp")(_zero_is_not_stated)


class Notice(BaseModel):
    ocid: str
    notice_id: str
    published: datetime
    title: str
    description: str | None
    buyer: str | None
    status: str | None
    main_category: str | None
    value_gbp: float | None
    deadline: datetime | None
    url: str
    cpv_codes: list[str]
    regions: list[str]
    lots: list[Lot]

    _value = field_validator("value_gbp")(_zero_is_not_stated)


@dataclass(frozen=True)
class NoticeBatch:
    tenders: list[Notice]
    planning_count: int
    withdrawn_count: int


def build_notices(releases: list[dict]) -> NoticeBatch:
    """Group releases by ocid, keep the latest, and sort them into tender / planning / withdrawn.

    Releases that are not tender, planning or cancellation releases (awards,
    contracts) are ignored.
    """
    relevant_tags = TENDER_TAGS | PLANNING_TAGS | CANCELLATION_TAGS
    latest: dict[str, dict] = {}
    for release in releases:
        if not set(release.get("tag") or []) & relevant_tags:
            continue
        current = latest.get(release["ocid"])
        if current is None or parse_datetime(release["date"]) > parse_datetime(current["date"]):
            latest[release["ocid"]] = release

    tenders, planning_count, withdrawn_count = [], 0, 0
    for release in latest.values():
        tags = set(release.get("tag") or [])
        status = (release.get("tender") or {}).get("status")
        if tags & CANCELLATION_TAGS or status in WITHDRAWN_STATUSES:
            withdrawn_count += 1
        elif tags & TENDER_TAGS:
            tenders.append(to_notice(release))
        else:
            planning_count += 1
    return NoticeBatch(tenders, planning_count, withdrawn_count)


def to_notice(release: dict) -> Notice:
    """Reduce one tender-stage release to a Notice."""
    tender = release.get("tender") or {}
    items = tender.get("items") or []
    lots = [_to_lot(lot, items) for lot in tender.get("lots") or []]
    notice_cpv = _cpv_codes(items)
    classification = tender.get("classification") or {}
    if classification.get("scheme") == "CPV" and classification.get("id"):
        notice_cpv = sorted(set(notice_cpv) | {classification["id"]})
    # Some procedures have no tender period yet; the expression-of-interest deadline is then
    # the first date the bid team must meet.
    deadline = (tender.get("tenderPeriod") or {}).get("endDate") or tender.get(
        "expressionOfInterestDeadline"
    )
    return Notice(
        ocid=release["ocid"],
        notice_id=release["id"],
        published=parse_datetime(release["date"]),
        title=mask_contacts(tender.get("title")) or "(untitled)",
        description=mask_contacts(tender.get("description")),
        buyer=(release.get("buyer") or {}).get("name"),
        status=tender.get("status"),
        main_category=tender.get("mainProcurementCategory"),
        value_gbp=_notice_value(tender, lots),
        deadline=parse_datetime(deadline) if deadline else None,
        url=_notice_url(release),
        cpv_codes=notice_cpv,
        regions=_regions(items),
        lots=lots,
    )


def parse_datetime(text: str) -> datetime:
    """Parse an OCDS timestamp. A date alone means the end of that day; no zone means UTC."""
    if len(text) == 10:
        return datetime.combine(date.fromisoformat(text), time(23, 59, 59), tzinfo=UTC)
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _to_lot(lot: dict, items: list[dict]) -> Lot:
    lot_items = [item for item in items if item.get("relatedLot") == lot.get("id")]
    period = lot.get("contractPeriod") or {}
    criteria = (lot.get("selectionCriteria") or {}).get("criteria") or []
    criteria_text = "\n".join(c["description"] for c in criteria if c.get("description"))
    return Lot(
        lot_id=str(lot.get("id")),
        title=mask_contacts(lot.get("title")),
        description=mask_contacts(lot.get("description")),
        value_gbp=_amount(lot.get("value")),
        contract_start=_date(period.get("startDate")),
        contract_end=_date(period.get("endDate")),
        cpv_codes=_cpv_codes(lot_items),
        regions=_regions(lot_items),
        selection_criteria=mask_contacts(criteria_text) or None,
    )


def _cpv_codes(items: list[dict]) -> list[str]:
    codes = {
        c["id"]
        for item in items
        for c in item.get("additionalClassifications") or []
        if c.get("scheme") == "CPV" and c.get("id")
    }
    return sorted(codes)


def _regions(items: list[dict]) -> list[str]:
    regions = {
        address["region"]
        for item in items
        for address in item.get("deliveryAddresses") or []
        if address.get("region")
    }
    return sorted(regions)


def _amount(value: dict | None) -> float | None:
    """Value in GBP excluding VAT, falling back to the gross amount. Other currencies: unknown."""
    if not value or value.get("currency") not in (None, "GBP"):
        return None
    amount = value.get("amount", value.get("amountGross"))
    return float(amount) if amount is not None else None


def _notice_value(tender: dict, lots: list[Lot]) -> float | None:
    """The notice's stated value, or the sum of its lots when every lot states one."""
    stated = _amount(tender.get("value"))
    if stated is not None:
        return stated
    if lots and all(lot.value_gbp is not None for lot in lots):
        return sum(lot.value_gbp for lot in lots)
    return None


def _notice_url(release: dict) -> str:
    for document in (release.get("tender") or {}).get("documents") or []:
        if document.get("documentType") == "tenderNotice" and document.get("url"):
            return document["url"]
    for link in release.get("links") or []:
        if link.get("rel") == "canonical" and link.get("href"):
            return link["href"]
    return NOTICE_URL.format(notice_id=release["id"])


def _date(text: str | None) -> date | None:
    return parse_datetime(text).date() if text else None
