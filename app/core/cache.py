import hashlib
import json
import math
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
    method: str = "hybrid"


@dataclass(frozen=True)
class SemanticCacheDocument:
    tokens: set[str]
    embedding: dict[int, float]


def serialize_cached_prompt(messages: list[dict[str, Any]]) -> str:
    return json.dumps(messages, sort_keys=True, separators=(",", ":"))


def deserialize_cached_prompt(prompt: str) -> list[dict[str, Any]] | None:
    try:
        messages = json.loads(prompt)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(messages, list):
        return None
    if not all(
        isinstance(message, dict)
        and isinstance(message.get("role"), str)
        and isinstance(message.get("content"), str)
        for message in messages
    ):
        return None
    return messages


def semantic_cache_tokens(messages: list[dict[str, Any]]) -> set[str]:
    text = " ".join(str(message.get("content", "")) for message in messages)[:16_000]
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


def semantic_hash_embedding(
    messages: list[dict[str, Any]],
    dimensions: int = 256,
) -> dict[int, float]:
    """Build a dependency-free, deterministic sparse embedding for local similarity."""
    if dimensions < 8:
        raise ValueError("semantic embedding dimensions must be at least 8")

    text = " ".join(str(message.get("content", "")) for message in messages).lower()
    normalized = " ".join(re.findall(r"[a-z0-9]+", text))[:8_000]
    features: list[tuple[str, float]] = [
        (f"word:{token}", 2.0) for token in semantic_cache_tokens(messages)
    ]
    padded = f"  {normalized}  "
    features.extend(
        (f"char:{padded[index:index + 3]}", 1.0)
        for index in range(max(0, len(padded) - 2))
    )

    vector: dict[int, float] = {}
    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest, "big") % dimensions
        sign = 1.0 if digest[0] & 1 else -1.0
        vector[bucket] = vector.get(bucket, 0.0) + sign * weight

    magnitude = math.sqrt(sum(value * value for value in vector.values()))
    if magnitude == 0:
        return {}
    return {bucket: value / magnitude for bucket, value in vector.items()}


def cosine_similarity(first: dict[int, float], second: dict[int, float]) -> float:
    if not first or not second:
        return 0.0
    if len(first) > len(second):
        first, second = second, first
    score = sum(value * second.get(bucket, 0.0) for bucket, value in first.items())
    return round(max(0.0, min(1.0, score)), 4)


def token_jaccard_similarity(first: set[str], second: set[str]) -> float:
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    return round(len(first & second) / len(first | second), 4)


@dataclass
class MemorySemanticCacheIndex:
    dimensions: int = 256
    entries: dict[str, SemanticCacheDocument] = field(default_factory=dict)

    def set(self, input_hash: str, messages: list[dict[str, Any]]) -> None:
        self.entries[input_hash] = SemanticCacheDocument(
            tokens=semantic_cache_tokens(messages),
            embedding=semantic_hash_embedding(messages, dimensions=self.dimensions),
        )

    def find_candidate(
        self,
        messages: list[dict[str, Any]],
        threshold: float,
        exclude_hash: str | None = None,
    ) -> SemanticCacheCandidate | None:
        query_tokens = semantic_cache_tokens(messages)
        query_embedding = semantic_hash_embedding(messages, dimensions=self.dimensions)
        best_hash = None
        best_score = 0.0
        best_method = "hybrid"

        for input_hash, document in self.entries.items():
            if input_hash == exclude_hash:
                continue
            lexical_score = token_jaccard_similarity(query_tokens, document.tokens)
            vector_score = cosine_similarity(query_embedding, document.embedding)
            score = max(lexical_score, vector_score)
            if score > best_score:
                best_hash = input_hash
                best_score = score
                best_method = "lexical" if lexical_score >= vector_score else "hash_embedding"

        if best_hash is None or best_score < threshold:
            return None

        return SemanticCacheCandidate(
            input_hash=best_hash,
            similarity_score=best_score,
            reason=(
                "Similar cached prompt found by local hybrid lexical/vector similarity; "
                "advisory unless semantic cache reuse is explicitly enabled."
            ),
            method=best_method,
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
