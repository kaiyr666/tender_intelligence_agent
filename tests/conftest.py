"""Shared test fixtures. Tests never call a real LLM; they use FakeLLM."""

import pytest

from app.llm import Reply


class FakeLLM:
    """Stands in for a real provider. Queue the replies a test needs.

    Every reply reports the same token counts, so costs in tests are exact:
    at the fake model's price (1 USD in, 10 USD out per million tokens) a
    call with the defaults costs 0.001 + 0.002 = 0.003 USD.
    """

    model = "fake-model"
    usd_per_mtok = (1.00, 10.00)

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[tuple[str, str]] = []
        self.input_tokens = 1000
        self.output_tokens = 200

    def reply_with(self, *replies: str) -> "FakeLLM":
        self.replies.extend(replies)
        return self

    def complete(self, system: str, user: str) -> Reply:
        self.calls.append((system, user))
        if not self.replies:
            raise AssertionError("FakeLLM was called more times than replies were queued")
        return Reply(self.replies.pop(0), self.input_tokens, self.output_tokens)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path, monkeypatch):
    """Keep test runs from writing into the real logs/ folder."""
    import app.llm

    monkeypatch.setattr(app.llm, "LOG_PATH", tmp_path / "llm_calls.jsonl")
