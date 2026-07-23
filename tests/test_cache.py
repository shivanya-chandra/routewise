import asyncio
import hashlib

from app.core.cache import (
    MemoryExactCache,
    cosine_similarity,
    deserialize_cached_prompt,
    request_hash,
    semantic_hash_embedding,
    serialize_cached_prompt,
)


def test_request_hash_is_stable_for_same_messages() -> None:
    messages = [{"role": "user", "content": "Explain polymorphism."}]

    assert request_hash(messages) == request_hash(messages)


def test_request_hash_changes_when_content_changes() -> None:
    first = [{"role": "user", "content": "Explain polymorphism."}]
    second = [{"role": "user", "content": "Explain inheritance."}]

    assert request_hash(first) != request_hash(second)


def test_request_hash_includes_cache_schema_version() -> None:
    messages = [{"role": "user", "content": "Explain polymorphism."}]
    legacy_normalized = '[{"content":"Explain polymorphism.","role":"user"}]'

    assert request_hash(messages) != hashlib.sha256(
        legacy_normalized.encode("utf-8")
    ).hexdigest()


def test_cached_prompt_serialization_round_trips() -> None:
    messages = [{"role": "user", "content": "Say hello."}]

    assert deserialize_cached_prompt(serialize_cached_prompt(messages)) == messages


def test_cached_prompt_deserialization_rejects_invalid_shapes() -> None:
    assert deserialize_cached_prompt("not-json") is None
    assert deserialize_cached_prompt('{"role":"user"}') is None


def test_hash_embeddings_score_related_text_above_unrelated_text() -> None:
    greeting = semantic_hash_embedding(
        [{"role": "user", "content": "Summarize this routing architecture."}]
    )
    related = semantic_hash_embedding(
        [{"role": "user", "content": "Provide a summary of the routing architecture."}]
    )
    unrelated = semantic_hash_embedding(
        [{"role": "user", "content": "Write a recipe for tomato soup."}]
    )

    assert cosine_similarity(greeting, related) > cosine_similarity(greeting, unrelated)


def test_memory_cache_expires_entries(monkeypatch) -> None:
    cache = MemoryExactCache()
    monkeypatch.setattr("app.core.cache.time.time", lambda: 100.0)
    asyncio.run(cache.set("key", "answer", ttl_seconds=5))

    assert asyncio.run(cache.get("key")) == "answer"

    monkeypatch.setattr("app.core.cache.time.time", lambda: 106.0)
    assert asyncio.run(cache.get("key")) is None
