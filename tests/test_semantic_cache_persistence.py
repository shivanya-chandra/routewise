import asyncio
from decimal import Decimal

from app.core.cache import MemoryExactCache, request_hash
from app.db.repository import CacheEntryLog, cache_entry_from_messages
from app.main import hydrate_cache_entries, semantic_cache_index


def test_cache_entry_from_messages_serializes_prompt() -> None:
    messages = [{"role": "user", "content": "Persist this answer."}]

    entry = cache_entry_from_messages(
        input_hash="hash",
        messages=messages,
        response="Persisted.",
        model="ollama/llama3.2",
        quality_score=Decimal("0.92"),
    )

    assert '"content":"Persist this answer."' in entry.prompt
    assert entry.quality_score == Decimal("0.92")


def test_hydration_seeds_exact_and_semantic_cache(monkeypatch) -> None:
    messages = [{"role": "user", "content": "Remember this route."}]
    input_hash = request_hash(messages)
    cache = MemoryExactCache()
    semantic_cache_index.entries.clear()
    monkeypatch.setattr("app.main.cache_client", cache)

    count = asyncio.run(
        hydrate_cache_entries(
            [
                CacheEntryLog(
                    input_hash=input_hash,
                    prompt='[{"content":"Remember this route.","role":"user"}]',
                    response="Remembered.",
                    model="ollama/llama3.2",
                )
            ]
        )
    )

    assert count == 1
    assert asyncio.run(cache.get(input_hash)) == "Remembered."
    assert input_hash in semantic_cache_index.entries


def test_hydration_skips_invalid_prompt(monkeypatch) -> None:
    cache = MemoryExactCache()
    monkeypatch.setattr("app.main.cache_client", cache)

    count = asyncio.run(
        hydrate_cache_entries(
            [
                CacheEntryLog(
                    input_hash="bad",
                    prompt="not-json",
                    response="Ignored.",
                    model="ollama/llama3.2",
                )
            ]
        )
    )

    assert count == 0
    assert asyncio.run(cache.get("bad")) is None


def test_hydration_skips_legacy_cache_hash(monkeypatch) -> None:
    cache = MemoryExactCache()
    messages = [{"role": "user", "content": "Do not restore a legacy entry."}]
    semantic_cache_index.entries.clear()
    monkeypatch.setattr("app.main.cache_client", cache)

    count = asyncio.run(
        hydrate_cache_entries(
            [
                CacheEntryLog(
                    input_hash="legacy-hash",
                    prompt='[{"content":"Do not restore a legacy entry.","role":"user"}]',
                    response="Potentially incomplete legacy response.",
                    model="ollama/llama3.2",
                )
            ]
        )
    )

    assert count == 0
    assert asyncio.run(cache.get("legacy-hash")) is None
    assert request_hash(messages) not in semantic_cache_index.entries
