"""LLM step: read a notice's free text into a validated, per-lot Extraction.

The model only reads; every decision (gates, scores, the shortlist) is made
in code from the Extraction (see score.py).
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm import Provider, Usage, complete_json, load_prompt
from app.notices import Notice
from app.profile import Profile

PROMPT_NAME = "extract"
# Lot id the model uses for a notice that has no lots.
WHOLE_NOTICE = "whole"
# About 8k tokens: long enough for real notices, short enough to bound the cost of one call.
MAX_INPUT_CHARS = 24_000
NOTICE_TAG = re.compile(r"</?\s*notice\s*>", re.IGNORECASE)


class Requirement(BaseModel):
    name: str = Field(description="The accreditation or certification, e.g. 'ISO 9001'.")
    quote: str = Field(description="The exact words from the notice that make it mandatory.")


class RedFlag(BaseModel):
    kind: Literal["tupe", "short_deadline", "closed_framework_call_off"]
    quote: str = Field(description="The exact words from the notice that raise this flag.")


class LotExtraction(BaseModel):
    lot_id: str
    services: list[str] = Field(description="Profile service labels this lot covers.")
    primary_service: str | None = Field(
        description="The lot's main service: a profile label, 'other: <what>', or null if unclear."
    )
    primary_service_quote: str | None = Field(
        description="Exact words from the notice that show the primary service."
    )
    region_nuts1: list[str] = Field(
        description="NUTS 1 codes where the work is delivered, also from named places; "
        "'UK' for UK-wide, [] if no place is named."
    )
    contract_length_months: int | None
    mobilisation_weeks: float | None
    mandatory_accreditations: list[Requirement]
    preferred_accreditations: list[str]


class Extraction(BaseModel):
    """What the notice says, per lot. Notice-wide requirements apply to every lot."""

    notice_mandatory_accreditations: list[Requirement]
    notice_preferred_accreditations: list[str]
    red_flags: list[RedFlag]
    lots: list[LotExtraction] = Field(min_length=1)


def notice_text(notice: Notice) -> str:
    """The notice's own words, as the model sees them and as quotes are checked against."""
    parts = [f"Title: {notice.title}"]
    if notice.buyer:
        parts.append(f"Buyer: {notice.buyer}")
    if notice.deadline:
        parts.append(f"Tender deadline: {notice.deadline.date().isoformat()}")
    if notice.description:
        parts.append(f"Description:\n{notice.description}")
    for lot in notice.lots:
        lines = [f"Lot {lot.lot_id}: {lot.title or '(no title)'}"]
        if lot.contract_start or lot.contract_end:
            lines.append(f"Contract period: {lot.contract_start} to {lot.contract_end}")
        if lot.description:
            lines.append(lot.description)
        if lot.selection_criteria:
            lines.append(f"Selection criteria:\n{lot.selection_criteria}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def prompt_variables(notice: Notice, profile: Profile) -> dict[str, str]:
    """Everything the extract prompt is filled with. Notice text is capped and cannot close
    its own <notice> delimiter."""
    text = NOTICE_TAG.sub("", notice_text(notice))
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n[notice text cut here]"
    lot_ids = [lot.lot_id for lot in notice.lots] or [WHOLE_NOTICE]
    return {
        "offered_services": "\n".join(f"- {s}" for s in profile.services.offered),
        "excluded_services": "\n".join(f"- {s}" for s in profile.services.excluded),
        "held_accreditations": ", ".join(profile.accreditations.held),
        "lot_ids": ", ".join(lot_ids),
        "notice": text,
    }


def extract_notice(
    notice: Notice, profile: Profile, provider: Provider, usage: Usage | None = None
) -> Extraction:
    """One LLM call for the whole notice. Raises LLMError, BudgetExceeded or ProviderError."""
    return complete_json(
        PROMPT_NAME, Extraction, provider=provider, usage=usage, **prompt_variables(notice, profile)
    )


class ExtractionCache:
    """Extractions on disk, one file per notice release and prompt input.

    The key holds the notice ID and release date (so an amended notice is read
    again) and a hash of the prompt, model and filled-in variables (so editing
    the prompt or the profile never returns a stale extraction).
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, notice: Notice, profile: Profile, model: str) -> Path:
        system, user = load_prompt(PROMPT_NAME)
        payload = json.dumps([system, user, model, prompt_variables(notice, profile)])
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        released = notice.published.strftime("%Y%m%dT%H%M%S")
        return self.directory / f"{notice.notice_id}_{released}_{digest}.json"

    def get(self, notice: Notice, profile: Profile, model: str) -> Extraction | None:
        """The cached extraction, or None if there is none or the file is unreadable."""
        path = self.path_for(notice, profile, model)
        if not path.exists():
            return None
        try:
            return Extraction.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            return None

    def put(self, notice: Notice, profile: Profile, model: str, extraction: Extraction) -> None:
        path = self.path_for(notice, profile, model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(extraction.model_dump_json(indent=1), encoding="utf-8")
