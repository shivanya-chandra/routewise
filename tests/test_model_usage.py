import asyncio
from decimal import Decimal

from app.db.metrics import ModelUsage, build_model_usage
from app.main import model_usage


def test_build_model_usage_calculates_rates_tokens_cost_and_latency() -> None:
    usage = build_model_usage(
        [
            {
                "model": "ollama/llama3.2",
                "provider": "ollama",
                "total_calls": 4,
                "successful_calls": 3,
                "failed_calls": 1,
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "estimated_cost_usd": Decimal("0.00000000"),
                "latency_sum": 4000,
            }
        ]
    )

    assert len(usage) == 1
    assert usage[0].model == "ollama/llama3.2"
    assert usage[0].provider == "ollama"
    assert usage[0].total_calls == 4
    assert usage[0].success_rate == 0.75
    assert usage[0].failed_calls == 1
    assert usage[0].total_tokens == 125
    assert usage[0].estimated_cost_usd == "0E-8"
    assert usage[0].average_latency_ms == 1000


def test_build_model_usage_handles_empty_rows() -> None:
    assert build_model_usage([]) == []


def test_model_usage_endpoint_returns_model_rows(monkeypatch) -> None:
    async def fake_fetch_model_usage() -> list[ModelUsage]:
        return [
            ModelUsage(
                model="ollama/llama3.2",
                provider="ollama",
                total_calls=4,
                successful_calls=3,
                failed_calls=1,
                success_rate=0.75,
                prompt_tokens=100,
                completion_tokens=25,
                total_tokens=125,
                estimated_cost_usd="0E-8",
                average_latency_ms=1000,
            )
        ]

    monkeypatch.setattr("app.main.fetch_model_usage", fake_fetch_model_usage)

    response = asyncio.run(model_usage())

    assert len(response.models) == 1
    assert response.models[0].model == "ollama/llama3.2"
    assert response.models[0].success_rate == 0.75
    assert response.models[0].total_tokens == 125
