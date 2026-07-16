from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.cost import model_price_source, model_prices_for
from app.core.providers import provider_from_model_name


class ModelCatalogSettings(Protocol):
    small_model: str
    medium_model: str
    frontier_model: str
    model_prices_json: str


@dataclass(frozen=True)
class CatalogModel:
    tier: str
    model: str
    provider: str | None
    is_local: bool
    price_source: str
    input_price_per_1k: str | None
    output_price_per_1k: str | None


def price_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def build_model_catalog(settings: ModelCatalogSettings) -> list[CatalogModel]:
    tier_models = [
        ("small", settings.small_model),
        ("medium", settings.medium_model),
        ("frontier", settings.frontier_model),
    ]

    catalog: list[CatalogModel] = []
    for tier, model in tier_models:
        prices = model_prices_for(model, settings.model_prices_json)
        input_price = prices[0] if prices is not None else None
        output_price = prices[1] if prices is not None else None

        catalog.append(
            CatalogModel(
                tier=tier,
                model=model,
                provider=provider_from_model_name(model),
                is_local=model.startswith("ollama/"),
                price_source=model_price_source(model, settings.model_prices_json),
                input_price_per_1k=price_to_string(input_price),
                output_price_per_1k=price_to_string(output_price),
            )
        )

    return catalog
