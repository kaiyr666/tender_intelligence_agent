"""The company profile loads from TOML and rejects incomplete or malformed config."""

import pytest
from pydantic import ValidationError

from app.profile import load_profile

VALID_TOML = """
[services]
offered = ["office and commercial cleaning"]
excluded = ["catering"]

[cpv]
codes = ["90910000"]
broad_codes = ["90900000"]

[value]
min_gbp = 100_000
max_gbp = 5_000_000

[region]
nuts_codes = ["UKC"]

[accreditations]
held = ["ISO 9001"]

[mobilisation]
min_weeks = 8
"""


def write_toml(tmp_path, text):
    path = tmp_path / "profile.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_real_profile_loads_value_band():
    profile = load_profile()
    assert (profile.value.min_gbp, profile.value.max_gbp) == (100_000, 5_000_000)


def test_real_profile_region_is_the_north():
    assert load_profile().region.nuts_codes == ["UKC", "UKD", "UKE"]


def test_real_profile_mobilisation_is_eight_weeks():
    assert load_profile().mobilisation.min_weeks == 8


def test_profile_loads_from_a_given_path(tmp_path):
    profile = load_profile(write_toml(tmp_path, VALID_TOML))
    assert profile.cpv.codes == ["90910000"]


def test_missing_section_is_rejected(tmp_path):
    without_mobilisation = VALID_TOML.split("[mobilisation]")[0]
    with pytest.raises(ValidationError):
        load_profile(write_toml(tmp_path, without_mobilisation))


def test_missing_field_is_rejected(tmp_path):
    without_max = VALID_TOML.replace("max_gbp = 5_000_000\n", "")
    with pytest.raises(ValidationError):
        load_profile(write_toml(tmp_path, without_max))


@pytest.mark.parametrize("bad_code", ["9091000", "909100000", "9091000A"])
def test_cpv_code_that_is_not_eight_digits_is_rejected(tmp_path, bad_code):
    text = VALID_TOML.replace('codes = ["90910000"]', f'codes = ["{bad_code}"]')
    with pytest.raises(ValidationError):
        load_profile(write_toml(tmp_path, text))
