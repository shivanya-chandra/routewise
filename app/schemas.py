from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class UserProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Display name cannot be blank.")
        return cleaned


class UserProfileItem(BaseModel):
    id: str
    display_name: str
    created_at: str


class UserProfilesResponse(BaseModel):
    users: list[UserProfileItem]


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = Field(default=None, max_length=200)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    quality_target: float = Field(default=0.90, ge=0.0, le=1.0)
    max_cost_tier: Literal["small", "medium", "frontier"] = "frontier"
    bypass_cache: bool = False
    allow_semantic_cache: bool = False
    routing_policy: Literal["balanced", "cost_first", "quality_first"] = "balanced"
    max_estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    max_completion_tokens: int = Field(default=256, ge=16, le=2048)


class RouteResponse(BaseModel):
    request_id: str
    answer: str
    selected_model: str
    final_model: str
    cache_hit: bool
    cache_bypassed: bool = False
    response_cached: bool = False
    semantic_cache_hit: bool = False
    semantic_cache_input_hash: str | None = None
    semantic_cache_score: float | None = None
    semantic_cache_method: str | None = None
    fallback_count: int
    fallback_skipped: bool = False
    fallback_skip_reason: str | None = None
    route_reason: str
    routing_policy: str = "balanced"
    quality_score: float | None = None
    quality_label: str | None = None
    quality_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    finish_reason: str | None = None
    answer_truncated: bool = False
    max_completion_tokens: int | None = None
    prompt_compressed: bool = False
    original_prompt_words: int | None = None
    compressed_prompt_words: int | None = None
    compression_ratio: float | None = None


class RoutePreviewResponse(BaseModel):
    input_hash: str
    cache_status: Literal["hit", "miss", "bypassed"]
    would_call_model: bool
    selected_model: str
    candidate_model: str | None = None
    candidate_tier: str | None = None
    model_available: bool = True
    model_availability_reason: str | None = None
    route_reason: str
    semantic_cache_candidate: bool = False
    semantic_cache_input_hash: str | None = None
    semantic_cache_score: float | None = None
    semantic_cache_reason: str | None = None
    semantic_cache_method: str | None = None
    semantic_cache_reuse_eligible: bool = False
    routing_policy: str = "balanced"
    prompt_compressed: bool = False
    original_prompt_words: int | None = None
    compressed_prompt_words: int | None = None
    compression_ratio: float | None = None


class RouteEstimateResponse(BaseModel):
    input_hash: str
    cache_status: Literal["hit", "miss", "bypassed"]
    would_call_model: bool
    selected_model: str
    candidate_model: str | None = None
    candidate_tier: str | None = None
    model_available: bool = True
    model_availability_reason: str | None = None
    price_source: Literal["cache", "configured", "built_in", "local_zero", "missing"]
    original_estimated_prompt_tokens: int
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_total_tokens: int
    estimated_input_cost_usd: str | None = None
    estimated_output_cost_usd: str | None = None
    estimated_total_cost_usd: str | None = None
    max_estimated_cost_usd: float | None = None
    budget_status: Literal["not_set", "within_budget", "exceeds_budget", "unknown"]
    budget_exceeded: bool
    semantic_cache_candidate: bool = False
    semantic_cache_input_hash: str | None = None
    semantic_cache_score: float | None = None
    semantic_cache_reason: str | None = None
    semantic_cache_method: str | None = None
    semantic_cache_reuse_eligible: bool = False
    routing_policy: str = "balanced"
    prompt_compressed: bool = False
    original_prompt_words: int | None = None
    compressed_prompt_words: int | None = None
    compression_ratio: float | None = None
    estimate_note: str


