"""Integer pricing: micro-USD per million tokens, rounded once at settlement."""

import os
from pathlib import Path

import yaml

VERSION = "2026-10-28.2"
RATES = {
    "mock/premium": (3_000_000, 15_000_000),
    "mock/backup": (3_000_000, 15_000_000),
    "mock/outage": (3_000_000, 15_000_000),
    "mock/balanced": (1_000_000, 5_000_000),
    "mock/economy": (1_000_000, 2_000_000),
    "openai/gpt-4.1": (2_000_000, 8_000_000),
    "openai/gpt-4.1-mini": (400_000, 1_600_000),
    "anthropic/claude-sonnet-4-20250514": (3_000_000, 15_000_000),
    "anthropic/claude-3-5-haiku-20241022": (800_000, 4_000_000),
    "google/gemini-2.5-flash": (300_000, 2_500_000),
}
path = Path(os.getenv("TOLLGATE_PRICING_FILE", "config/pricing.yaml"))
if path.exists():
    configured = yaml.safe_load(path.read_text())
    if "models" in configured:
        if configured.get("unit") != "micro_usd_per_million_tokens":
            raise ValueError("Unsupported pricing unit")
        VERSION = str(configured["version"])
        table = configured["models"]
        factor = 1
    else:
        # Backwards compatible legacy config, explicitly priced in whole micro-USD/token.
        table, factor = configured, 1_000_000
        VERSION = "legacy-per-token"
    for model, prices in table.items():
        if (
            model.split("/")[0] not in ("mock", "openai", "anthropic", "google")
            or len(prices) != 2
            or any(type(n) is not int or n < 0 for n in prices)
        ):
            raise ValueError("Pricing requires supported targets and two nonnegative integer rates")
        RATES[model] = tuple(n * factor for n in prices)


def cost(model: str, input_tokens: int, output_tokens: int) -> int:
    incoming, outgoing = RATES[model]
    return (input_tokens * incoming + output_tokens * outgoing + 999_999) // 1_000_000
