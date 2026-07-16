from app.core.cache import (
    MemorySemanticCacheIndex,
    semantic_cache_tokens,
    token_jaccard_similarity,
)


def test_semantic_cache_tokens_ignore_common_words() -> None:
    messages = [{"role": "user", "content": "Please explain the cache in one sentence."}]

    assert semantic_cache_tokens(messages) == {"explain", "cache", "one", "sentence"}


def test_token_jaccard_similarity_scores_overlap() -> None:
    first = {"hello", "phase", "4a"}
    second = {"hello", "phase", "4b"}

    assert token_jaccard_similarity(first, second) == 0.5


def test_memory_semantic_cache_index_returns_best_candidate() -> None:
    index = MemorySemanticCacheIndex()
    cached_messages = [
        {"role": "user", "content": "Say hello in one sentence for phase 4a."}
    ]
    query_messages = [
        {"role": "user", "content": "Say hello in one sentence for phase 4b."}
    ]

    index.set("cached-hash", cached_messages)
    candidate = index.find_candidate(query_messages, threshold=0.7)

    assert candidate is not None
    assert candidate.input_hash == "cached-hash"
    assert candidate.similarity_score >= 0.7
    assert "advisory" in candidate.reason


def test_memory_semantic_cache_index_respects_threshold() -> None:
    index = MemorySemanticCacheIndex()
    index.set("cached-hash", [{"role": "user", "content": "Explain routing."}])

    candidate = index.find_candidate(
        [{"role": "user", "content": "Debug a payment webhook."}],
        threshold=0.7,
    )

    assert candidate is None
