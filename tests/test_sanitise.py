"""Contact details are masked in free text; numbers that are not contacts are left alone."""

import pytest

from app.sanitise import EMAIL_PLACEHOLDER, PHONE_PLACEHOLDER, mask_contacts


def test_none_stays_none():
    assert mask_contacts(None) is None


def test_empty_text_stays_empty():
    assert mask_contacts("") == ""


def test_text_without_contacts_is_unchanged():
    text = "Window and high level cleaning at several public buildings."
    assert mask_contacts(text) == text


def test_email_is_replaced_with_placeholder():
    assert mask_contacts("Contact bids@example.org for details.") == (
        f"Contact {EMAIL_PLACEHOLDER} for details."
    )


def test_email_with_dots_plus_and_subdomain_is_masked():
    masked = mask_contacts("Write to j.smith+bids@procurement.council.gov.uk now.")
    assert masked == f"Write to {EMAIL_PLACEHOLDER} now."


@pytest.mark.parametrize(
    "phone",
    ["0113 496 0000", "01234 567890", "07700 900123", "+44 20 7946 0958", "(0113) 496 0000"],
)
def test_uk_phone_number_is_replaced_with_placeholder(phone):
    assert mask_contacts(f"Call {phone} today.") == f"Call {PHONE_PLACEHOLDER} today."


def test_email_and_phone_in_one_sentence_are_both_masked_and_punctuation_kept():
    text = "Questions to jane.example@example.org or call 0113 496 0002."
    assert mask_contacts(text) == (f"Questions to {EMAIL_PLACEHOLDER} or call {PHONE_PLACEHOLDER}.")


@pytest.mark.parametrize(
    "text",
    [
        "Estimated value £250,000 excluding VAT.",
        "Total £1,200,000 over the contract term.",
        "The contract runs 2026-2027.",
        "Services start on 1 April 2027.",
        "CPV 03000000 Agricultural products.",
        "CPV 90911200 Building-cleaning services.",
        "See notice 108257-2026 on Find a Tender.",
    ],
)
def test_money_dates_cpv_codes_and_notice_ids_are_not_masked(text):
    assert mask_contacts(text) == text