class MetricsSummaryResponse(BaseModel):
    total_requests: int
    cache_hits: int
    exact_cache_hits: int = 0
    semantic_cache_hits: int = 0
    cache_hit_rate: float
    cache_bypassed_requests: int = 0
    compressed_requests: int
    compression_rate: float
    prompt_words_saved: int
    average_compression_ratio: float | None = None
    blocked_requests: int = 0
    budget_exceeded_requests: int = 0
    fallback_skipped_requests: int = 0
    total_fallbacks: int
    successful_model_calls: int
    failed_model_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_request_latency_ms: float | None = None
    average_model_call_latency_ms: float | None = None


class ModelUsageItem(BaseModel):
    model: str
    provider: str | None = None
    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_latency_ms: float | None = None


class ModelUsageResponse(BaseModel):
    models: list[ModelUsageItem]


class ModelCatalogItem(BaseModel):
    tier: Literal["small", "medium", "frontier"]
    model: str
    provider: str | None = None
    is_local: bool
    price_source: Literal["configured", "built_in", "local_zero", "missing"]
    input_price_per_1k: str | None = None
    output_price_per_1k: str | None = None
    available: bool = True
    availability_reason: str | None = None
    required_env_var: str | None = None


class ModelCatalogResponse(BaseModel):
    models: list[ModelCatalogItem]


class ConfigDiagnosticIssueItem(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    hint: str | None = None
    tier: str | None = None
    model: str | None = None


class ConfigDiagnosticsResponse(BaseModel):
    status: Literal["ok", "needs_attention"]
    issues: list[ConfigDiagnosticIssueItem]


class RoutingDecisionItem(BaseModel):
    selected_model: str
    final_model: str
    cache_hit: bool
    semantic_cache_hit: bool = False
    request_count: int
    request_rate: float
    total_fallbacks: int
    compressed_requests: int
    prompt_words_saved: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    average_latency_ms: float | None = None
    average_quality_score: float | None = None
    budget_exceeded_requests: int = 0
    fallback_skipped_requests: int = 0


class RoutingDecisionsResponse(BaseModel):
    routes: list[RoutingDecisionItem]


class ReadinessCheck(BaseModel):
    status: Literal["ok", "error", "skipped"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheck]


class ModelCallHistoryItem(BaseModel):
    id: str
    model: str
    provider: str | None = None
    status: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: str | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: str | None = None


class RequestHistoryItem(BaseModel):
    id: str
    user_id: str | None = None
    input_hash: str
    selected_model: str
    final_model: str
    route_reason: str
    request_status: str = "success"
    cache_hit: bool
    cache_bypassed: bool = False
    semantic_cache_hit: bool = False
    semantic_cache_input_hash: str | None = None
    semantic_cache_score: str | None = None
    semantic_cache_method: str | None = None
    routing_policy: str = "balanced"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: str | None = None
    preflight_estimated_prompt_tokens: int | None = None
    preflight_estimated_completion_tokens: int | None = None
    preflight_estimated_total_tokens: int | None = None
    preflight_estimated_cost_usd: str | None = None
    max_estimated_cost_usd: str | None = None
    budget_status: str | None = None
    budget_exceeded: bool = False
    latency_ms: int | None = None
    quality_score: str | None = None
    quality_label: str | None = None
    quality_reason: str | None = None
    fallback_count: int
    fallback_skipped: bool = False
    fallback_skip_reason: str | None = None
    prompt_compressed: bool = False
    original_prompt_words: int | None = None
    compressed_prompt_words: int | None = None
    compression_ratio: str | None = None
    created_at: str | None = None
    model_calls: list[ModelCallHistoryItem]


class RequestHistoryResponse(BaseModel):
    requests: list[RequestHistoryItem]


class MetricsRecommendation(BaseModel):
    severity: Literal["info", "warning"]
    code: str
    message: str


class MetricsReportResponse(BaseModel):
    generated_at: str
    summary: MetricsSummaryResponse
    models: list[ModelUsageItem]
    routes: list[RoutingDecisionItem]
    recent_requests: list[RequestHistoryItem]
    recommendations: list[MetricsRecommendation]
