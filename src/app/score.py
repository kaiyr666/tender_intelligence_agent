"""Code step: gate and score every lot of an extracted notice against the profile.

Each criterion gives 0-1 with a reason; the lot score is their weighted mean.
A notice is shown by its best eligible lot. The gates are value under the
minimum, a region outside the profile's (D25), an excluded main service and a
missing mandatory accreditation. The last two rely on the LLM and only reject
when their supporting quote is found in the notice; otherwise the notice goes
to "needs review", because a wrong hard reject is a missed tender (D8). The
region gate has no quote check when the region comes from the notice text: the
client chose to reject those too (D25).
"""

import re
from dataclasses import dataclass
from datetime import datetime

from app.extract import WHOLE_NOTICE, Extraction, LotExtraction, Requirement, notice_text
from app.notices import Lot, Notice
from app.profile import Profile

SHORTLISTED = "shortlisted"
REJECTED = "rejected"
NEEDS_REVIEW = "needs review"
NOT_PROCESSED = "not processed"

ELIGIBLE = "eligible"
GATED = "gated"
REVIEW = "review"

UNKNOWN_SCORE = 0.5  # a fact the notice does not state neither helps nor hurts
OVER_MAX_VALUE_SCORE = 0.3  # biddable with a partner, so a penalty rather than a gate
MINOR_EXCLUDED_PENALTY = 0.25  # e.g. office cleaning that also covers a clinic
MIN_QUOTE_CHARS = 10  # shorter "quotes" (e.g. "ISO") would match almost any notice


@dataclass(frozen=True)
class Criterion:
    name: str
    score: float
    reason: str


@dataclass(frozen=True)
class LotResult:
    lot_id: str
    lot_name: str
    status: str  # ELIGIBLE, GATED or REVIEW
    reasons: list[str]  # why it was gated or sent to review; empty when eligible
    criteria: list[Criterion]
    score: float


@dataclass(frozen=True)
class NoticeResult:
    notice: Notice
    outcome: str  # SHORTLISTED, REJECTED, NEEDS_REVIEW or NOT_PROCESSED
    reason: str
    best_lot: LotResult | None
    lots: list[LotResult]
    extraction: Extraction | None


def without_extraction(notice: Notice, outcome: str, reason: str) -> NoticeResult:
    """A notice that could not be scored: extraction failed, or the run stopped first."""
    return NoticeResult(notice, outcome, reason, None, [], None)


def score_notice(
    notice: Notice, extraction: Extraction, profile: Profile, now: datetime
) -> NoticeResult:
    """Gate and score each extracted lot, then decide the notice's outcome from its best lot."""
    text = notice_text(notice)
    lots_by_id = {lot.lot_id: lot for lot in notice.lots}
    expected_ids = set(lots_by_id) or {WHOLE_NOTICE}
    results = [
        score_lot(notice, lots_by_id.get(lot_x.lot_id), lot_x, extraction, profile, now, text)
        for lot_x in extraction.lots
        if lot_x.lot_id in expected_ids
    ]
    if not results:
        reason = "the extraction did not cover any of the notice's lots"
        return NoticeResult(notice, NEEDS_REVIEW, reason, None, [], extraction)
    return _decide(notice, results, extraction, profile.scoring.shortlist_threshold)


def score_lot(
    notice: Notice,
    lot: Lot | None,
    lot_x: LotExtraction,
    extraction: Extraction,
    profile: Profile,
    now: datetime,
    text: str,
) -> LotResult:
    """All gates and criteria for one lot. `lot` is None for a notice without lots."""
    value = _lot_value(notice, lot)
    required = extraction.notice_mandatory_accreditations + lot_x.mandatory_accreditations
    preferred = extraction.notice_preferred_accreditations + lot_x.preferred_accreditations

    gates, reviews = [], []
    if value is not None and value < profile.value.min_gbp:
        gates.append(f"value £{value:,.0f} is under £{profile.value.min_gbp:,.0f}")
    region = _region_fit(notice, lot, lot_x, profile)
    # Only work in the profile's region is bid for; out of region, UK-wide and not stated
    # all score below 1 and are rejected (D25).
    if region.score < 1.0:
        gates.append(f"not in the company's region: {region.reason}")
    _check_excluded_service(lot_x, profile, text, gates, reviews)
    _check_accreditations(required, profile, text, gates, reviews)

    criteria = [
        _service_fit(lot_x, profile),
        region,
        _value_fit(value, profile),
        _accreditation_fit(preferred, profile),
        _mobilisation_fit(lot_x.mobilisation_weeks, profile),
        _deadline_fit(notice.deadline, now, profile),
    ]
    weights = profile.scoring.weights.model_dump()
    total = sum(weights[c.name] * c.score for c in criteria) / sum(weights.values())

    status = GATED if gates else REVIEW if reviews else ELIGIBLE
    return LotResult(
        lot_id=lot_x.lot_id,
        lot_name=_lot_name(lot, lot_x.lot_id),
        status=status,
        reasons=gates or reviews,
        criteria=criteria,
        score=round(total, 3),
    )


