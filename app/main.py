import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.cache import (
    ExactCache,
    MemoryExactCache,
    MemorySemanticCacheIndex,
    RedisExactCache,
    SemanticCacheCandidate,
    deserialize_cached_prompt,
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
from app.core.report import build_metrics_recommendations
from app.core.router_engine import choose_fallback_model, choose_model
from app.core.security import FixedWindowRateLimiter, api_key_is_valid, parse_cors_origins
from app.dashboard import dashboard_response
from app.db.repository import (
    CacheEntryLog,
    ModelCallLog,
    RouteRequestLog,
    cache_entry_from_messages,
    decimal_from_float,
    fetch_cache_entries,
    provider_from_model,
    save_cache_entry,
    save_route_log,
    sum_model_call_costs,
    sum_nullable_int,
)
from app.db.history import fetch_request_history
from app.db.metrics import (
    build_summary,
    fetch_eval_summary,
    fetch_model_usage,
    fetch_routing_decisions,
)
from app.schemas import (
    ConfigDiagnosticIssueItem,
    ConfigDiagnosticsResponse,
    MetricsSummaryResponse,
    MetricsRecommendation,
    MetricsReportResponse,
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
semantic_cache_index = MemorySemanticCacheIndex(
    dimensions=settings.semantic_cache_embedding_dimensions
)
route_rate_limiter = FixedWindowRateLimiter(settings.rate_limit_requests_per_minute)


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

    if settings.request_logging_enabled:
        await hydrate_cache_entries_from_db()

    try:
        yield
    finally:
        if cache_client is not None:
            await cache_client.close()
        if settings.request_logging_enabled:
            from app.db.session import close_db

            await close_db()


app = FastAPI(
    title="RouteWise LLM Routing Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = parse_cors_origins(settings.cors_allowed_origins)
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    )


@app.middleware("http")
async def request_guard(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    if request.url.path.startswith("/route"):
        provided_key = request.headers.get("X-API-Key")
        if not api_key_is_valid(settings.routewise_api_key, provided_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "A valid X-API-Key header is required."},
                headers={"X-Request-ID": request_id},
            )

        if request.url.path == "/route" and request.method == "POST":
            identity = provided_key or (request.client.host if request.client else "unknown")
            route_rate_limiter.requests_per_minute = settings.rate_limit_requests_per_minute
            decision = route_rate_limiter.check(identity)
            if not decision.allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Route request rate limit exceeded."},
                    headers={
                        "X-Request-ID": request_id,
                        "Retry-After": str(decision.retry_after_seconds or 1),
                    },
                )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return dashboard_response()


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
            result = await session.execute(
                text(
                    """
                    select
                        to_regclass('public.llm_requests') as llm_requests,
                        to_regclass('public.llm_calls') as llm_calls,
                        to_regclass('public.cache_entries') as cache_entries
                    """
                )
            )
            missing = missing_database_tables(dict(result.mappings().one()))
            if missing:
                raise RuntimeError("missing tables: " + ", ".join(missing))

    try:
        await asyncio.wait_for(probe_database(), timeout=settings.readiness_timeout_seconds)
    except Exception as exc:
        return ReadinessCheck(
            status="error",
            detail=f"Postgres check failed: {readiness_error_detail(exc)}",
        )

    return ReadinessCheck(
        status="ok",
        detail="Postgres is reachable and all RouteWise tables exist.",
    )


def missing_database_tables(table_row: dict[str, object]) -> list[str]:
    required = ("llm_requests", "llm_calls", "cache_entries")
    return [table for table in required if table_row.get(table) is None]


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


@app.get("/metrics/report", response_model=MetricsReportResponse)
async def metrics_report(limit: int = Query(default=20, ge=1, le=100)) -> MetricsReportResponse:
    if settings.request_logging_enabled:
        try:
            summary, models, routes, recent_requests = await asyncio.gather(
                fetch_eval_summary(),
                fetch_model_usage(),
                fetch_routing_decisions(),
                fetch_request_history(limit=limit),
            )
        except Exception:
            logger.exception("Failed to build metrics report")
            raise HTTPException(
                status_code=503,
                detail="Metrics report unavailable. Check Postgres and local tables.",
            )
    else:
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
        models = []
        routes = []
        recent_requests = []

    recommendations = build_metrics_recommendations(summary, models)
    return MetricsReportResponse(
        generated_at=datetime.now(UTC).isoformat(),
        summary=MetricsSummaryResponse(**asdict(summary)),
        models=[ModelUsageItem(**asdict(model)) for model in models],
        routes=[RoutingDecisionItem(**asdict(route)) for route in routes],
        recent_requests=recent_requests,
        recommendations=[
            MetricsRecommendation(**asdict(recommendation))
            for recommendation in recommendations
        ],
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
        routing_policy=payload.routing_policy,
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
            routing_policy=payload.routing_policy,
        )

    compression = compress_messages(
        messages,
        enabled=settings.prompt_compression_enabled,
        word_threshold=settings.prompt_compression_word_threshold,
        target_words=settings.prompt_compression_target_words,
    )
    route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
    route_reason = route_reason_with_compression(route_reason, compression)
    reuse_candidate, reuse_answer = await semantic_cache_reuse(
        payload,
        messages,
        cache_key,
        cache_status,
    )
    semantic_candidate = reuse_candidate
    if semantic_candidate is None and settings.semantic_cache_preview_enabled:
        semantic_candidate = find_semantic_cache_candidate(
            messages,
            cache_key,
            cache_status,
        )
    semantic_reuse_eligible = reuse_candidate is not None and reuse_answer is not None
    if semantic_candidate is not None:
        route_reason = (
            f"{route_reason}; semantic cache candidate "
            f"score={semantic_candidate.similarity_score}"
        )
    if semantic_reuse_eligible:
        route_reason = f"{route_reason}; semantic cache reuse eligible"

    return RoutePreviewResponse(
        input_hash=cache_key,
        cache_status=cache_status,
        would_call_model=not semantic_reuse_eligible,
        selected_model="semantic_cache" if semantic_reuse_eligible else decision.model,
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
        semantic_cache_method=(
            semantic_candidate.method if semantic_candidate is not None else None
        ),
        semantic_cache_reuse_eligible=semantic_reuse_eligible,
        routing_policy=payload.routing_policy,
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
        routing_policy=payload.routing_policy,
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
            routing_policy=payload.routing_policy,
            estimate_note="Exact cache hit; no model call cost is expected.",
        )

    compression = compress_messages(
        messages,
        enabled=settings.prompt_compression_enabled,
        word_threshold=settings.prompt_compression_word_threshold,
        target_words=settings.prompt_compression_target_words,
    )
    reuse_candidate, reuse_answer = await semantic_cache_reuse(
        payload,
        messages,
        cache_key,
        cache_status,
    )
    semantic_candidate = reuse_candidate
    if semantic_candidate is None and settings.semantic_cache_preview_enabled:
        semantic_candidate = find_semantic_cache_candidate(
            messages,
            cache_key,
            cache_status,
        )
    semantic_reuse_eligible = reuse_candidate is not None and reuse_answer is not None

    if semantic_reuse_eligible and semantic_candidate is not None:
        budget = check_estimated_budget("0", payload.max_estimated_cost_usd)
        return RouteEstimateResponse(
            input_hash=cache_key,
            cache_status=cache_status,
            would_call_model=False,
            selected_model="semantic_cache",
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
            semantic_cache_candidate=True,
            semantic_cache_input_hash=semantic_candidate.input_hash,
            semantic_cache_score=semantic_candidate.similarity_score,
            semantic_cache_reason=semantic_candidate.reason,
            semantic_cache_method=semantic_candidate.method,
            semantic_cache_reuse_eligible=True,
            routing_policy=payload.routing_policy,
            prompt_compressed=compression.compressed,
            original_prompt_words=compression.original_words,
            compressed_prompt_words=compression.compressed_words,
            compression_ratio=compression.compression_ratio,
            estimate_note="Semantic cache reuse is eligible; no model call cost is expected.",
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
        semantic_cache_method=(
            semantic_candidate.method if semantic_candidate is not None else None
        ),
        semantic_cache_reuse_eligible=False,
        routing_policy=payload.routing_policy,
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


def semantic_cached_quality_assessment() -> QualityAssessment:
    return QualityAssessment(
        score=1.0,
        label="semantic_cache_hit",
        reason="A high-similarity cached answer was reused with caller opt-in.",
    )


def find_semantic_cache_candidate(
    messages: list[dict[str, str]],
    cache_key: str,
    cache_status: str,
    threshold: float | None = None,
) -> SemanticCacheCandidate | None:
    if cache_status in {"hit", "bypassed"}:
        return None
    return semantic_cache_index.find_candidate(
        messages,
        threshold=(
            settings.semantic_cache_similarity_threshold
            if threshold is None
            else threshold
        ),
        exclude_hash=cache_key,
    )


async def semantic_cache_reuse(
    payload: RouteRequest,
    messages: list[dict[str, str]],
    cache_key: str,
    cache_status: str,
) -> tuple[SemanticCacheCandidate | None, str | None]:
    if not payload.allow_semantic_cache or not settings.semantic_cache_reuse_enabled:
        return None, None

    candidate = find_semantic_cache_candidate(
        messages,
        cache_key,
        cache_status,
        threshold=settings.semantic_cache_reuse_similarity_threshold,
    )
    if candidate is None or cache_client is None:
        return None, None

    return candidate, await cache_client.get(candidate.input_hash)


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


async def persist_cache_entry(
    input_hash: str,
    messages: list[dict[str, str]],
    response: str,
    model: str,
    quality_score: float | None,
) -> None:
    if not settings.request_logging_enabled:
        return

    from app.db.session import async_session

    try:
        await save_cache_entry(
            async_session,
            cache_entry_from_messages(
                input_hash=input_hash,
                messages=messages,
                response=response,
                model=model,
                quality_score=decimal_from_float(quality_score),
            ),
        )
    except Exception:
        logger.exception("Failed to persist cache entry")


async def hydrate_cache_entries(entries: list[CacheEntryLog]) -> int:
    if cache_client is None:
        return 0

    hydrated_count = 0
    for entry in entries:
        messages = deserialize_cached_prompt(entry.prompt)
        if messages is None:
            continue
        await cache_client.set(
            entry.input_hash,
            entry.response,
            ttl_seconds=settings.exact_cache_ttl_seconds,
        )
        semantic_cache_index.set(entry.input_hash, messages)
        hydrated_count += 1

    return hydrated_count


async def hydrate_cache_entries_from_db() -> None:
    from app.db.session import async_session

    try:
        entries = await fetch_cache_entries(
            async_session,
            limit=settings.semantic_cache_hydration_limit,
        )
        hydrated_count = await hydrate_cache_entries(entries)
        logger.info("Hydrated %s persisted cache entries", hydrated_count)
    except Exception:
        logger.exception("Persisted cache hydration failed; startup will continue")


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
                routing_policy=payload.routing_policy,
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
            response_cached=True,
            fallback_count=0,
            route_reason=route_reason,
            routing_policy=payload.routing_policy,
            quality_score=quality_assessment.score,
            quality_label=quality_assessment.label,
            quality_reason=quality_assessment.reason,
            estimated_cost_usd=0.0,
        )

    semantic_candidate, semantic_answer = await semantic_cache_reuse(
        payload,
        messages,
        cache_key,
        "bypassed" if payload.bypass_cache else "miss",
    )
    if semantic_candidate is not None and semantic_answer is not None:
        latency_ms = int((time.perf_counter() - start) * 1000)
        route_reason = (
            f"semantic cache hit; source={semantic_candidate.input_hash}; "
            f"score={semantic_candidate.similarity_score}; "
            f"method={semantic_candidate.method}; latency_ms={latency_ms}"
        )
        cache_budget = check_estimated_budget("0", payload.max_estimated_cost_usd)
        quality_assessment = semantic_cached_quality_assessment()
        await persist_route_log(
            RouteRequestLog(
                id=request_id_uuid,
                user_id=payload.user_id,
                input_hash=cache_key,
                selected_model="semantic_cache",
                final_model="semantic_cache",
                route_reason=route_reason,
                cache_hit=True,
                request_status="success",
                semantic_cache_hit=True,
                semantic_cache_input_hash=semantic_candidate.input_hash,
                semantic_cache_score=decimal_from_float(
                    semantic_candidate.similarity_score
                ),
                semantic_cache_method=semantic_candidate.method,
                routing_policy=payload.routing_policy,
                estimated_cost_usd=Decimal("0"),
                preflight_estimated_prompt_tokens=0,
                preflight_estimated_completion_tokens=0,
                preflight_estimated_total_tokens=0,
                preflight_estimated_cost_usd=Decimal("0"),
                max_estimated_cost_usd=decimal_from_float(
                    payload.max_estimated_cost_usd
                ),
                budget_status=cache_budget.status,
                budget_exceeded=cache_budget.exceeded,
                latency_ms=latency_ms,
                quality_score=decimal_from_float(quality_assessment.score),
                quality_label=quality_assessment.label,
                quality_reason=quality_assessment.reason,
            ),
            call_logs,
        )
        return RouteResponse(
            request_id=request_id,
            answer=semantic_answer,
            selected_model="semantic_cache",
            final_model="semantic_cache",
            cache_hit=True,
            cache_bypassed=False,
            response_cached=True,
            semantic_cache_hit=True,
            semantic_cache_input_hash=semantic_candidate.input_hash,
            semantic_cache_score=semantic_candidate.similarity_score,
            semantic_cache_method=semantic_candidate.method,
            fallback_count=0,
            route_reason=route_reason,
            routing_policy=payload.routing_policy,
            quality_score=quality_assessment.score,
            quality_label=quality_assessment.label,
            quality_reason=quality_assessment.reason,
            estimated_cost_usd=0.0,
        )

    decision = choose_model(
        payload.messages,
        settings=settings,
        max_cost_tier=payload.max_cost_tier,
        routing_policy=payload.routing_policy,
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
                routing_policy=payload.routing_policy,
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

        if quality_score < payload.quality_target:
            fallback_decision = choose_fallback_model(
                current_tier=decision.tier,
                max_cost_tier=payload.max_cost_tier,
                settings=settings,
            )
            if fallback_decision is None:
                fallback_skipped = True
                fallback_skip_reason = (
                    "fallback skipped because the current model already uses "
                    f"max_cost_tier={payload.max_cost_tier}"
                )
            else:
                fallback_model = fallback_decision.model
                fallback_cost = estimate_model_cost(
                    model=fallback_model,
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
                        "fallback skipped because estimated "
                        f"{fallback_decision.tier} cost "
                        f"{fallback_cost.estimated_total_cost_usd} exceeds "
                        f"max_estimated_cost_usd={payload.max_estimated_cost_usd}"
                    )
                else:
                    fallback_count += 1
                    try:
                        fallback_result = await call_model_with_logging(
                            request_id_uuid,
                            fallback_model,
                            model_messages,
                            call_logs,
                        )
                    except Exception as exc:
                        fallback_skipped = True
                        fallback_skip_reason = (
                            f"{fallback_decision.tier} fallback failed; "
                            f"returning first answer: {model_error_message(exc)}"
                        )
                    else:
                        final_model = fallback_model
                        result = fallback_result
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
                routing_policy=payload.routing_policy,
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

    response_cached = quality_score >= payload.quality_target
    if response_cached:
        await cache_client.set(cache_key, answer, ttl_seconds=settings.exact_cache_ttl_seconds)
        if settings.semantic_cache_preview_enabled or settings.semantic_cache_reuse_enabled:
            semantic_cache_index.set(cache_key, messages)
        await persist_cache_entry(
            input_hash=cache_key,
            messages=messages,
            response=answer,
            model=final_model,
            quality_score=quality_score,
        )

    latency_ms = int((time.perf_counter() - start) * 1000)
    route_reason = route_reason_with_cache_bypass(decision.reason, payload.bypass_cache)
    route_reason = route_reason_with_compression(route_reason, compression)
    if fallback_skip_reason is not None:
        route_reason = f"{route_reason}; {fallback_skip_reason}"
    if not response_cached:
        route_reason = (
            f"{route_reason}; response not cached because quality score "
            f"{quality_score} is below target {payload.quality_target}"
        )
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
            routing_policy=payload.routing_policy,
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
        response_cached=response_cached,
        fallback_count=fallback_count,
        fallback_skipped=fallback_skipped,
        fallback_skip_reason=fallback_skip_reason,
        route_reason=route_reason,
        routing_policy=payload.routing_policy,
        quality_score=quality_score,
        quality_label=quality_assessment.label if quality_assessment else None,
        quality_reason=quality_assessment.reason if quality_assessment else None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens_from_calls(call_logs),
        estimated_cost_usd=float(estimated_cost_usd) if estimated_cost_usd is not None else None,
        prompt_compressed=compression.compressed,
        original_prompt_words=compression.original_words,
        compressed_prompt_words=compression.compressed_words,
        compression_ratio=compression.compression_ratio,
    )
