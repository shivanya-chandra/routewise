import asyncio

import pytest
from fastapi import HTTPException

from app.core.cache import request_hash
from app.core.model_client import ModelResult
from app.core.preflight import check_estimated_budget
from app.main import route_estimate, route_request, semantic_cache_index
from app.schemas import RouteRequest


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


def test_check_estimated_budget_reports_budget_statuses() -> None:
    assert check_estimated_budget("0.01", None).status == "not_set"
    assert check_estimated_budget(None, 0.01).status == "unknown"
    assert check_estimated_budget("0.01", 0.02).status == "within_budget"

    exceeded = check_estimated_budget("0.03", 0.02)

    assert exceeded.status == "exceeds_budget"
    assert exceeded.exceeded is True


def test_route_estimate_reports_exceeded_budget(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="budget-test",
        messages=[{"role": "user", "content": "Explain this architecture in detail."}],
        max_cost_tier="frontier",
        max_estimated_cost_usd=0.001,
        max_completion_tokens=500,
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.medium_model", "paid/model")
    monkeypatch.setattr("app.main.settings.preflight_default_completion_tokens", 500)
    monkeypatch.setattr("app.main.settings.model_prices_json", '{"paid/model": ["0.01", "0.02"]}')

    response = asyncio.run(route_estimate(payload))

    assert response.selected_model == "paid/model"
    assert response.budget_status == "exceeds_budget"
    assert response.budget_exceeded is True


def test_route_estimate_reports_unknown_budget_when_price_is_missing(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="budget-test",
        messages=[{"role": "user", "content": "Explain this architecture in detail."}],
        max_cost_tier="frontier",
        max_estimated_cost_usd=0.001,
        max_completion_tokens=500,
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.medium_model", "paid/model")
    monkeypatch.setattr("app.main.settings.model_prices_json", "")

    response = asyncio.run(route_estimate(payload))

    assert response.price_source == "missing"
    assert response.estimated_total_cost_usd is None
    assert response.budget_status == "unknown"
    assert response.budget_exceeded is False


def test_route_request_rejects_over_budget_before_model_call(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="budget-test",
        messages=[{"role": "user", "content": "Explain this architecture in detail."}],
        max_cost_tier="frontier",
        max_estimated_cost_usd=0.001,
        max_completion_tokens=500,
    )

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("model call should not run when budget is exceeded")

    persisted_logs = []

    async def fake_persist_route_log(request_log, call_logs):
        persisted_logs.append((request_log, call_logs))

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.medium_model", "paid/model")
    monkeypatch.setattr("app.main.settings.preflight_default_completion_tokens", 500)
    monkeypatch.setattr("app.main.settings.model_prices_json", '{"paid/model": ["0.01", "0.02"]}')
    monkeypatch.setattr("app.main.call_model_with_logging", fail_if_called)
    monkeypatch.setattr("app.main.persist_route_log", fake_persist_route_log)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(route_request(payload))

    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["selected_model"] == "paid/model"
    assert exc_info.value.detail["max_estimated_cost_usd"] == 0.001
    assert len(persisted_logs) == 1
    request_log, call_logs = persisted_logs[0]
    assert request_log.request_status == "blocked"
    assert request_log.budget_status == "exceeds_budget"
    assert request_log.budget_exceeded is True
    assert request_log.preflight_estimated_total_tokens is not None
    assert call_logs == []


def test_route_request_skips_over_budget_fallback(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="budget-test",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_cost_tier="frontier",
        quality_target=0.9,
        max_estimated_cost_usd=0.001,
        max_completion_tokens=500,
    )
    called_models: list[str] = []
    cache_key = request_hash([message.model_dump() for message in payload.messages])

    async def fake_call_model_with_logging(
        request_id,
        model,
        messages,
        call_logs,
        max_completion_tokens,
    ):
        called_models.append(model)
        return ModelResult(
            answer="Too short.",
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            raw={},
        )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    semantic_cache_index.entries.clear()
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.settings.semantic_cache_preview_enabled", True)
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.frontier_model", "paid/frontier")
    monkeypatch.setattr("app.main.settings.preflight_default_completion_tokens", 500)
    monkeypatch.setattr(
        "app.main.settings.model_prices_json",
        '{"paid/frontier": ["0.01", "0.02"]}',
    )
    monkeypatch.setattr("app.main.call_model_with_logging", fake_call_model_with_logging)

    response = asyncio.run(route_request(payload))

    assert called_models == ["ollama/llama3.2"]
    assert response.final_model == "ollama/llama3.2"
    assert response.fallback_count == 0
    assert response.fallback_skipped is True
    assert response.fallback_skip_reason is not None
    assert "fallback skipped" in response.route_reason
    assert cache_key not in semantic_cache_index.entries
