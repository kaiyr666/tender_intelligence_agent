"""Shared test fixtures. Tests never call a real LLM; they use FakeLLM."""

import pytest


class FakeLLM:
    """Stands in for a real provider. Queue the replies a test needs."""

    model = "fake-model"

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def reply_with(self, *replies: str) -> "FakeLLM":
        self.replies.extend(replies)
        return self

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.replies:
            raise AssertionError("FakeLLM was called more times than replies were queued")
        return self.replies.pop(0)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path, monkeypatch):
    """Keep test runs from writing into the real logs/ folder."""
    import app.llm

    monkeypatch.setattr(app.llm, "LOG_PATH", tmp_path / "llm_calls.jsonl")
