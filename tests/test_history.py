import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.db.history import build_request_history
from app.main import request_history


def test_build_request_history_nests_model_calls() -> None:
    request_id = UUID("11111111-1111-1111-1111-111111111111")
    call_id = UUID("22222222-2222-2222-2222-222222222222")
    created_at = datetime(2026, 7, 13, 8, 30, 0)

    history = build_request_history(
        [
            {
                "id": request_id,
                "user_id": "test-user",
                "input_hash": "abc123",
                "selected_model": "ollama/llama3.2",
                "final_model": "ollama/llama3.2",
                "route_reason": "cost capped at small",
                "request_status": "success",
                "cache_hit": False,
                "cache_bypassed": True,
                "prompt_tokens": 31,
                "completion_tokens": 3,
                "total_tokens": 34,
                "estimated_cost_usd": Decimal("0.00000000"),
                "preflight_estimated_prompt_tokens": 40,
                "preflight_estimated_completion_tokens": 256,
                "preflight_estimated_total_tokens": 296,
                "preflight_estimated_cost_usd": Decimal("0.00000000"),
                "max_estimated_cost_usd": Decimal("0"),
                "budget_status": "within_budget",
                "budget_exceeded": False,
                "latency_ms": 1158,
                "quality_score": Decimal("0.65"),
                "quality_label": "short",
                "quality_reason": "Answer is concise.",
                "fallback_count": 0,
                "fallback_skipped": True,
                "fallback_skip_reason": "fallback skipped in test",
                "prompt_compressed": True,
                "original_prompt_words": 700,
                "compressed_prompt_words": 350,
                "compression_ratio": Decimal("0.5"),
                "created_at": created_at,
            }
        ],
        [
            {
                "id": call_id,
                "request_id": request_id,
                "model": "ollama/llama3.2",
                "provider": "ollama",
                "status": "success",
                "prompt_tokens": 31,
                "completion_tokens": 3,
                "estimated_cost_usd": Decimal("0.00000000"),
                "latency_ms": 1136,
                "error_message": None,
                "created_at": created_at,
            }
        ],
    )

    assert history[0]["id"] == str(request_id)
    assert history[0]["request_status"] == "success"
    assert history[0]["cache_bypassed"] is True
    assert history[0]["estimated_cost_usd"] == "0E-8"
    assert history[0]["preflight_estimated_total_tokens"] == 296
    assert history[0]["preflight_estimated_cost_usd"] == "0E-8"
    assert history[0]["max_estimated_cost_usd"] == "0"
    assert history[0]["budget_status"] == "within_budget"
    assert history[0]["fallback_skipped"] is True
    assert history[0]["fallback_skip_reason"] == "fallback skipped in test"
    assert history[0]["quality_score"] == "0.65"
    assert history[0]["quality_label"] == "short"
    assert history[0]["quality_reason"] == "Answer is concise."
    assert history[0]["prompt_compressed"] is True
    assert history[0]["original_prompt_words"] == 700
    assert history[0]["compressed_prompt_words"] == 350
    assert history[0]["compression_ratio"] == "0.5"
    assert history[0]["created_at"] == "2026-07-13T08:30:00"
    assert history[0]["model_calls"][0]["id"] == str(call_id)
    assert history[0]["model_calls"][0]["status"] == "success"


def test_build_request_history_handles_cache_hits_without_model_calls() -> None:
    request_id = UUID("33333333-3333-3333-3333-333333333333")

    history = build_request_history(
        [
            {
                "id": request_id,
                "user_id": "test-user",
                "input_hash": "def456",
                "selected_model": "cache",
                "final_model": "cache",
                "route_reason": "exact cache hit",
                "cache_hit": True,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": Decimal("0"),
                "latency_ms": 5,
                "quality_score": Decimal("1.0"),
                "quality_label": "cache_hit",
                "quality_reason": "Exact cached answer reused.",
                "fallback_count": 0,
                "created_at": None,
            }
        ],
        [],
    )

    assert history[0]["selected_model"] == "cache"
    assert history[0]["cache_hit"] is True
    assert history[0]["prompt_compressed"] is False
    assert history[0]["estimated_cost_usd"] == "0"
    assert history[0]["model_calls"] == []


def test_request_history_endpoint_returns_recent_requests(monkeypatch) -> None:
    async def fake_fetch_request_history(limit: int) -> list[dict]:
        assert limit == 5
        return [
            {
                "id": "request-1",
                "user_id": "test-user",
                "input_hash": "abc123",
                "selected_model": "cache",
                "final_model": "cache",
                "route_reason": "exact cache hit",
                "cache_hit": True,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": "0",
                "latency_ms": 5,
                "quality_score": "1.0",
                "quality_label": "cache_hit",
                "quality_reason": "Exact cached answer reused.",
                "fallback_count": 0,
                "created_at": None,
                "model_calls": [],
            }
        ]

    monkeypatch.setattr("app.main.fetch_request_history", fake_fetch_request_history)

    response = asyncio.run(request_history(limit=5))

    assert len(response.requests) == 1
    assert response.requests[0].id == "request-1"
    assert response.requests[0].cache_hit is True
    assert response.requests[0].quality_label == "cache_hit"
    assert response.requests[0].model_calls == []
