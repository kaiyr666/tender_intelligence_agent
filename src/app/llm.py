"""The single entry point for every LLM call in this project.

Why one place: prompts stay in files, every output is validated before use,
tests can swap in a fake provider, and changing model or provider is a
one-line change in .env.

Usage:
    fields = complete_json("example_extract", ExampleFields, text=notice_text)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from string import Template
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings

PROMPTS_DIR = Path(__file__).parent / "prompts"
LOG_PATH = Path("logs/llm_calls.jsonl")
MAX_ATTEMPTS = 2

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model did not return valid output after all attempts."""


class Provider(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str: ...


class AnthropicProvider:
    def __init__(self, model: str) -> None:
        import anthropic  # imported here so tests never need the SDK configured

        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def complete(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in message.content if block.type == "text")


class OpenAIProvider:
    def __init__(self, model: str) -> None:
        import openai

        self.model = model
        self._client = openai.OpenAI()  # reads OPENAI_API_KEY

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


def get_provider() -> Provider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.llm_model)
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
    **variables: str,
) -> T:
    """Run a prompt and return its output validated against `schema`.

    Prompt files use $name placeholders, filled from `variables`. If the
    reply is not valid, the model gets one retry with the validation error.
    """
    provider = provider or get_provider()
    system, user_template = load_prompt(prompt_name)
    user = Template(user_template).substitute(variables)
    user += "\n\nReply with a single JSON object only, matching this JSON schema:\n" + json.dumps(
        schema.model_json_schema()
    )

    started = time.monotonic()
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = provider.complete(system, user)
        try:
            result = schema.model_validate_json(extract_json(raw))
        except (ValueError, ValidationError) as error:
            last_error = str(error)
            user += f"\n\nYour previous reply was not valid ({last_error}). Try again."
            continue
        _log_call(prompt_name, provider.model, started, attempt, ok=True)
        return result

    _log_call(prompt_name, provider.model, started, MAX_ATTEMPTS, ok=False)
    raise LLMError(f"'{prompt_name}' failed after {MAX_ATTEMPTS} attempts: {last_error}")


def _log_call(prompt: str, model: str, started: float, attempts: int, ok: bool) -> None:
    """Append call metadata (never the content) to logs/llm_calls.jsonl."""
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt": prompt,
        "model": model,
        "attempts": attempts,
        "ok": ok,
        "seconds": round(time.monotonic() - started, 2),
    }
    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")
