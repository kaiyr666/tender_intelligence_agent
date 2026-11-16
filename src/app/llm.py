"""The single entry point for every LLM call in this project.

Why one place: prompts stay in files, every output is validated before use,
tests can swap in a fake provider, and changing model or provider is a
one-line change in .env.

Usage:
    usage = Usage(budget_usd=2.0)
    fields = complete_json("example_extract", ExampleFields, usage=usage, text=notice_text)

Cost is controlled before a call, not after: each attempt first checks that a
worst-case estimate of its cost still fits the budget.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings

PROMPTS_DIR = Path(__file__).parent / "prompts"
LOG_PATH = Path("logs/llm_calls.jsonl")
MAX_ATTEMPTS = 2
MAX_OUTPUT_TOKENS = 8000
# Deliberately low, so the pre-call estimate of input tokens errs on the high side.
CHARS_PER_TOKEN_ESTIMATE = 3

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model did not return valid output after all attempts."""


class BudgetExceeded(RuntimeError):
    """The next call could take the run over its LLM budget, so it was not made."""


class ProviderError(RuntimeError):
    """The provider API failed: authentication, network, or rate limits after the SDK's retries."""


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int
    output_tokens: int


class Provider(Protocol):
    model: str
    usd_per_mtok: tuple[float, float]  # (input, output) price per million tokens

    def complete(self, system: str, user: str) -> Reply: ...


@dataclass
class Usage:
    """Tokens and cost for one run, and the budget it must stay under (None means no limit)."""

    budget_usd: float | None = None
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def check(self, estimated_usd: float) -> None:
        """Raise BudgetExceeded if a call costing `estimated_usd` could go over the budget."""
        if self.budget_usd is not None and self.cost_usd + estimated_usd > self.budget_usd:
            raise BudgetExceeded(
                f"spent ${self.cost_usd:.2f} of ${self.budget_usd:.2f}; "
                f"the next call could cost up to ${estimated_usd:.2f}"
            )

    def add(self, usd_per_mtok: tuple[float, float], reply: Reply) -> None:
        self.calls += 1
        self.input_tokens += reply.input_tokens
        self.output_tokens += reply.output_tokens
        self.cost_usd += call_cost(usd_per_mtok, reply.input_tokens, reply.output_tokens)


def call_cost(usd_per_mtok: tuple[float, float], input_tokens: int, output_tokens: int) -> float:
    """USD cost of one call at the given (input, output) price per million tokens."""
    input_price, output_price = usd_per_mtok
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def estimate_input_tokens(*texts: str) -> int:
    return sum(len(text) for text in texts) // CHARS_PER_TOKEN_ESTIMATE + 1


def estimate_cost(usd_per_mtok: tuple[float, float], system: str, user: str) -> float:
    """Worst case for one call: a generous input token count plus the full output allowance."""
    return call_cost(usd_per_mtok, estimate_input_tokens(system, user), MAX_OUTPUT_TOKENS)


class AnthropicProvider:
    def __init__(self, model: str, usd_per_mtok: tuple[float, float]) -> None:
        import anthropic  # imported here so tests never need the SDK configured

        self.model = model
        self.usd_per_mtok = usd_per_mtok
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def complete(self, system: str, user: str) -> Reply:
        import anthropic

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as error:
            raise ProviderError(f"Anthropic API call failed: {error}") from error
        text = "".join(block.text for block in message.content if block.type == "text")
        return Reply(text, message.usage.input_tokens, message.usage.output_tokens)


class OpenAIProvider:
    def __init__(self, model: str, usd_per_mtok: tuple[float, float]) -> None:
        import openai

        self.model = model
        self.usd_per_mtok = usd_per_mtok
        try:
            self._client = openai.OpenAI()  # reads OPENAI_API_KEY
        except openai.OpenAIError as error:  # raised here when no key is set
            raise ProviderError(f"OpenAI client setup failed: {error}") from error

    def complete(self, system: str, user: str) -> Reply:
        import openai

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                # Newer OpenAI models reject the older `max_tokens` parameter.
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
        except openai.OpenAIError as error:
            raise ProviderError(f"OpenAI API call failed: {error}") from error
        text = response.choices[0].message.content or ""
        if response.usage is None:  # count the worst case rather than nothing, so the budget holds
            return Reply(text, estimate_input_tokens(system, user), MAX_OUTPUT_TOKENS)
        return Reply(text, response.usage.prompt_tokens, response.usage.completion_tokens)


def get_provider() -> Provider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings.llm_model, settings.usd_per_mtok)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.llm_model, settings.usd_per_mtok)
    raise RuntimeError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'.")


def load_prompt(name: str) -> tuple[str, str]:
    """Read prompts/<name>.md, split into the '# System' and '# User' sections."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    if "# User" not in text:
        raise ValueError(f"Prompt '{name}' needs a '# User' section.")
    system_part, user_part = text.split("# User", 1)
    return system_part.replace("# System", "", 1).strip(), user_part.strip()


def extract_json(raw: str) -> str:
    """Pull the JSON object out of a reply, tolerating code fences or extra prose."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the reply")
    return raw[start : end + 1]


def complete_json(
    prompt_name: str,
    schema: type[T],
    provider: Provider | None = None,
    usage: Usage | None = None,
    **variables: str,
) -> T:
    """Run a prompt and return its output validated against `schema`.

    Prompt files use $name placeholders, filled from `variables`. If the
    reply is not valid, the model gets one retry with the validation error.
    Each attempt is checked against `usage`'s budget before it is made
    (raising BudgetExceeded), and its tokens are added to `usage` after.
    """
    provider = provider or get_provider()
    usage = usage if usage is not None else Usage()
    system, user_template = load_prompt(prompt_name)
    user = Template(user_template).substitute(variables)
    user += "\n\nReply with a single JSON object only, matching this JSON schema:\n" + json.dumps(
        schema.model_json_schema()
    )

    call = Usage()  # this call's attempts only, for the log
    started = time.monotonic()
    last_error = ""
    for _attempt in range(MAX_ATTEMPTS):
        usage.check(estimate_cost(provider.usd_per_mtok, system, user))
        reply = provider.complete(system, user)
        usage.add(provider.usd_per_mtok, reply)
        call.add(provider.usd_per_mtok, reply)
        try:
            result = schema.model_validate_json(extract_json(reply.text))
        except (ValueError, ValidationError) as error:
            last_error = str(error)
            user += f"\n\nYour previous reply was not valid ({last_error}). Try again."
            continue
        _log_call(prompt_name, provider.model, started, call, ok=True)
        return result

    _log_call(prompt_name, provider.model, started, call, ok=False)
    raise LLMError(f"'{prompt_name}' failed after {MAX_ATTEMPTS} attempts: {last_error}")


def _log_call(prompt: str, model: str, started: float, call: Usage, ok: bool) -> None:
    """Append call metadata, tokens and cost (never the content) to logs/llm_calls.jsonl."""
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt": prompt,
        "model": model,
        "attempts": call.calls,
        "ok": ok,
        "seconds": round(time.monotonic() - started, 2),
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "cost_usd": round(call.cost_usd, 5),
    }
    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")
