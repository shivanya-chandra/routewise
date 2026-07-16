import asyncio

from app.core.cache import request_hash
from app.main import route_preview
from app.schemas import RouteRequest


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


def test_route_preview_reports_cache_hit_without_model_call(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="preview-test",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_cost_tier="small",
    )
    cache_key = request_hash([message.model_dump() for message in payload.messages])

    monkeypatch.setattr("app.main.cache_client", FakeCache({cache_key: "Hello!"}))
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")

    response = asyncio.run(route_preview(payload))

    assert response.input_hash == cache_key
    assert response.cache_status == "hit"
    assert response.would_call_model is False
    assert response.selected_model == "cache"
    assert response.candidate_model == "ollama/llama3.2"
    assert response.prompt_compressed is False


def test_route_preview_reports_cache_miss_and_selected_model(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="preview-test",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_cost_tier="small",
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")

    response = asyncio.run(route_preview(payload))

    assert response.cache_status == "miss"
    assert response.would_call_model is True
    assert response.selected_model == "ollama/llama3.2"
    assert response.candidate_tier == "small"
    assert "cost capped at small" in response.route_reason


def test_route_preview_reports_cache_bypass_and_compression(monkeypatch) -> None:
    long_text = " ".join(f"word{i}" for i in range(30))
    payload = RouteRequest(
        user_id="preview-test",
        messages=[{"role": "user", "content": long_text}],
        max_cost_tier="small",
        bypass_cache=True,
    )

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.prompt_compression_enabled", True)
    monkeypatch.setattr("app.main.settings.prompt_compression_word_threshold", 20)
    monkeypatch.setattr("app.main.settings.prompt_compression_target_words", 12)

    response = asyncio.run(route_preview(payload))

    assert response.cache_status == "bypassed"
    assert response.would_call_model is True
    assert response.prompt_compressed is True
    assert response.original_prompt_words == 30
    assert response.compressed_prompt_words is not None
    assert response.compressed_prompt_words < response.original_prompt_words
    assert "cache bypassed" in response.route_reason
    assert "prompt compressed" in response.route_reason


def test_route_preview_reports_semantic_cache_candidate(monkeypatch) -> None:
    payload = RouteRequest(
        user_id="preview-test",
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

    response = asyncio.run(route_preview(payload))

    assert response.cache_status == "miss"
    assert response.semantic_cache_candidate is True
    assert response.semantic_cache_input_hash == "cached-hash"
    assert response.semantic_cache_score is not None
    assert response.semantic_cache_score >= 0.7
    assert "semantic cache candidate" in response.route_reason
