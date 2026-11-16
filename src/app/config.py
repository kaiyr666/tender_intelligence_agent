"""Settings read from environment variables (and from .env when present)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str


def get_settings() -> Settings:
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "")
    if not model:
        raise RuntimeError(f"Set LLM_MODEL in .env for provider '{provider}'.")
    return Settings(llm_provider=provider, llm_model=model)
