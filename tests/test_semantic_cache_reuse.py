import asyncio

from app.core.model_client import ModelResult
from app.main import route_preview, route_request, semantic_cache_index
from app.schemas import RouteRequest


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer

    async def close(self) -> None:
        return None


def semantic_payload(**overrides) -> RouteRequest:
    values = {
        "user_id": "semantic-test",
        "messages": [
            {"role": "user", "content": "Please say hello in one sentence for release."}
        ],
        "quality_target": 0,
        "max_cost_tier": "small",
        "allow_semantic_cache": True,
    }
    values.update(overrides)
    return RouteRequest(**values)


def seed_semantic_cache() -> FakeCache:
    semantic_cache_index.entries.clear()
    semantic_cache_index.set(
        "source-hash",
        [{"role": "user", "content": "Say hello in one sentence for release."}],
    )
    return FakeCache({"source-hash": "Hello from semantic cache!"})


def test_route_reuses_semantic_cache_only_with_opt_in(monkeypatch) -> None:
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("model should not be called for an eligible semantic hit")

    persisted = []

    async def capture_log(request_log, call_logs):
        persisted.append(request_log)

    monkeypatch.setattr("app.main.cache_client", seed_semantic_cache())
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_enabled", True)
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_similarity_threshold", 0.95)
    monkeypatch.setattr("app.main.call_model_with_logging", fail_if_called)
    monkeypatch.setattr("app.main.persist_route_log", capture_log)

    response = asyncio.run(route_request(semantic_payload()))

    assert response.selected_model == "semantic_cache"
    assert response.semantic_cache_hit is True
    assert response.semantic_cache_input_hash == "source-hash"
    assert response.answer == "Hello from semantic cache!"
    assert response.estimated_cost_usd == 0
    assert persisted[0].semantic_cache_hit is True


def test_route_calls_model_when_semantic_cache_is_not_allowed(monkeypatch) -> None:
    called_models: list[str] = []

    async def fake_model(
        request_id, model, messages, call_logs, max_completion_tokens
    ):
        called_models.append(model)
        return ModelResult("Fresh answer.", 4, 2, 6, {})

    monkeypatch.setattr("app.main.cache_client", seed_semantic_cache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_model)

    response = asyncio.run(
        route_request(semantic_payload(allow_semantic_cache=False))
    )

    assert called_models == ["ollama/llama3.2"]
    assert response.semantic_cache_hit is False


def test_cache_bypass_disables_semantic_reuse(monkeypatch) -> None:
    called_models: list[str] = []

    async def fake_model(
        request_id, model, messages, call_logs, max_completion_tokens
    ):
        called_models.append(model)
        return ModelResult("Fresh answer.", 4, 2, 6, {})

    monkeypatch.setattr("app.main.cache_client", seed_semantic_cache())
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.call_model_with_logging", fake_model)

    response = asyncio.run(route_request(semantic_payload(bypass_cache=True)))

    assert called_models == ["ollama/llama3.2"]
    assert response.cache_bypassed is True
    assert response.semantic_cache_hit is False


def test_preview_marks_eligible_semantic_reuse(monkeypatch) -> None:
    monkeypatch.setattr("app.main.cache_client", seed_semantic_cache())
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_enabled", True)
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_similarity_threshold", 0.95)

    response = asyncio.run(route_preview(semantic_payload()))

    assert response.selected_model == "semantic_cache"
    assert response.would_call_model is False
    assert response.semantic_cache_reuse_eligible is True
    assert response.semantic_cache_method in {"lexical", "hash_embedding"}


def test_reuse_still_works_when_advisory_preview_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.main.cache_client", seed_semantic_cache())
    monkeypatch.setattr("app.main.settings.semantic_cache_preview_enabled", False)
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_enabled", True)
    monkeypatch.setattr("app.main.settings.semantic_cache_reuse_similarity_threshold", 0.95)

    response = asyncio.run(route_request(semantic_payload()))

    assert response.semantic_cache_hit is True
    assert response.selected_model == "semantic_cache"
