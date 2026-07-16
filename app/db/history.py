from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text

from app.db.session import async_session


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_request_history(
    request_rows: list[dict[str, Any]],
    call_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    calls_by_request: dict[str, list[dict[str, Any]]] = {}
    for row in call_rows:
        request_id = str(row["request_id"])
        calls_by_request.setdefault(request_id, []).append(
            {
                "id": str(row["id"]),
                "model": row["model"],
                "provider": row["provider"],
                "status": row["status"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "estimated_cost_usd": optional_string(row["estimated_cost_usd"]),
                "latency_ms": row["latency_ms"],
                "error_message": row["error_message"],
                "created_at": optional_isoformat(row["created_at"]),
            }
        )

    history: list[dict[str, Any]] = []
    for row in request_rows:
        request_id = str(row["id"])
        history.append(
            {
                "id": request_id,
                "user_id": row["user_id"],
                "input_hash": row["input_hash"],
                "selected_model": row["selected_model"],
                "final_model": row["final_model"],
                "route_reason": row["route_reason"],
                "request_status": row.get("request_status", "success"),
                "cache_hit": row["cache_hit"],
                "cache_bypassed": row.get("cache_bypassed", False),
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "estimated_cost_usd": optional_string(row["estimated_cost_usd"]),
                "preflight_estimated_prompt_tokens": row.get(
                    "preflight_estimated_prompt_tokens"
                ),
                "preflight_estimated_completion_tokens": row.get(
                    "preflight_estimated_completion_tokens"
                ),
                "preflight_estimated_total_tokens": row.get(
                    "preflight_estimated_total_tokens"
                ),
                "preflight_estimated_cost_usd": optional_string(
                    row.get("preflight_estimated_cost_usd")
                ),
                "max_estimated_cost_usd": optional_string(row.get("max_estimated_cost_usd")),
                "budget_status": row.get("budget_status"),
                "budget_exceeded": row.get("budget_exceeded", False),
                "latency_ms": row["latency_ms"],
                "quality_score": optional_string(row["quality_score"]),
                "quality_label": row.get("quality_label"),
                "quality_reason": row.get("quality_reason"),
                "fallback_count": row["fallback_count"],
                "fallback_skipped": row.get("fallback_skipped", False),
                "fallback_skip_reason": row.get("fallback_skip_reason"),
                "prompt_compressed": row.get("prompt_compressed", False),
                "original_prompt_words": row.get("original_prompt_words"),
                "compressed_prompt_words": row.get("compressed_prompt_words"),
                "compression_ratio": optional_string(row.get("compression_ratio")),
                "created_at": optional_isoformat(row["created_at"]),
                "model_calls": calls_by_request.get(request_id, []),
            }
        )

    return history


async def fetch_request_history(limit: int = 20) -> list[dict[str, Any]]:
    async with async_session() as session:
        request_result = await session.execute(
            text(
                """
                select
                    id,
                    user_id,
                    input_hash,
                    selected_model,
                    final_model,
                    route_reason,
                    request_status,
                    cache_hit,
                    cache_bypassed,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    estimated_cost_usd,
                    preflight_estimated_prompt_tokens,
                    preflight_estimated_completion_tokens,
                    preflight_estimated_total_tokens,
                    preflight_estimated_cost_usd,
                    max_estimated_cost_usd,
                    budget_status,
                    budget_exceeded,
                    latency_ms,
                    quality_score,
                    quality_label,
                    quality_reason,
                    fallback_count,
                    fallback_skipped,
                    fallback_skip_reason,
                    prompt_compressed,
                    original_prompt_words,
                    compressed_prompt_words,
                    compression_ratio,
                    created_at
                from llm_requests
                order by created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        )
        request_rows = [dict(row) for row in request_result.mappings().all()]

        request_ids = [row["id"] for row in request_rows]
        if not request_ids:
            return []

        call_statement = text(
            """
            select
                id,
                request_id,
                model,
                provider,
                status,
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
                latency_ms,
                error_message,
                created_at
            from llm_calls
            where request_id in :request_ids
            order by created_at asc
            """
        ).bindparams(bindparam("request_ids", expanding=True))
        call_result = await session.execute(call_statement, {"request_ids": request_ids})
        call_rows = [dict(row) for row in call_result.mappings().all()]

    return build_request_history(request_rows, call_rows)
