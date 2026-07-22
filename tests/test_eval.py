from decimal import Decimal

from app.db.metrics import build_summary


def test_build_summary_calculates_rates_tokens_cost_and_latency() -> None:
    summary = build_summary(
        {
            "total_requests": 4,
            "cache_hits": 1,
            "semantic_cache_hits": 1,
            "cache_bypassed_requests": 1,
            "blocked_requests": 1,
            "budget_exceeded_requests": 1,
            "fallback_skipped_requests": 1,
            "compressed_requests": 2,
            "prompt_words_saved": 700,
            "average_compression_ratio": Decimal("0.5"),
            "total_fallbacks": 2,
            "request_latency_sum": 400,
        },
        {
            "successful_model_calls": 2,
            "failed_model_calls": 1,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "estimated_cost_usd": Decimal("0.0123"),
            "model_latency_sum": 300,
        },
    )

    assert summary.total_requests == 4
    assert summary.cache_hit_rate == 0.25
    assert summary.exact_cache_hits == 0
    assert summary.semantic_cache_hits == 1
    assert summary.cache_bypassed_requests == 1
    assert summary.blocked_requests == 1
    assert summary.budget_exceeded_requests == 1
    assert summary.fallback_skipped_requests == 1
    assert summary.compressed_requests == 2
    assert summary.compression_rate == 0.5
    assert summary.prompt_words_saved == 700
    assert summary.average_compression_ratio == 0.5
    assert summary.total_fallbacks == 2
    assert summary.successful_model_calls == 2
    assert summary.failed_model_calls == 1
    assert summary.total_tokens == 150
    assert summary.estimated_cost_usd == "0.0123"
    assert summary.average_request_latency_ms == 100
    assert summary.average_model_call_latency_ms == 100


def test_build_summary_handles_empty_logs() -> None:
    summary = build_summary(
        {
            "total_requests": 0,
            "cache_hits": 0,
            "total_fallbacks": 0,
            "request_latency_sum": None,
        },
        {
            "successful_model_calls": 0,
            "failed_model_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost_usd": None,
            "model_latency_sum": None,
        },
    )

    assert summary.cache_hit_rate == 0.0
    assert summary.compression_rate == 0.0
    assert summary.prompt_words_saved == 0
    assert summary.average_compression_ratio is None
    assert summary.estimated_cost_usd == "0"
    assert summary.average_request_latency_ms is None
    assert summary.average_model_call_latency_ms is None
