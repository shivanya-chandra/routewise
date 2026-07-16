import asyncio

from app.db.metrics import EvalSummary
from app.main import metrics_summary


def test_metrics_summary_endpoint_returns_eval_summary(monkeypatch) -> None:
    async def fake_fetch_eval_summary() -> EvalSummary:
        return EvalSummary(
            total_requests=8,
            cache_hits=3,
            cache_hit_rate=0.375,
            compressed_requests=1,
            compression_rate=0.125,
            prompt_words_saved=350,
            average_compression_ratio=0.5,
            total_fallbacks=0,
            successful_model_calls=3,
            failed_model_calls=2,
            prompt_tokens=93,
            completion_tokens=9,
            total_tokens=102,
            estimated_cost_usd="0E-8",
            average_request_latency_ms=6057.25,
            average_model_call_latency_ms=9655.0,
        )

    monkeypatch.setattr("app.main.fetch_eval_summary", fake_fetch_eval_summary)

    response = asyncio.run(metrics_summary())

    assert response.total_requests == 8
    assert response.cache_hits == 3
    assert response.cache_hit_rate == 0.375
    assert response.compressed_requests == 1
    assert response.compression_rate == 0.125
    assert response.prompt_words_saved == 350
    assert response.average_compression_ratio == 0.5
    assert response.successful_model_calls == 3
    assert response.failed_model_calls == 2
    assert response.total_tokens == 102
    assert response.estimated_cost_usd == "0E-8"
