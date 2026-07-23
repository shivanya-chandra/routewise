import json
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MODEL_PRICES_PER_1K_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    "ollama/llama3.2": (Decimal("0"), Decimal("0")),
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.00060")),
    "gpt-4o": (Decimal("0.0025"), Decimal("0.0100")),
}


def decimal_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def parse_price_pair(model: str, raw_prices: Any) -> tuple[Decimal, Decimal]:
    if isinstance(raw_prices, dict):
        input_price = raw_prices.get("input_per_1k")
        output_price = raw_prices.get("output_per_1k")
    elif isinstance(raw_prices, (list, tuple)) and len(raw_prices) == 2:
        input_price, output_price = raw_prices
    else:
        raise ValueError(f"Invalid price entry for {model}")

    return Decimal(str(input_price)), Decimal(str(output_price))


def load_model_prices(prices_json: str | None = None) -> dict[str, tuple[Decimal, Decimal]]:
    prices = dict(MODEL_PRICES_PER_1K_TOKENS)
    raw_json = prices_json if prices_json is not None else os.getenv("MODEL_PRICES_JSON", "")
    if not raw_json:
        return prices

    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        raise ValueError("MODEL_PRICES_JSON must be a JSON object")

    for model, raw_prices in parsed.items():
        prices[str(model)] = parse_price_pair(str(model), raw_prices)

    return prices


def configured_price_models(prices_json: str | None = None) -> set[str]:
    raw_json = prices_json if prices_json is not None else os.getenv("MODEL_PRICES_JSON", "")
    if not raw_json:
        return set()

    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        raise ValueError("MODEL_PRICES_JSON must be a JSON object")

    return {str(model) for model in parsed}


def model_prices_for(
    model: str,
    model_prices_json: str | None = None,
) -> tuple[Decimal, Decimal] | None:
    prices = load_model_prices(model_prices_json)
    if model in prices:
        return prices[model]

    if model.startswith("ollama/"):
        return Decimal("0"), Decimal("0")

    return None


def model_price_source(model: str, model_prices_json: str | None = None) -> str:
    if model in configured_price_models(model_prices_json):
        return "configured"

    if model in MODEL_PRICES_PER_1K_TOKENS:
        return "built_in"

    if model.startswith("ollama/"):
        return "local_zero"

    return "missing"


def estimate_cost_usd(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    model_prices_json: str | None = None,
) -> Decimal | None:
    prices = model_prices_for(model, model_prices_json)
    if prices is None or prompt_tokens is None or completion_tokens is None:
        return None

    input_price, output_price = prices
    return decimal_usd(
        Decimal(prompt_tokens) / Decimal(1000) * input_price
        + Decimal(completion_tokens) / Decimal(1000) * output_price
    )
