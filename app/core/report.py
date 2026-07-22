from dataclasses import dataclass

from app.db.metrics import EvalSummary, ModelUsage


@dataclass(frozen=True)
class MetricsRecommendation:
    severity: str
    code: str
    message: str


def build_metrics_recommendations(
    summary: EvalSummary,
    models: list[ModelUsage],
) -> list[MetricsRecommendation]:
    recommendations: list[MetricsRecommendation] = []

    if summary.total_requests == 0:
        return [
            MetricsRecommendation(
                severity="info",
                code="no_traffic",
                message="No routed requests have been recorded yet.",
            )
        ]

    if summary.cache_hit_rate < 0.20:
        recommendations.append(
            MetricsRecommendation(
                severity="info",
                code="low_cache_hit_rate",
                message="Cache hit rate is below 20%; inspect repeated prompt patterns and cache TTL.",
            )
        )

    if summary.failed_model_calls > 0:
        recommendations.append(
            MetricsRecommendation(
                severity="warning",
                code="model_call_failures",
                message=(
                    f"{summary.failed_model_calls} model calls failed; inspect provider errors "
                    "and readiness before increasing traffic."
                ),
            )
        )

    if (
        summary.average_model_call_latency_ms is not None
        and summary.average_model_call_latency_ms > 10_000
    ):
        recommendations.append(
            MetricsRecommendation(
                severity="warning",
                code="high_model_latency",
                message="Average model-call latency is above 10 seconds.",
            )
        )

    unreliable_models = [model.model for model in models if model.success_rate < 0.80]
    if unreliable_models:
        recommendations.append(
            MetricsRecommendation(
                severity="warning",
                code="unreliable_models",
                message="Models below 80% success: " + ", ".join(unreliable_models) + ".",
            )
        )

    if not recommendations:
        recommendations.append(
            MetricsRecommendation(
                severity="info",
                code="healthy_baseline",
                message="Observed routing, cache, latency, and provider success metrics look healthy.",
            )
        )

    return recommendations
