"""The company profile, read from config/profile.toml."""

import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, StringConstraints

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "profile.toml"

CpvCode = Annotated[str, StringConstraints(pattern=r"^\d{8}$")]


class Services(BaseModel):
    offered: list[str]
    excluded: list[str]


class CpvRules(BaseModel):
    codes: list[CpvCode]
    broad_codes: list[CpvCode]


class ValueBand(BaseModel):
    min_gbp: float
    max_gbp: float


class Region(BaseModel):
    nuts_codes: list[str]


class Accreditations(BaseModel):
    held: list[str]


class Mobilisation(BaseModel):
    min_weeks: int


class Deadline(BaseModel):
    min_days: int


class Weights(BaseModel):
    service: float
    region: float
    value: float
    accreditations: float
    mobilisation: float
    deadline: float


class Scoring(BaseModel):
    shortlist_threshold: float
    weights: Weights


class Profile(BaseModel):
    services: Services
    cpv: CpvRules
    value: ValueBand
    region: Region
    accreditations: Accreditations
    mobilisation: Mobilisation
    deadline: Deadline
    scoring: Scoring


def load_profile(path: Path = DEFAULT_PROFILE_PATH) -> Profile:
    """Read and validate the profile. Raises if a section or field is missing."""
    with path.open("rb") as file:
        return Profile.model_validate(tomllib.load(file))
