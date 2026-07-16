import asyncio
from dataclasses import dataclass

from app.core.model_catalog import build_model_catalog
from app.main import model_catalog


@dataclass(frozen=True)
class FakeSettings:
    small_model: str = "ollama/llama3.2"
    medium_model: str = "paid/model"
    frontier_model: str = "unknown/model"
    model_prices_json: str = (
        '{"paid/model": {"input_per_1k": "0.01", "output_per_1k": "0.02"}}'
    )


def test_build_model_catalog_lists_tiers_prices_and_sources() -> None:
    catalog = build_model_catalog(FakeSettings())

    assert [item.tier for item in catalog] == ["small", "medium", "frontier"]

    assert catalog[0].model == "ollama/llama3.2"
    assert catalog[0].provider == "ollama"
    assert catalog[0].is_local is True
    assert catalog[0].price_source == "built_in"
    assert catalog[0].input_price_per_1k == "0"
    assert catalog[0].output_price_per_1k == "0"

    assert catalog[1].model == "paid/model"
    assert catalog[1].provider == "paid"
    assert catalog[1].is_local is False
    assert catalog[1].price_source == "configured"
    assert catalog[1].input_price_per_1k == "0.01"
    assert catalog[1].output_price_per_1k == "0.02"

    assert catalog[2].model == "unknown/model"
    assert catalog[2].price_source == "missing"
    assert catalog[2].input_price_per_1k is None
    assert catalog[2].output_price_per_1k is None


def test_model_catalog_endpoint_returns_configured_models(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.medium_model", "paid/model")
    monkeypatch.setattr("app.main.settings.frontier_model", "unknown/model")
    monkeypatch.setattr(
        "app.main.settings.model_prices_json",
        '{"paid/model": ["0.01", "0.02"]}',
    )

    response = asyncio.run(model_catalog())

    assert len(response.models) == 3
    assert response.models[0].tier == "small"
    assert response.models[1].price_source == "configured"
    assert response.models[2].price_source == "missing"
