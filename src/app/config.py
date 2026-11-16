"""Settings read from environment variables (and from .env when present)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5"}
# USD per million tokens (input, output) for models whose price is known here. Any other
# model needs LLM_INPUT_USD_PER_MTOK and LLM_OUTPUT_USD_PER_MTOK, or the budget cannot work.
KNOWN_PRICES = {"claude-sonnet-5-5": (2.00, 10.00)}
DEFAULT_BUDGET_USD = 2.50


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    usd_per_mtok: tuple[float, float]  # (input, output)
    budget_usd: float


def get_settings() -> Settings:
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "")
    if not model:
        raise RuntimeError(f"Set LLM_MODEL in .env for provider '{provider}'.")
    return Settings(
        llm_provider=provider,
        llm_model=model,
        usd_per_mtok=_prices(model),
        budget_usd=_positive_float("LLM_BUDGET_USD", DEFAULT_BUDGET_USD),
    )


def _prices(model: str) -> tuple[float, float]:
    if os.getenv("LLM_INPUT_USD_PER_MTOK") or os.getenv("LLM_OUTPUT_USD_PER_MTOK"):
        return (
            _positive_float("LLM_INPUT_USD_PER_MTOK"),
            _positive_float("LLM_OUTPUT_USD_PER_MTOK"),
        )
    if model in KNOWN_PRICES:
        return KNOWN_PRICES[model]
    raise RuntimeError(
        f"No price known for model '{model}'. Set LLM_INPUT_USD_PER_MTOK and "
        "LLM_OUTPUT_USD_PER_MTOK in .env (USD per million tokens) so the budget can be enforced."
    )


def _positive_float(name: str, default: float | None = None) -> float:
    raw = os.getenv(name, "").strip()
    if not raw and default is not None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"{name} in .env must be a number, got '{raw}'.") from None
    if value <= 0:
        raise RuntimeError(f"{name} in .env must be greater than 0.")
    return value
