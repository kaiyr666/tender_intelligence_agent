import json

import pytest
from pydantic import BaseModel

from app import llm

pytestmark = pytest.mark.usefixtures("test_prompts")


class ExampleFields(BaseModel):
    organisation: str | None
    amount_gbp: float | None
    deadline: str | None


def extract_fields(text: str, provider) -> ExampleFields:
    return llm.complete_json("fields", ExampleFields, provider=provider, text=text)


VALID = json.dumps({"organisation": "Leeds City Council", "amount_gbp": 250000, "deadline": None})


def test_valid_reply_is_parsed_into_the_schema(fake_llm):
    result = extract_fields("Leeds City Council, £250,000", provider=fake_llm.reply_with(VALID))
    assert result == ExampleFields(
        organisation="Leeds City Council", amount_gbp=250000, deadline=None
    )


def test_reply_wrapped_in_code_fences_is_accepted(fake_llm):
    fake_llm.reply_with(f"Here you go:\n```json\n{VALID}\n```")
    assert extract_fields("text", provider=fake_llm).organisation == "Leeds City Council"


def test_invalid_reply_gets_one_retry_with_the_error(fake_llm):
    fake_llm.reply_with('{"organisation": "X", "amount_gbp": "lots"}', VALID)
    result = extract_fields("text", provider=fake_llm)
    assert result.amount_gbp == 250000
    assert len(fake_llm.calls) == 2
    assert "not valid" in fake_llm.calls[1][1]


def test_two_invalid_replies_raise_llm_error(fake_llm):
    fake_llm.reply_with("no json here", "still none")
    with pytest.raises(llm.LLMError):
        extract_fields("text", provider=fake_llm)


def test_prompt_variables_are_filled_in(fake_llm):
    extract_fields("Bid deadline 1 March", provider=fake_llm.reply_with(VALID))
    system, user = fake_llm.calls[0]
    assert "Never guess" in system
    assert "Bid deadline 1 March" in user
    assert "$text" not in user


def test_calls_are_logged_without_content(fake_llm, tmp_path):
    extract_fields("secret business text", provider=fake_llm.reply_with(VALID))
    record = json.loads(llm.LOG_PATH.read_text().strip())
    assert record["ok"] is True
    assert "secret business text" not in json.dumps(record)
