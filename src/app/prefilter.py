"""Cheap, exact checks that drop notices before any LLM call."""

from dataclasses import dataclass
from datetime import datetime

from app.notices import Notice
from app.profile import CpvRules, Profile

CLOSED = "closed"
LOW_VALUE = "value under minimum"
NO_CPV_MATCH = "no matching CPV code"


@dataclass(frozen=True)
class Screened:
    notice: Notice
    drop_reason: str | None  # None means the notice is kept


def cpv_matches(code: str, rules: CpvRules) -> bool:
    """True if `code` is a profile code or sits under one, or is one of the broad codes exactly."""
    if code in rules.broad_codes:
        return True
    return any(code.startswith(_significant_digits(profile_code)) for profile_code in rules.codes)


def prefilter(notices: list[Notice], profile: Profile, now: datetime) -> list[Screened]:
    """Return every notice with the first reason it was dropped, or None if kept."""
    return [Screened(notice, _drop_reason(notice, profile, now)) for notice in notices]


def _drop_reason(notice: Notice, profile: Profile, now: datetime) -> str | None:
    if notice.status == "complete" or (notice.deadline is not None and notice.deadline < now):
        return CLOSED
    if notice.value_gbp is not None and notice.value_gbp < profile.value.min_gbp:
        return LOW_VALUE
    codes = set(notice.cpv_codes).union(*(lot.cpv_codes for lot in notice.lots))
    if codes and not any(cpv_matches(code, profile.cpv) for code in codes):
        return NO_CPV_MATCH
    return None


def _significant_digits(code: str) -> str:
    """The prefix that defines a CPV code's place in the hierarchy.

    Trailing zeros mark a broader level, but the first two digits (the division)
    always count: 50700000 -> "507", 50000000 -> "50", never "5".
    """
    return code[:2] + code[2:].rstrip("0")
