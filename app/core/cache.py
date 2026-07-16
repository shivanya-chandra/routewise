import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


def request_hash(messages: list[dict[str, Any]]) -> str:
    normalized = json.dumps(messages, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ExactCache(Protocol):
    async def get(self, key: str) -> str | None:
        pass

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        pass

    async def close(self) -> None:
        pass


@dataclass(frozen=True)
class SemanticCacheCandidate:
    input_hash: str
    similarity_score: float
    reason: str


def semantic_cache_tokens(messages: list[dict[str, Any]]) -> set[str]:
    text = " ".join(str(message.get("content", "")) for message in messages)
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "for",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "please",
        "the",
        "to",
        "with",
    }
    return {token for token in tokens if token not in stop_words}


def token_jaccard_similarity(first: set[str], second: set[str]) -> float:
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    return round(len(first & second) / len(first | second), 4)


@dataclass
class MemorySemanticCacheIndex:
    entries: dict[str, set[str]] = field(default_factory=dict)

    def set(self, input_hash: str, messages: list[dict[str, Any]]) -> None:
        self.entries[input_hash] = semantic_cache_tokens(messages)

    def find_candidate(
        self,
        messages: list[dict[str, Any]],
        threshold: float,
        exclude_hash: str | None = None,
    ) -> SemanticCacheCandidate | None:
        query_tokens = semantic_cache_tokens(messages)
        best_hash = None
        best_score = 0.0

        for input_hash, tokens in self.entries.items():
            if input_hash == exclude_hash:
                continue
            score = token_jaccard_similarity(query_tokens, tokens)
            if score > best_score:
                best_hash = input_hash
                best_score = score

        if best_hash is None or best_score < threshold:
            return None

        return SemanticCacheCandidate(
            input_hash=best_hash,
            similarity_score=best_score,
            reason=(
                "Similar cached prompt found by lexical token overlap; "
                "advisory only, exact cache still controls response reuse."
            ),
        )


class RedisExactCache:
    def __init__(self, redis_url: str):
        from redis.asyncio import Redis

        self.redis = Redis.from_url(redis_url)

    async def get(self, key: str) -> str | None:
        return await get_cached_response(self.redis, key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        await set_cached_response(self.redis, key, answer, ttl_seconds)

    async def close(self) -> None:
        await self.redis.aclose()


@dataclass
class MemoryExactCache:
    values: dict[str, tuple[str, float]] = field(default_factory=dict)

    async def get(self, key: str) -> str | None:
        cached = self.values.get(key)
        if cached is None:
            return None

        answer, expires_at = cached
        if expires_at <= time.time():
            self.values.pop(key, None)
            return None

        return answer

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = (answer, time.time() + ttl_seconds)

    async def close(self) -> None:
        self.values.clear()


async def get_cached_response(redis: Any, key: str) -> str | None:
    value = await redis.get(f"routewise:cache:{key}")
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def set_cached_response(redis: Any, key: str, answer: str, ttl_seconds: int) -> None:
    await redis.set(f"routewise:cache:{key}", answer, ex=ttl_seconds)
