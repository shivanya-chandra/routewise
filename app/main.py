import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query, Response
from sqlalchemy import text

from app.config import settings
from app.core.cache import (
    ExactCache,
    MemoryExactCache,
    MemorySemanticCacheIndex,
    SemanticCacheCandidate,
    RedisExactCache,
    request_hash,
)
from app.core.config_diagnostics import build_config_diagnostics
from app.core.cost import estimate_cost_usd
from app.core.model_catalog import build_model_catalog
from app.core.model_client import (
    ModelResult,
    call_model,
    list_ollama_models,
    ollama_model_available,
    ollama_model_name,
)
from app.core.preflight import check_estimated_budget, estimate_message_tokens, estimate_model_cost
from app.core.prompt_compressor import CompressionResult, compress_messages
from app.core.quality import QualityAssessment, assess_answer_quality
from app.core.router_engine import choose_model
from app.db.repository import (
    ModelCallLog,
    RouteRequestLog,
    decimal_from_float,
    provider_from_model,
    save_route_log,
    sum_model_call_costs,
    sum_nullable_int,
)
from app.db.history import fetch_request_history
from app.db.metrics import fetch_eval_summary, fetch_model_usage, fetch_routing_decisions
from app.schemas import (
    ConfigDiagnosticIssueItem,
    ConfigDiagnosticsResponse,
    MetricsSummaryResponse,
    ModelCatalogItem,
    ModelCatalogResponse,
    ModelUsageItem,
    ModelUsageResponse,
    ReadinessCheck,
    ReadinessResponse,
    RequestHistoryResponse,
    RouteEstimateResponse,
    RoutePreviewResponse,
    RouteRequest,
    RouteResponse,
    RoutingDecisionItem,
    RoutingDecisionsResponse,
)


logger = logging.getLogger(__name__)
cache_client: ExactCache | None = None
semantic_cache_index = MemorySemanticCacheIndex()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache_client
    semantic_cache_index.entries.clear()
    if settings.cache_backend == "redis":
        cache_client = RedisExactCache(settings.redis_url)
    else:
        cache_client = MemoryExactCache()

    if settings.request_logging_enabled and settings.auto_create_db_tables:
        from app.db.session import init_db

        await init_db()

    try:
        yield
    finally:
        if cache_client is not None:
            await cache_client.close()
        if settings.request_logging_enabled:
            from app.db.session import close_db

            await close_db()


