"""Remove contact details from free text before it is stored or sent anywhere."""

import re

EMAIL_PLACEHOLDER = "[email removed]"
PHONE_PLACEHOLDER = "[phone removed]"

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# UK numbers: 0 or +44, then 9-10 digits in up to three groups, e.g. "0113 496 0000",
# "+44 20 7946 0958", "(0113) 496 0000". Eight-digit CPV codes are too short to match.
PHONE = re.compile(r"(?:\+44\s?\(?0?\)?\s?|\(0|\b0)\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b")


def mask_contacts(text: str | None) -> str | None:
    """Replace email addresses and UK phone numbers with placeholders. None stays None."""
    if text is None:
        return None
    return PHONE.sub(PHONE_PLACEHOLDER, EMAIL.sub(EMAIL_PLACEHOLDER, text))
