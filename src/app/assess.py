"""Extract and score every pre-filtered notice, within the LLM budget."""

from collections import Counter
from datetime import datetime

from app.extract import ExtractionCache, extract_notice
from app.llm import BudgetExceeded, LLMError, Provider, Usage
from app.notices import Notice
from app.profile import Profile
from app.score import NEEDS_REVIEW, NOT_PROCESSED, NoticeResult, score_notice, without_extraction

BUDGET_REACHED = "the LLM budget was reached before this notice"


def assess(
    notices: list[Notice],
    profile: Profile,
    now: datetime,
    provider: Provider,
    usage: Usage,
    cache: ExtractionCache,
) -> list[NoticeResult]:
    """One result per notice, in the same order.

    Cached extractions are always used, even after the budget is reached.
    A notice whose extraction fails goes to "needs review" and the run carries
    on. Once a call would exceed the budget, notices without a cached
    extraction are "not processed". ProviderError (e.g. a bad API key) is not
    caught: it stops the run, and the extractions cached so far are kept.
    """
    results = []
    budget_reached = False
    for notice in notices:
        extraction = cache.get(notice, profile, provider.model)
        if extraction is None and budget_reached:
            results.append(without_extraction(notice, NOT_PROCESSED, BUDGET_REACHED))
            continue
        if extraction is None:
            try:
                extraction = extract_notice(notice, profile, provider, usage)
            except BudgetExceeded:
                budget_reached = True
                results.append(without_extraction(notice, NOT_PROCESSED, BUDGET_REACHED))
                continue
            except LLMError:
                reason = "the extraction failed: the model did not return valid output"
                results.append(without_extraction(notice, NEEDS_REVIEW, reason))
                continue
            cache.put(notice, profile, provider.model, extraction)
        results.append(score_notice(notice, extraction, profile, now))
    return results


def format_assessment(results: list[NoticeResult], usage: Usage) -> str:
    """Plain-text outcome counts and the shortlist, for the terminal."""
    counts = Counter(r.outcome for r in results)
    lines = ["Assessment of the pre-filtered notices"]
    lines += [f"  {outcome}: {count}" for outcome, count in counts.most_common()]
    lines.append(f"  LLM calls: {usage.calls}, cost ${usage.cost_usd:.2f}")
    shortlist = sorted(
        (r for r in results if r.best_lot and r.outcome == "shortlisted"),
        key=lambda r: r.best_lot.score,
        reverse=True,
    )
    for result in shortlist:
        lines.append(
            f"  {result.best_lot.score:.2f}  {result.notice.notice_id}  {result.notice.title}"
            f"  [{result.best_lot.lot_name}]"
        )
    return "\n".join(lines)