def quote_found(quote: str | None, text: str) -> bool:
    """True if the quote appears in the text, ignoring case, spacing and quote/dash styles."""
    if not quote:
        return False
    needle = _normalise_text(quote).strip(" \"'.")
    return len(needle) >= MIN_QUOTE_CHARS and needle in _normalise_text(text)


def holds(requirement: str, profile: Profile) -> bool:
    """True if the company holds the required accreditation, e.g. 'ISO 9001:2015' -> ISO 9001."""
    wanted = _compact(requirement)
    return any(_compact(held) in wanted for held in profile.accreditations.held)


def _decide(
    notice: Notice, results: list[LotResult], extraction: Extraction, threshold: float
) -> NoticeResult:
    eligible = [r for r in results if r.status == ELIGIBLE]
    best = max(eligible, key=lambda r: r.score, default=None)
    if best and best.score >= threshold:
        reason = f"{best.lot_name} scores {best.score:.2f} (threshold {threshold:.2f})"
        return NoticeResult(notice, SHORTLISTED, reason, best, results, extraction)
    reviews = [reason for r in results if r.status == REVIEW for reason in r.reasons]
    if reviews:
        reason = "; ".join(dict.fromkeys(reviews))
        return NoticeResult(notice, NEEDS_REVIEW, reason, best, results, extraction)
    if best:
        reason = f"best lot scores {best.score:.2f}, below the threshold {threshold:.2f}"
        return NoticeResult(notice, REJECTED, reason, best, results, extraction)
    gates = [reason for r in results for reason in r.reasons]
    return NoticeResult(
        notice, REJECTED, "; ".join(dict.fromkeys(gates)), None, results, extraction
    )


def _check_excluded_service(
    lot_x: LotExtraction, profile: Profile, text: str, gates: list[str], reviews: list[str]
) -> None:
    if _label(lot_x.primary_service) not in _labels(profile.services.excluded_names):
        return
    if quote_found(lot_x.primary_service_quote, text):
        gates.append(f"main service is {lot_x.primary_service}, which the company does not do")
    else:
        reviews.append(
            f"main service may be {lot_x.primary_service}, but the supporting quote "
            "was not found in the notice"
        )


def _check_accreditations(
    required: list[Requirement], profile: Profile, text: str, gates: list[str], reviews: list[str]
) -> None:
    for requirement in required:
        if holds(requirement.name, profile):
            continue
        if quote_found(requirement.quote, text):
            gates.append(f"requires {requirement.name}, which the company does not hold")
        else:
            reviews.append(
                f"may require {requirement.name}, but the supporting quote "
                "was not found in the notice"
            )


def _service_fit(lot_x: LotExtraction, profile: Profile) -> Criterion:
    primary = _label(lot_x.primary_service)
    offered = _labels(profile.services.offered_names)
    excluded = _labels(profile.services.excluded_names)
    if primary is None:
        score, reason = UNKNOWN_SCORE, "main service not stated"
    elif primary in offered:
        score, reason = 1.0, f"main service is {lot_x.primary_service}"
    elif primary in excluded:
        score, reason = 0.0, f"main service is {lot_x.primary_service} (excluded)"
    else:
        score, reason = 0.0, f"main service ({lot_x.primary_service}) is not one the company offers"
    minor = [s for s in lot_x.services if _label(s) in excluded and _label(s) != primary]
    if minor:
        score = max(0.0, score - MINOR_EXCLUDED_PENALTY)
        reason += f"; also includes {', '.join(minor)}"
    return Criterion("service", score, reason)


