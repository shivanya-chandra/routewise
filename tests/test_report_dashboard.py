import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.report import build_metrics_recommendations
from app.db.metrics import EvalSummary, ModelUsage, RoutingDecisionUsage
from app.main import app, metrics_report


def summary(**overrides) -> EvalSummary:
    values = {
        "total_requests": 10,
        "cache_hits": 3,
        "cache_hit_rate": 0.3,
        "compressed_requests": 2,
        "compression_rate": 0.2,
        "prompt_words_saved": 100,
        "average_compression_ratio": 0.5,
        "total_fallbacks": 1,
        "successful_model_calls": 7,
        "failed_model_calls": 0,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
        "estimated_cost_usd": "0.01",
        "average_request_latency_ms": 1200.0,
        "average_model_call_latency_ms": 1500.0,
    }
    values.update(overrides)
    return EvalSummary(**values)


def model_usage(**overrides) -> ModelUsage:
    values = {
        "model": "ollama/llama3.2",
        "provider": "ollama",
        "total_calls": 7,
        "successful_calls": 7,
        "failed_calls": 0,
        "success_rate": 1.0,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
        "estimated_cost_usd": "0",
        "average_latency_ms": 1500.0,
    }
    values.update(overrides)
    return ModelUsage(**values)


def test_report_recommends_investigation_for_failures() -> None:
    recommendations = build_metrics_recommendations(
        summary(failed_model_calls=2),
        [model_usage(success_rate=0.7)],
    )

    codes = {item.code for item in recommendations}
    assert "model_call_failures" in codes
    assert "unreliable_models" in codes


def test_report_returns_healthy_baseline_when_no_action_is_needed() -> None:
    recommendations = build_metrics_recommendations(summary(), [model_usage()])

    assert [item.code for item in recommendations] == ["healthy_baseline"]


def test_metrics_report_combines_operational_data(monkeypatch) -> None:
    async def fake_summary():
        return summary()

    async def fake_models():
        return [model_usage()]

    async def fake_routes():
        return [
            RoutingDecisionUsage(
                selected_model="ollama/llama3.2",
                final_model="ollama/llama3.2",
                cache_hit=False,
                request_count=1,
                request_rate=1.0,
                total_fallbacks=0,
                compressed_requests=0,
                prompt_words_saved=0,
                prompt_tokens=10,
                completion_tokens=2,
                total_tokens=12,
                estimated_cost_usd=str(Decimal("0")),
                average_latency_ms=100.0,
                average_quality_score=0.92,
            )
        ]

    async def fake_history(limit):
        return []

    monkeypatch.setattr("app.main.fetch_eval_summary", fake_summary)
    monkeypatch.setattr("app.main.fetch_model_usage", fake_models)
    monkeypatch.setattr("app.main.fetch_routing_decisions", fake_routes)
    monkeypatch.setattr("app.main.fetch_request_history", fake_history)
    monkeypatch.setattr("app.main.settings.request_logging_enabled", True)

    report = asyncio.run(metrics_report(limit=5))

    assert report.summary.total_requests == 10
    assert report.models[0].model == "ollama/llama3.2"
    assert report.routes[0].request_count == 1
    assert report.generated_at.endswith("+00:00")


def test_metrics_report_returns_zero_state_when_logging_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)

    report = asyncio.run(metrics_report(limit=5))

    assert report.summary.total_requests == 0
    assert report.models == []
    assert report.routes == []
    assert report.recommendations[0].code == "no_traffic"


def test_dashboard_is_a_real_html_operations_view() -> None:
    client = TestClient(app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "RouteWise Operations" in response.text
    assert "/metrics/report" in response.text
    assert "Recent requests" in response.text


def test_root_is_the_interactive_routewise_playground() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "RouteWise Playground" in response.text
    assert 'id="user-select"' in response.text
    assert 'id="tier"' in response.text
    assert 'id="budget"' in response.text
    assert "/route/estimate" in response.text
    assert "/route" in response.text
    assert "/models/catalog" in response.text
