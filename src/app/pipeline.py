"""Example pipeline. Replace it in the first slice.

It shows the intended split: deterministic code for exact things
(`basic_facts`), the LLM only for reading messy text (`extract_fields`).
"""

import re

from pydantic import BaseModel

from app.llm import Provider, complete_json

AMOUNT = re.compile(r"£\s?([\d,]+(?:\.\d+)?)")


class ExampleFields(BaseModel):
    organisation: str | None
    amount_gbp: float | None
    deadline: str | None


def basic_facts(text: str) -> dict:
    """Deterministic facts: no model needed, always the same answer."""
    amounts = [float(a.replace(",", "")) for a in AMOUNT.findall(text)]
    return {
        "word_count": len(text.split()),
        "max_amount_gbp": max(amounts) if amounts else None,
    }


def extract_fields(text: str, provider: Provider | None = None) -> ExampleFields:
    """LLM step: read free text into a validated structure."""
    return complete_json("example_extract", ExampleFields, provider=provider, text=text)


def run(text: str) -> dict:
    """Entry point used by the CLI and the eval harness."""
    return basic_facts(text)
