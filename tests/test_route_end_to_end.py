import asyncio
import uuid

import pytest
from fastapi import HTTPException

from app.core.model_client import ModelResult
from app.db.repository import ModelCallLog
from app.main import route_request, semantic_cache_index
from app.schemas import RouteRequest


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


def payload(**overrides) -> RouteRequest:
    values = {
        "user_id": "e2e-test",
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "quality_target": 0.9,
        "max_cost_tier": "frontier",
        "bypass_cache": True,
    }
    values.update(overrides)
    return RouteRequest(**values)


def append_success(call_logs, request_id: uuid.UUID, model: str, result: ModelResult) -> None:
    call_logs.append(
        ModelCallLog(
            request_id=request_id,
            model=model,
            provider="test",
            status="success",
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=None,
            latency_ms=1,
        )
    )


def test_weak_answer_falls_back_and_aggregates_usage(monkeypatch) -> None:
    answers = [
        ModelResult("Too short.", 10, 2, 12, {}),
        ModelResult(
            "This complete fallback answer contains enough useful detail to satisfy the quality target, explain the result clearly, and finish the routing request successfully for the user.",
            12,
            18,
            30,
            {},
        ),
    ]
    called_models: list[str] = []

    async def fake_call(request_id, model, messages, call_logs):
        called_models.append(model)
        result = answers.pop(0)
        append_success(call_logs, request_id, model, result)
        return result

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_call)
    semantic_cache_index.entries.clear()

    response = asyncio.run(route_request(payload()))

    assert called_models == ["ollama/llama3.2", "gpt-4o"]
    assert response.final_model == "gpt-4o"
    assert response.fallback_count == 1
    assert response.prompt_tokens == 22
    assert response.completion_tokens == 20
    assert response.total_tokens == 42
    assert response.quality_label == "complete"
    assert response.response_cached is True


def test_provider_failure_returns_502_and_records_error_status(monkeypatch) -> None:
    persisted = []

    async def fail_call(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    async def capture(request_log, call_logs):
        persisted.append(request_log)

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.call_model_with_logging", fail_call)
    monkeypatch.setattr("app.main.persist_route_log", capture)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(route_request(payload(quality_target=0)))

    assert exc_info.value.status_code == 502
    assert persisted[0].request_status == "error"


def test_failed_fallback_returns_first_answer(monkeypatch) -> None:
    call_count = 0

    async def fake_call(request_id, model, messages, call_logs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("frontier unavailable")
        result = ModelResult("Usable but short.", 5, 3, 8, {})
        append_success(call_logs, request_id, model, result)
        return result

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_call)

    response = asyncio.run(route_request(payload()))

    assert response.answer == "Usable but short."
    assert response.final_model == "ollama/llama3.2"
    assert response.fallback_count == 1
    assert response.fallback_skipped is True
    assert "fallback failed" in response.fallback_skip_reason
    assert response.response_cached is False
    assert "response not cached" in response.route_reason


def test_small_cost_cap_prevents_paid_fallback(monkeypatch) -> None:
    called_models: list[str] = []

    async def fake_call(request_id, model, messages, call_logs):
        called_models.append(model)
        result = ModelResult("Usable but short.", 5, 3, 8, {})
        append_success(call_logs, request_id, model, result)
        return result

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_call)

    response = asyncio.run(route_request(payload(max_cost_tier="small")))

    assert called_models == ["ollama/llama3.2"]
    assert response.fallback_count == 0
    assert response.fallback_skipped is True
    assert "max_cost_tier=small" in response.fallback_skip_reason
    assert response.response_cached is False


def test_quality_first_policy_is_visible_in_route_result(monkeypatch) -> None:
    called_models: list[str] = []

    async def fake_call(request_id, model, messages, call_logs):
        called_models.append(model)
        result = ModelResult("A useful response.", 5, 3, 8, {})
        append_success(call_logs, request_id, model, result)
        return result

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_call)

    response = asyncio.run(
        route_request(payload(quality_target=0, routing_policy="quality_first"))
    )

    assert called_models == ["gpt-4o-mini"]
    assert response.routing_policy == "quality_first"
    assert "routing policy=quality_first" in response.route_reason
