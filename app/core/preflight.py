from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.cost import decimal_usd, model_price_source, model_prices_for
from app.core.prompt_compressor import normalize_messages


@dataclass(frozen=True)
class EstimatedModelCost:
    price_source: str
    estimated_input_cost_usd: str | None
    estimated_output_cost_usd: str | None
    estimated_total_cost_usd: str | None


@dataclass(frozen=True)
class BudgetCheck:
    status: str
    exceeded: bool


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def estimate_message_tokens(messages: list[Any]) -> int:
    total = 2
    for message in normalize_messages(messages):
        total += 4
        total += estimate_text_tokens(message["role"])
        total += estimate_text_tokens(message["content"])
    return total


def estimate_model_cost(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    model_prices_json: str | None = None,
) -> EstimatedModelCost:
    prices = model_prices_for(model, model_prices_json)
    price_source = model_price_source(model, model_prices_json)
    if prices is None:
        return EstimatedModelCost(
            price_source=price_source,
            estimated_input_cost_usd=None,
            estimated_output_cost_usd=None,
            estimated_total_cost_usd=None,
        )

    input_price, output_price = prices
    input_cost = decimal_usd(Decimal(prompt_tokens) / Decimal(1000) * input_price)
    output_cost = decimal_usd(Decimal(completion_tokens) / Decimal(1000) * output_price)
    return EstimatedModelCost(
        price_source=price_source,
        estimated_input_cost_usd=str(input_cost),
        estimated_output_cost_usd=str(output_cost),
        estimated_total_cost_usd=str(input_cost + output_cost),
    )


def check_estimated_budget(
    estimated_total_cost_usd: str | None,
    max_estimated_cost_usd: float | None,
) -> BudgetCheck:
    if max_estimated_cost_usd is None:
        return BudgetCheck(status="not_set", exceeded=False)

    if estimated_total_cost_usd is None:
        return BudgetCheck(status="unknown", exceeded=False)

    estimated_cost = Decimal(str(estimated_total_cost_usd))
    max_cost = Decimal(str(max_estimated_cost_usd))
    if estimated_cost > max_cost:
        return BudgetCheck(status="exceeds_budget", exceeded=True)

    return BudgetCheck(status="within_budget", exceeded=False)
