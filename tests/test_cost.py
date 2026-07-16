from decimal import Decimal

from app.core.cost import estimate_cost_usd, load_model_prices, model_prices_for


def test_ollama_models_are_estimated_as_zero_cost() -> None:
    assert estimate_cost_usd("ollama/llama3.2", 31, 3) == Decimal("0E-8")
    assert estimate_cost_usd("ollama/custom", 31, 3) == Decimal("0E-8")


def test_unknown_model_cost_is_none_without_price_configuration() -> None:
    assert estimate_cost_usd("unknown/model", 100, 100) is None


def test_model_prices_can_be_loaded_from_json() -> None:
    prices = load_model_prices(
        '{"paid/model": {"input_per_1k": "0.01", "output_per_1k": "0.02"}}'
    )

    assert prices["paid/model"] == (Decimal("0.01"), Decimal("0.02"))


def test_estimate_cost_uses_configured_model_prices() -> None:
    cost = estimate_cost_usd(
        "paid/model",
        prompt_tokens=1000,
        completion_tokens=500,
        model_prices_json='{"paid/model": ["0.01", "0.02"]}',
    )

    assert cost == Decimal("0.02000000")


def test_model_prices_for_returns_none_when_missing() -> None:
    assert model_prices_for("paid/model", "{}") is None
