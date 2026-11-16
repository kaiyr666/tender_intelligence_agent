"""Token usage, cost and the pre-call budget check in llm.py."""

import json

import pytest

from app import llm
from app.llm import BudgetExceeded, LLMError, Usage, call_cost, complete_json, estimate_cost
from app.pipeline import ExampleFields

VALID = json.dumps({"organisation": "X", "amount_gbp": 1, "deadline": None})
INVALID = "no json here"
ONE_CALL_USD = 0.003  # FakeLLM: 1000 tokens at $1/M in + 200 tokens at $10/M out


def run(fake_llm, usage, text="Some text"):
    return complete_json(
        "example_extract", ExampleFields, provider=fake_llm, usage=usage, text=text
    )


def first_attempt_estimate(fake_llm):
    """The estimate for the exact messages the fake was sent on its first call."""
    system, user = fake_llm.calls[0]
    return estimate_cost(fake_llm.usd_per_mtok, system, user)


# call_cost and estimate_cost


def test_call_cost_is_tokens_times_price_per_million():
    assert call_cost((1.0, 10.0), 1000, 200) == pytest.approx(0.003)


def test_call_cost_uses_separate_input_and_output_prices():
    assert call_cost((3.0, 15.0), 2_000_000, 1_000_000) == pytest.approx(21.0)


def test_estimate_covers_a_reply_of_max_output_tokens():
    prices = (1.0, 10.0)
    system, user = "s" * 3000, "u" * 9000
    input_tokens = len(system + user) // llm.CHARS_PER_TOKEN_ESTIMATE
    worst_case = call_cost(prices, input_tokens, llm.MAX_OUTPUT_TOKENS)
    assert estimate_cost(prices, system, user) >= worst_case


def test_estimate_grows_with_input_length():
    prices = (1.0, 10.0)
    assert estimate_cost(prices, "s", "u" * 30_000) > estimate_cost(prices, "s", "u")


# Usage recorded per call


def test_one_call_adds_its_tokens_and_cost_to_usage(fake_llm):
    usage = Usage()
    run(fake_llm.reply_with(VALID), usage)
    assert (usage.calls, usage.input_tokens, usage.output_tokens) == (1, 1000, 200)
    assert usage.cost_usd == pytest.approx(ONE_CALL_USD)


def test_usage_accumulates_across_calls(fake_llm):
    usage = Usage()
    run(fake_llm.reply_with(VALID, VALID), usage)
    run(fake_llm, usage)
    assert usage.calls == 2
    assert usage.cost_usd == pytest.approx(2 * ONE_CALL_USD)


def test_retry_after_invalid_reply_counts_both_attempts(fake_llm):
    usage = Usage()
    run(fake_llm.reply_with(INVALID, VALID), usage)
    assert usage.calls == 2
    assert usage.cost_usd == pytest.approx(2 * ONE_CALL_USD)


def test_two_invalid_replies_raise_llm_error_and_both_are_counted(fake_llm):
    usage = Usage()
    with pytest.raises(LLMError):
        run(fake_llm.reply_with(INVALID, INVALID), usage)
    assert usage.calls == 2
    assert usage.cost_usd == pytest.approx(2 * ONE_CALL_USD)


def test_no_budget_means_no_limit(fake_llm):
    usage = Usage(budget_usd=None)
    for _ in range(5):
        run(fake_llm.reply_with(VALID), usage)
    assert usage.calls == 5


# Budget check before each attempt


def test_zero_budget_raises_without_calling_the_provider(fake_llm):
    usage = Usage(budget_usd=0.0)
    with pytest.raises(BudgetExceeded):
        run(fake_llm.reply_with(VALID), usage)
    assert fake_llm.calls == []
    assert usage.calls == 0


def test_budget_is_checked_against_worst_case_not_actual_cost(fake_llm):
    # The real reply would cost 0.003, but a reply of MAX_OUTPUT_TOKENS could not fit.
    usage = Usage(budget_usd=0.004)
    with pytest.raises(BudgetExceeded):
        run(fake_llm.reply_with(VALID), usage)
    assert fake_llm.calls == []


def test_spent_cost_counts_towards_the_budget(fake_llm):
    run(fake_llm.reply_with(VALID), Usage())
    estimate = first_attempt_estimate(fake_llm)
    usage = Usage(budget_usd=estimate + 0.001, cost_usd=0.002)
    with pytest.raises(BudgetExceeded):
        run(fake_llm.reply_with(VALID), usage)
    assert len(fake_llm.calls) == 1


def test_call_is_made_when_estimate_exactly_fills_the_budget(fake_llm):
    run(fake_llm.reply_with(VALID), Usage())
    usage = Usage(budget_usd=first_attempt_estimate(fake_llm))
    run(fake_llm.reply_with(VALID), usage)
    assert usage.calls == 1


def test_budget_is_checked_again_before_the_retry(fake_llm):
    run(fake_llm.reply_with(VALID), Usage())
    # Room for the first attempt, but not for a second after paying 0.003 for the first.
    usage = Usage(budget_usd=first_attempt_estimate(fake_llm) + 0.001)
    fake_llm.calls.clear()
    with pytest.raises(BudgetExceeded):
        run(fake_llm.reply_with(INVALID, VALID), usage)
    assert len(fake_llm.calls) == 1
    assert usage.calls == 1


# Log line


def test_log_line_records_tokens_and_cost(fake_llm):
    run(fake_llm.reply_with(VALID), Usage())
    record = json.loads(llm.LOG_PATH.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert (record["input_tokens"], record["output_tokens"]) == (1000, 200)
    assert record["cost_usd"] == pytest.approx(ONE_CALL_USD)


def test_log_line_never_contains_the_prompt(fake_llm):
    run(fake_llm.reply_with(VALID), Usage(), text="confidential tender wording")
    log = llm.LOG_PATH.read_text(encoding="utf-8")
    system, _ = fake_llm.calls[0]
    assert "confidential tender wording" not in log
    assert system not in log
