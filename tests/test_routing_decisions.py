import asyncio
from decimal import Decimal

from app.db.metrics import RoutingDecisionUsage, build_routing_decisions
from app.main import routing_decisions


def test_build_routing_decisions_calculates_rates_and_totals() -> None:
    decisions = build_routing_decisions(
        [
            {
                "selected_model": "cache",
                "final_model": "cache",
                "cache_hit": True,
                "request_count": 3,
                "total_fallbacks": 0,
                "compressed_requests": 0,
                "prompt_words_saved": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": Decimal("0"),
                "latency_sum": 15,
                "average_quality_score": Decimal("1.0"),
            },
            {
                "selected_model": "ollama/llama3.2",
                "final_model": "ollama/llama3.2",
                "cache_hit": False,
                "request_count": 1,
                "total_fallbacks": 0,
                "compressed_requests": 1,
                "prompt_words_saved": 350,
                "prompt_tokens": 724,
                "completion_tokens": 35,
                "estimated_cost_usd": Decimal("0.00000000"),
                "latency_sum": 11195,
                "average_quality_score": Decimal("0.92"),
            },
        ]
    )

    assert decisions[0].selected_model == "cache"
    assert decisions[0].request_rate == 0.75
    assert decisions[0].average_latency_ms == 5
    assert decisions[0].average_quality_score == 1.0
    assert decisions[1].request_rate == 0.25
    assert decisions[1].compressed_requests == 1
    assert decisions[1].prompt_words_saved == 350
    assert decisions[1].total_tokens == 759
    assert decisions[1].estimated_cost_usd == "0E-8"


def test_build_routing_decisions_handles_empty_rows() -> None:
    assert build_routing_decisions([]) == []


def test_build_routing_decisions_includes_policy_counts() -> None:
    decisions = build_routing_decisions(
        [
            {
                "selected_model": "paid/model",
                "final_model": "paid/model",
                "cache_hit": False,
                "request_count": 2,
                "total_fallbacks": 0,
                "compressed_requests": 0,
                "prompt_words_saved": 0,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "estimated_cost_usd": Decimal("0.01"),
                "latency_sum": 20,
                "average_quality_score": Decimal("0.65"),
                "budget_exceeded_requests": 1,
                "fallback_skipped_requests": 1,
            }
        ]
    )

    assert decisions[0].budget_exceeded_requests == 1
    assert decisions[0].fallback_skipped_requests == 1


def test_routing_decisions_endpoint_returns_route_rows(monkeypatch) -> None:
    async def fake_fetch_routing_decisions() -> list[RoutingDecisionUsage]:
        return [
            RoutingDecisionUsage(
                selected_model="cache",
                final_model="cache",
                cache_hit=True,
                request_count=3,
                request_rate=0.75,
                total_fallbacks=0,
                compressed_requests=0,
                prompt_words_saved=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost_usd="0",
                average_latency_ms=5,
                average_quality_score=1.0,
            )
        ]

    monkeypatch.setattr("app.main.fetch_routing_decisions", fake_fetch_routing_decisions)

    response = asyncio.run(routing_decisions())

    assert len(response.routes) == 1
    assert response.routes[0].selected_model == "cache"
    assert response.routes[0].cache_hit is True
    assert response.routes[0].request_rate == 0.75
