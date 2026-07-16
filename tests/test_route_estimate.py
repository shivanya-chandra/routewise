import asyncio

from app.core.cache import request_hash
from app.core.preflight import estimate_message_tokens, estimate_model_cost
from app.main import route_estimate
from app.schemas import RouteRequest


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


def test_estimate_message_tokens_is_stable_and_positive() -> None:
    tokens = estimate_message_tokens([{"role": "user", "content": "abcd"}])

    assert tokens == 8


def test_estimate_model_cost_uses_configured_prices() -> None:
    estimate = estimate_model_cost(
        model="paid/model",
        prompt_tokens=1000,
        completion_tokens=500,
        model_prices_json='{"paid/model": ["0.01", "0.02"]}',
    )

    assert estimate.price_source == "configured"
    assert estimate.estimated_input_cost_usd == "0.01000000"
    assert estimate.estimated_output_cost_usd == "0.01000000"
    assert estimate.estimated_total_cost_usd == "0.02000000"


def test_route_estimate_reports_cache_hit_as_zero_cost(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="estimate-test",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_cost_tier="small",
    )
    cache_key = request_hash([message.model_dump() for message in payload.messages])

    monkeypatch.setattr("app.main.cache_client", FakeCache({cache_key: "Hello!"}))
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")

    response = asyncio.run(route_estimate(payload))

    assert response.cache_status == "hit"
    assert response.would_call_model is False
    assert response.selected_model == "cache"
    assert response.price_source == "cache"
    assert response.estimated_total_tokens == 0
    assert response.estimated_total_cost_usd == "0"


def test_route_estimate_reports_local_model_zero_cost(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="estimate-test",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_cost_tier="small",
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.preflight_default_completion_tokens", 10)

    response = asyncio.run(route_estimate(payload))

    assert response.cache_status == "miss"
    assert response.would_call_model is True
    assert response.selected_model == "ollama/llama3.2"
    assert response.price_source == "built_in"
    assert response.estimated_completion_tokens == 10
    assert response.estimated_total_cost_usd == "0E-8"


def test_route_estimate_reports_configured_paid_model_cost(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="estimate-test",
        messages=[{"role": "user", "content": "Explain this architecture in detail."}],
        max_cost_tier="frontier",
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.medium_model", "paid/model")
    monkeypatch.setattr("app.main.settings.preflight_default_completion_tokens", 500)
    monkeypatch.setattr("app.main.settings.model_prices_json", '{"paid/model": ["0.01", "0.02"]}')

    response = asyncio.run(route_estimate(payload))

    assert response.selected_model == "paid/model"
    assert response.price_source == "configured"
    assert response.estimated_total_tokens > response.estimated_prompt_tokens
    assert response.estimated_total_cost_usd is not None


def test_route_estimate_reports_semantic_cache_candidate(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="estimate-test",
        messages=[
            {"role": "user", "content": "Say hello in one sentence for phase 4b."}
        ],
        max_cost_tier="small",
    )

    from app.main import semantic_cache_index

    semantic_cache_index.entries.clear()
    semantic_cache_index.set(
        "cached-hash",
        [{"role": "user", "content": "Say hello in one sentence for phase 4a."}],
    )
    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.semantic_cache_preview_enabled", True)
    monkeypatch.setattr("app.main.settings.semantic_cache_similarity_threshold", 0.7)

    response = asyncio.run(route_estimate(payload))

    assert response.cache_status == "miss"
    assert response.semantic_cache_candidate is True
    assert response.semantic_cache_input_hash == "cached-hash"
    assert response.semantic_cache_score is not None
    assert response.semantic_cache_score >= 0.7
