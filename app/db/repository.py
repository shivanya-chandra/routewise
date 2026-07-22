from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.core.cache import serialize_cached_prompt
from app.core.providers import provider_from_model_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _load_models():
    from app.db.models import LLMCall, LLMRequest

    return LLMCall, LLMRequest


@dataclass(frozen=True)
class RouteRequestLog:
    id: uuid.UUID
    user_id: str | None
    input_hash: str
    selected_model: str
    final_model: str
    route_reason: str
    cache_hit: bool
    request_status: str = "success"
    cache_bypassed: bool = False
    semantic_cache_hit: bool = False
    semantic_cache_input_hash: str | None = None
    semantic_cache_score: Decimal | None = None
    semantic_cache_method: str | None = None
    routing_policy: str = "balanced"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None
    preflight_estimated_prompt_tokens: int | None = None
    preflight_estimated_completion_tokens: int | None = None
    preflight_estimated_total_tokens: int | None = None
    preflight_estimated_cost_usd: Decimal | None = None
    max_estimated_cost_usd: Decimal | None = None
    budget_status: str | None = None
    budget_exceeded: bool = False
    latency_ms: int | None = None
    quality_score: Decimal | None = None
    quality_label: str | None = None
    quality_reason: str | None = None
    fallback_count: int = 0
    fallback_skipped: bool = False
    fallback_skip_reason: str | None = None
    prompt_compressed: bool = False
    original_prompt_words: int | None = None
    compressed_prompt_words: int | None = None
    compression_ratio: Decimal | None = None


@dataclass(frozen=True)
class ModelCallLog:
    request_id: uuid.UUID
    model: str
    provider: str | None
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    estimated_cost_usd: Decimal | None
    latency_ms: int | None
    error_message: str | None = None


@dataclass(frozen=True)
class CacheEntryLog:
    input_hash: str
    prompt: str
    response: str
    model: str
    quality_score: Decimal | None = None


def cache_entry_from_messages(
    input_hash: str,
    messages: list[dict[str, str]],
    response: str,
    model: str,
    quality_score: Decimal | None = None,
) -> CacheEntryLog:
    return CacheEntryLog(
        input_hash=input_hash,
        prompt=serialize_cached_prompt(messages),
        response=response,
        model=model,
        quality_score=quality_score,
    )


def decimal_from_float(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def provider_from_model(model: str) -> str | None:
    return provider_from_model_name(model)


def sum_model_call_costs(call_logs: list[ModelCallLog]) -> Decimal | None:
    costs = [call.estimated_cost_usd for call in call_logs if call.estimated_cost_usd is not None]
    if not costs:
        return None
    return sum(costs, Decimal("0"))


def sum_nullable_int(values: list[int | None]) -> int | None:
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return sum(present_values)


async def add_route_log(
    session: "AsyncSession",
    request_log: RouteRequestLog,
    call_logs: list[ModelCallLog],
) -> None:
    LLMCall, LLMRequest = _load_models()

    session.add(
        LLMRequest(
            id=request_log.id,
            user_id=request_log.user_id,
            input_hash=request_log.input_hash,
            selected_model=request_log.selected_model,
            final_model=request_log.final_model,
            route_reason=request_log.route_reason,
            request_status=request_log.request_status,
            cache_hit=request_log.cache_hit,
            cache_bypassed=request_log.cache_bypassed,
            semantic_cache_hit=request_log.semantic_cache_hit,
            semantic_cache_input_hash=request_log.semantic_cache_input_hash,
            semantic_cache_score=request_log.semantic_cache_score,
            semantic_cache_method=request_log.semantic_cache_method,
            routing_policy=request_log.routing_policy,
            prompt_tokens=request_log.prompt_tokens,
            completion_tokens=request_log.completion_tokens,
            total_tokens=request_log.total_tokens,
            estimated_cost_usd=request_log.estimated_cost_usd,
            preflight_estimated_prompt_tokens=request_log.preflight_estimated_prompt_tokens,
            preflight_estimated_completion_tokens=request_log.preflight_estimated_completion_tokens,
            preflight_estimated_total_tokens=request_log.preflight_estimated_total_tokens,
            preflight_estimated_cost_usd=request_log.preflight_estimated_cost_usd,
            max_estimated_cost_usd=request_log.max_estimated_cost_usd,
            budget_status=request_log.budget_status,
            budget_exceeded=request_log.budget_exceeded,
            latency_ms=request_log.latency_ms,
            quality_score=request_log.quality_score,
            quality_label=request_log.quality_label,
            quality_reason=request_log.quality_reason,
            fallback_count=request_log.fallback_count,
            fallback_skipped=request_log.fallback_skipped,
            fallback_skip_reason=request_log.fallback_skip_reason,
            prompt_compressed=request_log.prompt_compressed,
            original_prompt_words=request_log.original_prompt_words,
            compressed_prompt_words=request_log.compressed_prompt_words,
            compression_ratio=request_log.compression_ratio,
        )
    )
    await session.flush()

    for call_log in call_logs:
        session.add(
            LLMCall(
                id=uuid.uuid4(),
                request_id=call_log.request_id,
                model=call_log.model,
                provider=call_log.provider,
                status=call_log.status,
                prompt_tokens=call_log.prompt_tokens,
                completion_tokens=call_log.completion_tokens,
                estimated_cost_usd=call_log.estimated_cost_usd,
                latency_ms=call_log.latency_ms,
                error_message=call_log.error_message,
            )
        )


async def save_route_log(
    session_factory: "async_sessionmaker[AsyncSession]",
    request_log: RouteRequestLog,
    call_logs: list[ModelCallLog],
) -> None:
    async with session_factory() as session:
        try:
            await add_route_log(session, request_log, call_logs)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def save_cache_entry(
    session_factory: "async_sessionmaker[AsyncSession]",
    cache_entry: CacheEntryLog,
) -> None:
    async with session_factory() as session:
        try:
            await session.execute(
                text(
                    """
                    insert into cache_entries (
                        id, input_hash, prompt, response, model, quality_score, created_at
                    )
                    values (
                        :id, :input_hash, :prompt, :response, :model, :quality_score, now()
                    )
                    on conflict (input_hash) do update set
                        prompt = excluded.prompt,
                        response = excluded.response,
                        model = excluded.model,
                        quality_score = excluded.quality_score,
                        created_at = now()
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "input_hash": cache_entry.input_hash,
                    "prompt": cache_entry.prompt,
                    "response": cache_entry.response,
                    "model": cache_entry.model,
                    "quality_score": cache_entry.quality_score,
                },
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def fetch_cache_entries(
    session_factory: "async_sessionmaker[AsyncSession]",
    limit: int,
) -> list[CacheEntryLog]:
    async with session_factory() as session:
        result = await session.execute(
            text(
                """
                select input_hash, prompt, response, model, quality_score
                from cache_entries
                order by created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        )
        return [CacheEntryLog(**dict(row)) for row in result.mappings().all()]
