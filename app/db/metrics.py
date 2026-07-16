from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db.session import async_session


@dataclass(frozen=True)
class EvalSummary:
    total_requests: int
    cache_hits: int
    cache_hit_rate: float
    compressed_requests: int
    compression_rate: float
    prompt_words_saved: int
    average_compression_ratio: float | None
    total_fallbacks: int
    successful_model_calls: int
    failed_model_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_request_latency_ms: float | None
    average_model_call_latency_ms: float | None
    cache_bypassed_requests: int = 0
    blocked_requests: int = 0
    budget_exceeded_requests: int = 0
    fallback_skipped_requests: int = 0


@dataclass(frozen=True)
class ModelUsage:
    model: str
    provider: str | None
    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_latency_ms: float | None


@dataclass(frozen=True)
class RoutingDecisionUsage:
    selected_model: str
    final_model: str
    cache_hit: bool
    request_count: int
    request_rate: float
    total_fallbacks: int
    compressed_requests: int
    prompt_words_saved: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_latency_ms: float | None
    average_quality_score: float | None
    budget_exceeded_requests: int = 0
    fallback_skipped_requests: int = 0


def decimal_to_string(value: Decimal | None) -> str:
    if value is None:
        return "0"
    return str(value)


def rate(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round(part / whole, 4)


def average(total: int | None, count: int) -> float | None:
    if total is None or count == 0:
        return None
    return round(total / count, 2)


def build_summary(request_stats: dict[str, Any], call_stats: dict[str, Any]) -> EvalSummary:
    total_requests = int(request_stats["total_requests"] or 0)
    cache_hits = int(request_stats["cache_hits"] or 0)
    compressed_requests = int(request_stats.get("compressed_requests") or 0)
    prompt_words_saved = int(request_stats.get("prompt_words_saved") or 0)
    average_compression_ratio = request_stats.get("average_compression_ratio")
    cache_bypassed_requests = int(request_stats.get("cache_bypassed_requests") or 0)
    blocked_requests = int(request_stats.get("blocked_requests") or 0)
    budget_exceeded_requests = int(request_stats.get("budget_exceeded_requests") or 0)
    fallback_skipped_requests = int(request_stats.get("fallback_skipped_requests") or 0)
    total_fallbacks = int(request_stats["total_fallbacks"] or 0)
    request_latency_sum = request_stats["request_latency_sum"]

    successful_calls = int(call_stats["successful_model_calls"] or 0)
    failed_calls = int(call_stats["failed_model_calls"] or 0)
    prompt_tokens = int(call_stats["prompt_tokens"] or 0)
    completion_tokens = int(call_stats["completion_tokens"] or 0)
    model_latency_sum = call_stats["model_latency_sum"]

    return EvalSummary(
        total_requests=total_requests,
        cache_hits=cache_hits,
        cache_hit_rate=rate(cache_hits, total_requests),
        compressed_requests=compressed_requests,
        compression_rate=rate(compressed_requests, total_requests),
        prompt_words_saved=prompt_words_saved,
        average_compression_ratio=(
            round(float(average_compression_ratio), 4)
            if average_compression_ratio is not None
            else None
        ),
        total_fallbacks=total_fallbacks,
        successful_model_calls=successful_calls,
        failed_model_calls=failed_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        estimated_cost_usd=decimal_to_string(call_stats["estimated_cost_usd"]),
        average_request_latency_ms=average(request_latency_sum, total_requests),
        average_model_call_latency_ms=average(
            model_latency_sum,
            successful_calls + failed_calls,
        ),
        cache_bypassed_requests=cache_bypassed_requests,
        blocked_requests=blocked_requests,
        budget_exceeded_requests=budget_exceeded_requests,
        fallback_skipped_requests=fallback_skipped_requests,
    )


async def fetch_eval_summary() -> EvalSummary:
    async with async_session() as session:
        request_result = await session.execute(
            text(
                """
                select
                    count(*) as total_requests,
                    coalesce(sum(case when cache_hit then 1 else 0 end), 0) as cache_hits,
                    coalesce(sum(case when cache_bypassed then 1 else 0 end), 0)
                        as cache_bypassed_requests,
                    coalesce(sum(case when request_status = 'blocked' then 1 else 0 end), 0)
                        as blocked_requests,
                    coalesce(sum(case when budget_exceeded then 1 else 0 end), 0)
                        as budget_exceeded_requests,
                    coalesce(sum(case when fallback_skipped then 1 else 0 end), 0)
                        as fallback_skipped_requests,
                    coalesce(sum(case when prompt_compressed then 1 else 0 end), 0)
                        as compressed_requests,
                    coalesce(
                        sum(
                            case
                                when prompt_compressed
                                    then original_prompt_words - compressed_prompt_words
                                else 0
                            end
                        ),
                        0
                    ) as prompt_words_saved,
                    avg(compression_ratio) filter (where prompt_compressed)
                        as average_compression_ratio,
                    coalesce(sum(fallback_count), 0) as total_fallbacks,
                    sum(latency_ms) as request_latency_sum
                from llm_requests
                """
            )
        )
        call_result = await session.execute(
            text(
                """
                select
                    coalesce(sum(case when status = 'success' then 1 else 0 end), 0)
                        as successful_model_calls,
                    coalesce(sum(case when status = 'error' then 1 else 0 end), 0)
                        as failed_model_calls,
                    coalesce(sum(prompt_tokens), 0) as prompt_tokens,
                    coalesce(sum(completion_tokens), 0) as completion_tokens,
                    coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
                    sum(latency_ms) as model_latency_sum
                from llm_calls
                """
            )
        )
        request_stats = dict(request_result.mappings().one())
        call_stats = dict(call_result.mappings().one())

    return build_summary(request_stats, call_stats)


def build_model_usage(rows: list[dict[str, Any]]) -> list[ModelUsage]:
    usage: list[ModelUsage] = []
    for row in rows:
        total_calls = int(row["total_calls"] or 0)
        successful_calls = int(row["successful_calls"] or 0)
        failed_calls = int(row["failed_calls"] or 0)
        prompt_tokens = int(row["prompt_tokens"] or 0)
        completion_tokens = int(row["completion_tokens"] or 0)

        usage.append(
            ModelUsage(
                model=row["model"],
                provider=row["provider"],
                total_calls=total_calls,
                successful_calls=successful_calls,
                failed_calls=failed_calls,
                success_rate=rate(successful_calls, total_calls),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost_usd=decimal_to_string(row["estimated_cost_usd"]),
                average_latency_ms=average(row["latency_sum"], total_calls),
            )
        )

    return usage


async def fetch_model_usage() -> list[ModelUsage]:
    async with async_session() as session:
        result = await session.execute(
            text(
                """
                select
                    model,
                    provider,
                    count(*) as total_calls,
                    coalesce(sum(case when status = 'success' then 1 else 0 end), 0)
                        as successful_calls,
                    coalesce(sum(case when status = 'error' then 1 else 0 end), 0)
                        as failed_calls,
                    coalesce(sum(prompt_tokens), 0) as prompt_tokens,
                    coalesce(sum(completion_tokens), 0) as completion_tokens,
                    coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
                    sum(latency_ms) as latency_sum
                from llm_calls
                group by model, provider
                order by total_calls desc, model asc
                """
            )
        )
        rows = [dict(row) for row in result.mappings().all()]

    return build_model_usage(rows)


def build_routing_decisions(rows: list[dict[str, Any]]) -> list[RoutingDecisionUsage]:
    total_requests = sum(int(row["request_count"] or 0) for row in rows)
    decisions: list[RoutingDecisionUsage] = []

    for row in rows:
        request_count = int(row["request_count"] or 0)
        prompt_tokens = int(row["prompt_tokens"] or 0)
        completion_tokens = int(row["completion_tokens"] or 0)
        average_quality_score = row["average_quality_score"]

        decisions.append(
            RoutingDecisionUsage(
                selected_model=row["selected_model"],
                final_model=row["final_model"],
                cache_hit=row["cache_hit"],
                request_count=request_count,
                request_rate=rate(request_count, total_requests),
                total_fallbacks=int(row["total_fallbacks"] or 0),
                compressed_requests=int(row["compressed_requests"] or 0),
                prompt_words_saved=int(row["prompt_words_saved"] or 0),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost_usd=decimal_to_string(row["estimated_cost_usd"]),
                average_latency_ms=average(row["latency_sum"], request_count),
                average_quality_score=(
                    round(float(average_quality_score), 4)
                    if average_quality_score is not None
                    else None
                ),
                budget_exceeded_requests=int(row.get("budget_exceeded_requests") or 0),
                fallback_skipped_requests=int(row.get("fallback_skipped_requests") or 0),
            )
        )

    return decisions


async def fetch_routing_decisions() -> list[RoutingDecisionUsage]:
    async with async_session() as session:
        result = await session.execute(
            text(
                """
                select
                    selected_model,
                    final_model,
                    cache_hit,
                    count(*) as request_count,
                    coalesce(sum(fallback_count), 0) as total_fallbacks,
                    coalesce(sum(case when budget_exceeded then 1 else 0 end), 0)
                        as budget_exceeded_requests,
                    coalesce(sum(case when fallback_skipped then 1 else 0 end), 0)
                        as fallback_skipped_requests,
                    coalesce(sum(case when prompt_compressed then 1 else 0 end), 0)
                        as compressed_requests,
                    coalesce(
                        sum(
                            case
                                when prompt_compressed
                                    then original_prompt_words - compressed_prompt_words
                                else 0
                            end
                        ),
                        0
                    ) as prompt_words_saved,
                    coalesce(sum(prompt_tokens), 0) as prompt_tokens,
                    coalesce(sum(completion_tokens), 0) as completion_tokens,
                    coalesce(sum(estimated_cost_usd), 0) as estimated_cost_usd,
                    sum(latency_ms) as latency_sum,
                    avg(quality_score) as average_quality_score
                from llm_requests
                group by selected_model, final_model, cache_hit
                order by request_count desc, selected_model asc, final_model asc
                """
            )
        )
        rows = [dict(row) for row in result.mappings().all()]

    return build_routing_decisions(rows)