def _region_fit(
    notice: Notice, lot: Lot | None, lot_x: LotExtraction, profile: Profile
) -> Criterion:
    regions, source = lot_regions(notice, lot, lot_x)
    if not regions:
        return Criterion("region", UNKNOWN_SCORE, "delivery region not stated")
    listed = ", ".join(regions)
    north = tuple(profile.region.nuts_codes)
    outside = [r for r in regions if not r.startswith(north)]
    if not outside:
        return Criterion("region", 1.0, f"in region ({listed}, from {source})")
    if regions == ["UK"]:
        return Criterion("region", 0.0, f"UK-wide contract, no regional lot (from {source})")
    if len(outside) < len(regions):
        # Buyers list every English region for national lots; the client rejects any lot
        # that also covers work outside the North (D25, clarified 22 Nov).
        return Criterion(
            "region", 0.0, f"also covers regions outside the North ({listed}, from {source})"
        )
    return Criterion("region", 0.0, f"out of region ({listed}, from {source})")


def lot_regions(notice: Notice, lot: Lot | None, lot_x: LotExtraction) -> tuple[list[str], str]:
    """Where the lot is delivered and where that came from: delivery-address NUTS codes
    when the notice has them, the LLM's reading of the text otherwise."""
    if lot and lot.regions:
        return lot.regions, "delivery address"
    if len(notice.lots) <= 1 and notice.regions:
        return notice.regions, "delivery address"
    return [r.strip().upper() for r in lot_x.region_nuts1], "notice text"


def _value_fit(value: float | None, profile: Profile) -> Criterion:
    if value is None:
        return Criterion("value", UNKNOWN_SCORE, "value not stated")
    if value < profile.value.min_gbp:
        return Criterion("value", 0.0, f"£{value:,.0f} is under the minimum")
    if value > profile.value.max_gbp:
        return Criterion(
            "value", OVER_MAX_VALUE_SCORE, f"£{value:,.0f} is over £{profile.value.max_gbp:,.0f}"
        )
    return Criterion("value", 1.0, f"£{value:,.0f} is in the value band")


def _accreditation_fit(preferred: list[str], profile: Profile) -> Criterion:
    """Mandatory accreditations are gates; this scores the preferred ones."""
    if not preferred:
        return Criterion("accreditations", 1.0, "no preferred accreditations listed")
    missing = [name for name in preferred if not holds(name, profile)]
    score = 1 - len(missing) / len(preferred)
    if not missing:
        return Criterion("accreditations", score, "holds every preferred accreditation")
    return Criterion("accreditations", score, f"lacks preferred {', '.join(missing)}")


def _mobilisation_fit(weeks: float | None, profile: Profile) -> Criterion:
    needed = profile.mobilisation.min_weeks
    if weeks is None:
        return Criterion("mobilisation", UNKNOWN_SCORE, "mobilisation time not stated")
    score = min(1.0, max(0.0, weeks / needed))
    return Criterion("mobilisation", score, f"{weeks:g} weeks to mobilise (needs {needed})")


def _deadline_fit(deadline: datetime | None, now: datetime, profile: Profile) -> Criterion:
    needed = profile.deadline.min_days
    if deadline is None:
        return Criterion("deadline", UNKNOWN_SCORE, "deadline not stated")
    days = (deadline - now).total_seconds() / 86_400
    score = min(1.0, max(0.0, days / needed))
    return Criterion("deadline", score, f"{max(days, 0):.0f} days to respond (needs {needed})")


def _lot_value(notice: Notice, lot: Lot | None) -> float | None:
    """The lot's own value; the notice value only when the notice is a single lot."""
    if lot and lot.value_gbp is not None:
        return lot.value_gbp
    return notice.value_gbp if len(notice.lots) <= 1 else None


def _lot_name(lot: Lot | None, lot_id: str) -> str:
    if lot is None:
        return "whole notice"
    return f"Lot {lot.lot_id}: {lot.title}" if lot.title else f"Lot {lot.lot_id}"


def _label(service: str | None) -> str | None:
    return service.strip().casefold() if service else None


def _labels(services: list[str]) -> set[str]:
    return {s.strip().casefold() for s in services}


def _compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _normalise_text(text: str) -> str:
    text = text.casefold()
    for fancy, plain in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}.items():
        text = text.replace(fancy, plain)
    return " ".join(text.split())