app = FastAPI(title="RouteWise LLM Routing Gateway", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def readiness_status(checks: dict[str, ReadinessCheck]) -> str:
    if any(check.status == "error" for check in checks.values()):
        return "not_ready"
    return "ready"


def readiness_error_detail(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:300]


async def cache_readiness_check() -> ReadinessCheck:
    if cache_client is None:
        return ReadinessCheck(
            status="error",
            detail="Cache client has not been initialized by the FastAPI lifespan.",
        )

    async def probe_cache() -> None:
        key = "readiness:probe"
        await cache_client.set(key, "ok", ttl_seconds=5)
        value = await cache_client.get(key)
        if value != "ok":
            raise RuntimeError("Cache probe value could not be read back.")

    try:
        await asyncio.wait_for(probe_cache(), timeout=settings.readiness_timeout_seconds)
    except Exception as exc:
        return ReadinessCheck(
            status="error",
            detail=f"{settings.cache_backend} cache check failed: {readiness_error_detail(exc)}",
        )

    return ReadinessCheck(
        status="ok",
        detail=f"{settings.cache_backend} cache accepted a short read/write probe.",
    )


async def database_readiness_check() -> ReadinessCheck:
    if not settings.request_logging_enabled:
        return ReadinessCheck(
            status="skipped",
            detail="Request logging is disabled, so Postgres is not required for this run.",
        )

    async def probe_database() -> None:
        from app.db.session import async_session

        async with async_session() as session:
            await session.execute(text("select 1"))

    try:
        await asyncio.wait_for(probe_database(), timeout=settings.readiness_timeout_seconds)
    except Exception as exc:
        return ReadinessCheck(
            status="error",
            detail=f"Postgres check failed: {readiness_error_detail(exc)}",
        )

    return ReadinessCheck(
        status="ok",
        detail="Postgres accepted a simple select 1 query.",
    )


async def model_backend_readiness_check() -> ReadinessCheck:
    model = settings.small_model
    ollama_model = ollama_model_name(model)
    if ollama_model is None:
        return ReadinessCheck(
            status="skipped",
            detail=f"Small model {model} is not an Ollama model, so local model readiness was not checked.",
        )

    try:
        available_models = await asyncio.wait_for(
            list_ollama_models(timeout_seconds=settings.readiness_timeout_seconds),
            timeout=settings.readiness_timeout_seconds + 1,
        )
    except Exception as exc:
        return ReadinessCheck(
            status="error",
            detail=f"Ollama check failed: {readiness_error_detail(exc)}",
        )

    if not ollama_model_available(model, available_models):
        available = ", ".join(available_models) if available_models else "none"
        return ReadinessCheck(
            status="error",
            detail=f"Ollama is reachable, but {ollama_model} is not installed. Available models: {available}.",
        )

    return ReadinessCheck(
        status="ok",
        detail=f"Ollama is reachable and {ollama_model} is installed.",
    )


@app.get("/readiness", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    checks = {
        "cache": await cache_readiness_check(),
        "database": await database_readiness_check(),
        "model_backend": await model_backend_readiness_check(),
    }
    status = readiness_status(checks)

    if status != "ready":
        response.status_code = 503

    return ReadinessResponse(status=status, checks=checks)


@app.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary() -> MetricsSummaryResponse:
    try:
        summary = await fetch_eval_summary()
    except Exception:
        logger.exception("Failed to fetch metrics summary")
        raise HTTPException(
            status_code=503,
            detail="Metrics summary unavailable. Check Postgres and local tables.",
        )

    return MetricsSummaryResponse(**asdict(summary))


@app.get("/metrics/models", response_model=ModelUsageResponse)
async def model_usage() -> ModelUsageResponse:
    try:
        models = await fetch_model_usage()
    except Exception:
        logger.exception("Failed to fetch model usage")
        raise HTTPException(
            status_code=503,
            detail="Model usage unavailable. Check Postgres and local tables.",
        )

    return ModelUsageResponse(
        models=[ModelUsageItem(**asdict(model)) for model in models],
    )


@app.get("/models/catalog", response_model=ModelCatalogResponse)
async def model_catalog() -> ModelCatalogResponse:
    try:
        models = build_model_catalog(settings)
    except Exception:
        logger.exception("Failed to build model catalog")
        raise HTTPException(
            status_code=503,
            detail="Model catalog unavailable. Check MODEL_PRICES_JSON configuration.",
        )

    return ModelCatalogResponse(
        models=[ModelCatalogItem(**asdict(model)) for model in models],
    )


@app.get("/config/diagnostics", response_model=ConfigDiagnosticsResponse)
async def config_diagnostics() -> ConfigDiagnosticsResponse:
    diagnostics = build_config_diagnostics(settings)
    return ConfigDiagnosticsResponse(
        status=diagnostics.status,
        issues=[ConfigDiagnosticIssueItem(**asdict(issue)) for issue in diagnostics.issues],
    )


@app.get("/metrics/routes", response_model=RoutingDecisionsResponse)
async def routing_decisions() -> RoutingDecisionsResponse:
    try:
        routes = await fetch_routing_decisions()
    except Exception:
        logger.exception("Failed to fetch routing decisions")
        raise HTTPException(
            status_code=503,
            detail="Routing decisions unavailable. Check Postgres and local tables.",
        )

    return RoutingDecisionsResponse(
        routes=[RoutingDecisionItem(**asdict(route)) for route in routes],
    )


@app.get("/requests", response_model=RequestHistoryResponse)
async def request_history(limit: int = Query(default=20, ge=1, le=100)) -> RequestHistoryResponse:
    try:
        requests = await fetch_request_history(limit=limit)
    except Exception:
        logger.exception("Failed to fetch request history")
        raise HTTPException(
            status_code=503,
            detail="Request history unavailable. Check Postgres and local tables.",
        )

    return RequestHistoryResponse(requests=requests)


@app.post("/route/preview", response_model=RoutePreviewResponse)
async def route_preview(payload: RouteRequest) -> RoutePreviewResponse:
    if cache_client is None:
        raise HTTPException(
            status_code=503,
            detail="Cache client is not initialized. Start the app before previewing routes.",
        )

    messages = [message.model_dump() for message in payload.messages]
    cache_key = request_hash(messages)
    cached_answer = None
    cache_status = "bypassed" if payload.bypass_cache else "miss"

    if not payload.bypass_cache:
        cached_answer = await cache_client.get(cache_key)
        if cached_answer is not None:
            cache_status = "hit"

    decision = choose_model(
        payload.messages,
        settings=settings,
        max_cost_tier=payload.max_cost_tier,
    )

    if cache_status == "hit":
        return RoutePreviewResponse(
            input_hash=cache_key,
            cache_status=cache_status,
            would_call_model=False,
            selected_model="cache",
            candidate_model=decision.model,
            candidate_tier=decision.tier,
            route_reason="exact cache hit; model call would be skipped",
        )

    compression = compress_messages(
        messages,
        enabled=settings.prompt_compression_enabled,
        word_threshold=settings.prompt_compression_word_threshold,
        target_words=settings.prompt_compression_target_words,
    )
    route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
    route_reason = route_reason_with_compression(route_reason, compression)
    semantic_candidate = find_semantic_cache_candidate(messages, cache_key, cache_status)
    if semantic_candidate is not None:
        route_reason = (
            f"{route_reason}; semantic cache candidate "
            f"score={semantic_candidate.similarity_score}"
        )

    return RoutePreviewResponse(
        input_hash=cache_key,
        cache_status=cache_status,
        would_call_model=True,
        selected_model=decision.model,
        candidate_model=decision.model,
        candidate_tier=decision.tier,
        route_reason=route_reason,
        semantic_cache_candidate=semantic_candidate is not None,
        semantic_cache_input_hash=(
            semantic_candidate.input_hash if semantic_candidate is not None else None
        ),
        semantic_cache_score=(
            semantic_candidate.similarity_score if semantic_candidate is not None else None
        ),
        semantic_cache_reason=(
            semantic_candidate.reason if semantic_candidate is not None else None
        ),
        prompt_compressed=compression.compressed,
        original_prompt_words=compression.original_words,
        compressed_prompt_words=compression.compressed_words,
        compression_ratio=compression.compression_ratio,
    )


@app.post("/route/estimate", response_model=RouteEstimateResponse)
async def route_estimate(payload: RouteRequest) -> RouteEstimateResponse:
    if cache_client is None:
        raise HTTPException(
            status_code=503,
            detail="Cache client is not initialized. Start the app before estimating routes.",
        )

    messages = [message.model_dump() for message in payload.messages]
    cache_key = request_hash(messages)
    cached_answer = None
    cache_status = "bypassed" if payload.bypass_cache else "miss"

    if not payload.bypass_cache:
        cached_answer = await cache_client.get(cache_key)
        if cached_answer is not None:
            cache_status = "hit"

    decision = choose_model(
        payload.messages,
        settings=settings,
        max_cost_tier=payload.max_cost_tier,
    )
    original_estimated_prompt_tokens = estimate_message_tokens(messages)

    if cache_status == "hit":
        budget = check_estimated_budget("0", payload.max_estimated_cost_usd)
        return RouteEstimateResponse(
            input_hash=cache_key,
            cache_status=cache_status,
            would_call_model=False,
            selected_model="cache",
            candidate_model=decision.model,
            candidate_tier=decision.tier,
            price_source="cache",
            original_estimated_prompt_tokens=original_estimated_prompt_tokens,
            estimated_prompt_tokens=0,
            estimated_completion_tokens=0,
            estimated_total_tokens=0,
            estimated_input_cost_usd="0",
            estimated_output_cost_usd="0",
            estimated_total_cost_usd="0",
            max_estimated_cost_usd=payload.max_estimated_cost_usd,
            budget_status=budget.status,
            budget_exceeded=budget.exceeded,
            estimate_note="Exact cache hit; no model call cost is expected.",
        )

    compression = compress_messages(
        messages,
        enabled=settings.prompt_compression_enabled,
        word_threshold=settings.prompt_compression_word_threshold,
        target_words=settings.prompt_compression_target_words,
    )
    estimated_prompt_tokens = estimate_message_tokens(compression.messages)
    estimated_completion_tokens = settings.preflight_default_completion_tokens
    estimated_total_tokens = estimated_prompt_tokens + estimated_completion_tokens
    cost = estimate_model_cost(
        model=decision.model,
        prompt_tokens=estimated_prompt_tokens,
        completion_tokens=estimated_completion_tokens,
        model_prices_json=settings.model_prices_json,
    )
    budget = check_estimated_budget(
        cost.estimated_total_cost_usd,
        payload.max_estimated_cost_usd,
    )
    semantic_candidate = find_semantic_cache_candidate(messages, cache_key, cache_status)

    return RouteEstimateResponse(
        input_hash=cache_key,
        cache_status=cache_status,
        would_call_model=True,
        selected_model=decision.model,
        candidate_model=decision.model,
        candidate_tier=decision.tier,
        price_source=cost.price_source,
        original_estimated_prompt_tokens=original_estimated_prompt_tokens,
        estimated_prompt_tokens=estimated_prompt_tokens,
        estimated_completion_tokens=estimated_completion_tokens,
        estimated_total_tokens=estimated_total_tokens,
        estimated_input_cost_usd=cost.estimated_input_cost_usd,
        estimated_output_cost_usd=cost.estimated_output_cost_usd,
        estimated_total_cost_usd=cost.estimated_total_cost_usd,
        max_estimated_cost_usd=payload.max_estimated_cost_usd,
        budget_status=budget.status,
        budget_exceeded=budget.exceeded,
        semantic_cache_candidate=semantic_candidate is not None,
        semantic_cache_input_hash=(
            semantic_candidate.input_hash if semantic_candidate is not None else None
        ),
        semantic_cache_score=(
            semantic_candidate.similarity_score if semantic_candidate is not None else None
        ),
        semantic_cache_reason=(
            semantic_candidate.reason if semantic_candidate is not None else None
        ),
        prompt_compressed=compression.compressed,
        original_prompt_words=compression.original_words,
        compressed_prompt_words=compression.compressed_words,
        compression_ratio=compression.compression_ratio,
        estimate_note=(
            "Heuristic preflight estimate; actual provider token usage and cost may differ."
        ),
    )


def total_tokens_from_calls(call_logs: list[ModelCallLog]) -> int | None:
    prompt_tokens = sum_nullable_int([call.prompt_tokens for call in call_logs])
    completion_tokens = sum_nullable_int([call.completion_tokens for call in call_logs])
    if prompt_tokens is None and completion_tokens is None:
        return None
    return (prompt_tokens or 0) + (completion_tokens or 0)


def decimal_from_string(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def cached_quality_assessment() -> QualityAssessment:
    return QualityAssessment(
        score=1.0,
        label="cache_hit",
        reason="Exact cached answer reused; no fresh quality assessment ran.",
    )


def find_semantic_cache_candidate(
    messages: list[dict[str, str]],
    cache_key: str,
    cache_status: str,
) -> SemanticCacheCandidate | None:
    if not settings.semantic_cache_preview_enabled:
        return None
    if cache_status in {"hit", "bypassed"}:
        return None
    return semantic_cache_index.find_candidate(
        messages,
        threshold=settings.semantic_cache_similarity_threshold,
        exclude_hash=cache_key,
    )


def route_reason_with_compression(base_reason: str, compression: CompressionResult) -> str:
    if not compression.compressed:
        return base_reason
    return f"{base_reason}; {compression.reason}"


def route_reason_with_cache_bypass(base_reason: str, bypass_cache: bool) -> str:
    if not bypass_cache:
        return base_reason
    return f"{base_reason}; cache bypassed"


async def persist_route_log(request_log: RouteRequestLog, call_logs: list[ModelCallLog]) -> None:
    if not settings.request_logging_enabled:
        return

    from app.db.session import async_session

    try:
        await save_route_log(async_session, request_log, call_logs)
    except Exception:
        logger.exception("Failed to persist route log")


def model_error_message(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return f"Model call timed out after {settings.model_call_timeout_seconds} seconds"

    message = str(exc)
    if not message:
        message = exc.__class__.__name__
    return message[:1000]


async def call_model_with_logging(
    request_id: uuid.UUID,
    model: str,
    messages: list[dict[str, str]],
    call_logs: list[ModelCallLog],
) -> ModelResult:
    call_start = time.perf_counter()

    try:
        result = await asyncio.wait_for(
            call_model(model, messages),
            timeout=settings.model_call_timeout_seconds,
        )
    except Exception as exc:
        call_logs.append(
            ModelCallLog(
                request_id=request_id,
                model=model,
                provider=provider_from_model(model),
                status="error",
                prompt_tokens=None,
                completion_tokens=None,
                estimated_cost_usd=None,
                latency_ms=int((time.perf_counter() - call_start) * 1000),
                error_message=model_error_message(exc),
            )
        )
        raise

    call_logs.append(
        ModelCallLog(
            request_id=request_id,
            model=model,
            provider=provider_from_model(model),
            status="success",
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=estimate_cost_usd(
                model,
                result.prompt_tokens,
                result.completion_tokens,
                settings.model_prices_json,
            ),
            latency_ms=int((time.perf_counter() - call_start) * 1000),
        )
    )

    return result


@app.post("/route", response_model=RouteResponse)
async def route_request(payload: RouteRequest) -> RouteResponse:
    if cache_client is None:
        raise RuntimeError("Cache client is not initialized")

    start = time.perf_counter()
    request_id_uuid = uuid.uuid4()
    request_id = str(request_id_uuid)
    messages = [message.model_dump() for message in payload.messages]
    cache_key = request_hash(messages)
    call_logs: list[ModelCallLog] = []

    cached_answer = None
    if not payload.bypass_cache:
        cached_answer = await cache_client.get(cache_key)

    if cached_answer is not None:
        latency_ms = int((time.perf_counter() - start) * 1000)
        route_reason = f"exact cache hit; latency_ms={latency_ms}"
        cache_budget = check_estimated_budget("0", payload.max_estimated_cost_usd)
        quality_assessment = cached_quality_assessment()
        await persist_route_log(
            RouteRequestLog(
                id=request_id_uuid,
                user_id=payload.user_id,
                input_hash=cache_key,
                selected_model="cache",
                final_model="cache",
                route_reason=route_reason,
                cache_hit=True,
                request_status="success",
                cache_bypassed=False,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                estimated_cost_usd=Decimal("0"),
                preflight_estimated_prompt_tokens=0,
                preflight_estimated_completion_tokens=0,
                preflight_estimated_total_tokens=0,
                preflight_estimated_cost_usd=Decimal("0"),
                max_estimated_cost_usd=decimal_from_float(payload.max_estimated_cost_usd),
                budget_status=cache_budget.status,
                budget_exceeded=cache_budget.exceeded,
                latency_ms=latency_ms,
                quality_score=decimal_from_float(quality_assessment.score),
                quality_label=quality_assessment.label,
                quality_reason=quality_assessment.reason,
                fallback_count=0,
            ),
            call_logs,
        )
        return RouteResponse(
            request_id=request_id,
            answer=cached_answer,
            selected_model="cache",
            final_model="cache",
            cache_hit=True,
            cache_bypassed=False,
            fallback_count=0,
            route_reason=route_reason,
            quality_score=quality_assessment.score,
            quality_label=quality_assessment.label,
            quality_reason=quality_assessment.reason,
            estimated_cost_usd=0.0,
        )

    decision = choose_model(
        payload.messages,
        settings=settings,
        max_cost_tier=payload.max_cost_tier,
    )

    selected_model = decision.model
    final_model = selected_model
    fallback_count = 0
    fallback_skipped = False
    fallback_skip_reason = None
    quality_assessment: QualityAssessment | None = None
    compression = compress_messages(
        messages,
        enabled=settings.prompt_compression_enabled,
        word_threshold=settings.prompt_compression_word_threshold,
        target_words=settings.prompt_compression_target_words,
    )
    model_messages = compression.messages
    estimated_prompt_tokens = estimate_message_tokens(model_messages)
    estimated_completion_tokens = settings.preflight_default_completion_tokens
    preflight_cost = estimate_model_cost(
        model=selected_model,
        prompt_tokens=estimated_prompt_tokens,
        completion_tokens=estimated_completion_tokens,
        model_prices_json=settings.model_prices_json,
    )
    budget = check_estimated_budget(
        preflight_cost.estimated_total_cost_usd,
        payload.max_estimated_cost_usd,
    )
    if budget.exceeded:
        latency_ms = int((time.perf_counter() - start) * 1000)
        route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
        route_reason = route_reason_with_compression(route_reason, compression)
        route_reason = (
            f"{route_reason}; estimated cost {preflight_cost.estimated_total_cost_usd} "
            f"exceeds max_estimated_cost_usd={payload.max_estimated_cost_usd}; "
            f"latency_ms={latency_ms}"
        )
        await persist_route_log(
            RouteRequestLog(
                id=request_id_uuid,
                user_id=payload.user_id,
                input_hash=cache_key,
                selected_model=selected_model,
                final_model=selected_model,
                route_reason=route_reason,
                cache_hit=False,
                request_status="blocked",
                cache_bypassed=payload.bypass_cache,
                preflight_estimated_prompt_tokens=estimated_prompt_tokens,
                preflight_estimated_completion_tokens=estimated_completion_tokens,
                preflight_estimated_total_tokens=estimated_prompt_tokens + estimated_completion_tokens,
                preflight_estimated_cost_usd=decimal_from_string(
                    preflight_cost.estimated_total_cost_usd
                ),
                max_estimated_cost_usd=decimal_from_float(payload.max_estimated_cost_usd),
                budget_status=budget.status,
                budget_exceeded=budget.exceeded,
                latency_ms=latency_ms,
                prompt_compressed=compression.compressed,
                original_prompt_words=compression.original_words,
                compressed_prompt_words=compression.compressed_words,
                compression_ratio=decimal_from_float(compression.compression_ratio),
            ),
            call_logs,
        )
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Estimated route cost exceeds max_estimated_cost_usd.",
                "selected_model": selected_model,
                "estimated_total_cost_usd": preflight_cost.estimated_total_cost_usd,
                "max_estimated_cost_usd": payload.max_estimated_cost_usd,
                "price_source": preflight_cost.price_source,
                "estimated_prompt_tokens": estimated_prompt_tokens,
                "estimated_completion_tokens": estimated_completion_tokens,
            },
        )

    try:
        result = await call_model_with_logging(
            request_id_uuid,
            selected_model,
            model_messages,
            call_logs,
        )
        answer = result.answer
        quality_assessment = assess_answer_quality(answer)
        quality_score = quality_assessment.score

        if quality_score < payload.quality_target and decision.tier != "frontier":
            fallback_cost = estimate_model_cost(
                model=settings.frontier_model,
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=estimated_completion_tokens,
                model_prices_json=settings.model_prices_json,
            )
            fallback_budget = check_estimated_budget(
                fallback_cost.estimated_total_cost_usd,
                payload.max_estimated_cost_usd,
            )
            if fallback_budget.exceeded:
                fallback_skipped = True
                fallback_skip_reason = (
                    "fallback skipped because estimated frontier cost "
                    f"{fallback_cost.estimated_total_cost_usd} exceeds "
                    f"max_estimated_cost_usd={payload.max_estimated_cost_usd}"
                )
            else:
                fallback_count += 1
                final_model = settings.frontier_model
                result = await call_model_with_logging(
                    request_id_uuid,
                    final_model,
                    model_messages,
                    call_logs,
                )
                answer = result.answer
                quality_assessment = assess_answer_quality(answer)
                quality_score = quality_assessment.score
    except Exception:
        latency_ms = int((time.perf_counter() - start) * 1000)
        route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
        route_reason = route_reason_with_compression(route_reason, compression)
        route_reason = f"{route_reason}; model call failed; latency_ms={latency_ms}"
        prompt_tokens = sum_nullable_int([call.prompt_tokens for call in call_logs])
        completion_tokens = sum_nullable_int([call.completion_tokens for call in call_logs])
        await persist_route_log(
            RouteRequestLog(
                id=request_id_uuid,
                user_id=payload.user_id,
                input_hash=cache_key,
                selected_model=selected_model,
                final_model=final_model,
                route_reason=route_reason,
                cache_hit=False,
                request_status="error",
                cache_bypassed=payload.bypass_cache,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens_from_calls(call_logs),
                estimated_cost_usd=sum_model_call_costs(call_logs),
                preflight_estimated_prompt_tokens=estimated_prompt_tokens,
                preflight_estimated_completion_tokens=estimated_completion_tokens,
                preflight_estimated_total_tokens=estimated_prompt_tokens
                + estimated_completion_tokens,
                preflight_estimated_cost_usd=decimal_from_string(
                    preflight_cost.estimated_total_cost_usd
                ),
                max_estimated_cost_usd=decimal_from_float(payload.max_estimated_cost_usd),
                budget_status=budget.status,
                budget_exceeded=budget.exceeded,
                latency_ms=latency_ms,
                quality_score=(
                    decimal_from_float(quality_assessment.score)
                    if quality_assessment
                    else None
                ),
                quality_label=quality_assessment.label if quality_assessment else None,
                quality_reason=quality_assessment.reason if quality_assessment else None,
                fallback_count=fallback_count,
                fallback_skipped=fallback_skipped,
                fallback_skip_reason=fallback_skip_reason,
                prompt_compressed=compression.compressed,
                original_prompt_words=compression.original_words,
                compressed_prompt_words=compression.compressed_words,
                compression_ratio=decimal_from_float(compression.compression_ratio),
            ),
            call_logs,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Model provider call failed. Check the configured model backend "
                "and the latest llm_calls.error_message row."
            ),
        )

    await cache_client.set(cache_key, answer, ttl_seconds=settings.exact_cache_ttl_seconds)
    if settings.semantic_cache_preview_enabled:
        semantic_cache_index.set(cache_key, messages)

    latency_ms = int((time.perf_counter() - start) * 1000)
    route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
    route_reason = route_reason_with_compression(route_reason, compression)
    if fallback_skip_reason is not None:
        route_reason = f"{route_reason}; {fallback_skip_reason}"
    route_reason = f"{route_reason}; latency_ms={latency_ms}"
    prompt_tokens = sum_nullable_int([call.prompt_tokens for call in call_logs])
    completion_tokens = sum_nullable_int([call.completion_tokens for call in call_logs])
    estimated_cost_usd = sum_model_call_costs(call_logs)

    await persist_route_log(
        RouteRequestLog(
            id=request_id_uuid,
            user_id=payload.user_id,
            input_hash=cache_key,
            selected_model=selected_model,
            final_model=final_model,
            route_reason=route_reason,
            cache_hit=False,
            request_status="success",
            cache_bypassed=payload.bypass_cache,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens_from_calls(call_logs),
            estimated_cost_usd=estimated_cost_usd,
            preflight_estimated_prompt_tokens=estimated_prompt_tokens,
            preflight_estimated_completion_tokens=estimated_completion_tokens,
            preflight_estimated_total_tokens=estimated_prompt_tokens + estimated_completion_tokens,
            preflight_estimated_cost_usd=decimal_from_string(
                preflight_cost.estimated_total_cost_usd
            ),
            max_estimated_cost_usd=decimal_from_float(payload.max_estimated_cost_usd),
            budget_status=budget.status,
            budget_exceeded=budget.exceeded,
            latency_ms=latency_ms,
            quality_score=decimal_from_float(quality_score),
            quality_label=quality_assessment.label if quality_assessment else None,
            quality_reason=quality_assessment.reason if quality_assessment else None,
            fallback_count=fallback_count,
            fallback_skipped=fallback_skipped,
            fallback_skip_reason=fallback_skip_reason,
            prompt_compressed=compression.compressed,
            original_prompt_words=compression.original_words,
            compressed_prompt_words=compression.compressed_words,
            compression_ratio=decimal_from_float(compression.compression_ratio),
        ),
        call_logs,
    )

    return RouteResponse(
        request_id=request_id,
        answer=answer,
        selected_model=selected_model,
        final_model=final_model,
        cache_hit=False,
        cache_bypassed=payload.bypass_cache,
        fallback_count=fallback_count,
        fallback_skipped=fallback_skipped,
        fallback_skip_reason=fallback_skip_reason,
        route_reason=route_reason,
        quality_score=quality_score,
        quality_label=quality_assessment.label if quality_assessment else None,
        quality_reason=quality_assessment.reason if quality_assessment else None,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=float(estimated_cost_usd) if estimated_cost_usd is not None else None,
        prompt_compressed=compression.compressed,
        original_prompt_words=compression.original_words,
        compressed_prompt_words=compression.compressed_words,
        compression_ratio=compression.compression_ratio,
    )
