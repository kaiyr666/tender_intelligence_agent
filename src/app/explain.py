"""LLM step: a 2-3 sentence rationale for each shortlisted notice.

The model sees only what extraction and scoring produced (labels, numbers,
criterion reasons), never the notice's own text, so a rationale cannot
introduce claims that the scored fields do not support. A rationale that
cannot be written never blocks the report: the score breakdown is there anyway.
"""

import json

from pydantic import BaseModel, Field

from app.llm import BudgetExceeded, LLMError, Provider, ProviderError, Usage, complete_json
from app.score import SHORTLISTED, NoticeResult

PROMPT_NAME = "rationale"
NOT_WRITTEN = "Rationale not written ({reason}); see the score breakdown."


class Rationale(BaseModel):
    rationale: str = Field(max_length=800, description="2-3 sentences for the bid team.")


def rationale_facts(result: NoticeResult) -> dict:
    """The extracted fields and score reasons for the notice's best lot. No notice text."""
    lot = result.best_lot
    lot_x = next(x for x in result.extraction.lots if x.lot_id == lot.lot_id)
    extraction = result.extraction
    return {
        "criteria": [
            {"name": c.name, "score": round(c.score, 2), "reason": c.reason} for c in lot.criteria
        ],
        "primary_service": lot_x.primary_service,
        "services": lot_x.services,
        "contract_length_months": lot_x.contract_length_months,
        "mobilisation_weeks": lot_x.mobilisation_weeks,
        "mandatory_accreditations": [
            r.name
            for r in extraction.notice_mandatory_accreditations + lot_x.mandatory_accreditations
        ],
        "preferred_accreditations": (
            extraction.notice_preferred_accreditations + lot_x.preferred_accreditations
        ),
        "red_flags": sorted({flag.kind for flag in extraction.red_flags}),
        "other_lots_in_notice": len(result.lots) - 1,
    }


def write_rationales(
    results: list[NoticeResult], provider: Provider, usage: Usage
) -> dict[str, str]:
    """Rationale text by notice ID, for shortlisted notices only.

    Invalid output gives a placeholder for that notice. A budget or provider
    error gives a placeholder for that notice and every one after it, without
    further calls (repeating a failing call 30 times would only slow the run).
    """
    rationales = {}
    stopped_reason = None
    for result in results:
        if result.outcome != SHORTLISTED:
            continue
        notice_id = result.notice.notice_id
        if stopped_reason:
            rationales[notice_id] = NOT_WRITTEN.format(reason=stopped_reason)
            continue
        try:
            facts = json.dumps(rationale_facts(result), indent=1, ensure_ascii=False)
            reply = complete_json(PROMPT_NAME, Rationale, provider, usage, facts=facts)
            rationales[notice_id] = reply.rationale.strip()
        except LLMError:
            rationales[notice_id] = NOT_WRITTEN.format(reason="the model's output was invalid")
        except BudgetExceeded:
            stopped_reason = "the LLM budget was reached"
            rationales[notice_id] = NOT_WRITTEN.format(reason=stopped_reason)
        except ProviderError:
            stopped_reason = "the LLM provider failed"
            rationales[notice_id] = NOT_WRITTEN.format(reason=stopped_reason)
    return rationales
