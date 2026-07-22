from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.model_catalog import CatalogModel, build_model_catalog
from app.core.providers import required_env_var_for_provider


Severity = Literal["info", "warning", "error"]


class DiagnosticSettings(Protocol):
    small_model: str
    medium_model: str
    frontier_model: str
    model_prices_json: str
    openai_api_key: str


@dataclass(frozen=True)
class ConfigDiagnosticIssue:
    severity: Severity
    code: str
    message: str
    hint: str | None = None
    tier: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class ConfigDiagnostics:
    status: str
    issues: list[ConfigDiagnosticIssue]


def status_from_issues(issues: list[ConfigDiagnosticIssue]) -> str:
    if any(issue.severity in {"warning", "error"} for issue in issues):
        return "needs_attention"
    return "ok"


def provider_env_value(settings: DiagnosticSettings, env_var: str) -> str:
    if env_var == "OPENAI_API_KEY":
        return settings.openai_api_key
    return ""


def add_price_issues(issues: list[ConfigDiagnosticIssue], catalog: list[CatalogModel]) -> None:
    for model in catalog:
        if model.is_local or model.price_source != "missing":
            continue

        issues.append(
            ConfigDiagnosticIssue(
                severity="warning",
                code="missing_model_price",
                message=f"{model.tier} model {model.model} has no price configuration.",
                hint=(
                    "Add this model to MODEL_PRICES_JSON so RouteWise can estimate "
                    "cost for successful calls."
                ),
                tier=model.tier,
                model=model.model,
            )
        )


def add_provider_issues(
    issues: list[ConfigDiagnosticIssue],
    catalog: list[CatalogModel],
    settings: DiagnosticSettings,
) -> None:
    checked_env_vars: set[str] = set()

    for model in catalog:
        if model.is_local:
            continue

        if model.provider is None:
            issues.append(
                ConfigDiagnosticIssue(
                    severity="warning",
                    code="unknown_provider",
                    message=f"{model.tier} model {model.model} does not expose a known provider.",
                    hint=(
                        "Use a provider-prefixed model name or add provider inference "
                        "before relying on provider-specific diagnostics."
                    ),
                    tier=model.tier,
                    model=model.model,
                )
            )
            continue

        env_var = required_env_var_for_provider(model.provider)
        if env_var is None or env_var in checked_env_vars:
            continue

        checked_env_vars.add(env_var)
        if not provider_env_value(settings, env_var):
            issues.append(
                ConfigDiagnosticIssue(
                    severity="warning",
                    code="missing_provider_api_key",
                    message=f"{model.provider} models are configured, but {env_var} is not set.",
                    hint=f"Set {env_var} before routing live requests to {model.provider} models.",
                )
            )


def add_duplicate_model_issues(
    issues: list[ConfigDiagnosticIssue],
    catalog: list[CatalogModel],
) -> None:
    tiers_by_model: dict[str, list[str]] = {}
    for model in catalog:
        tiers_by_model.setdefault(model.model, []).append(model.tier)

    for model_name, tiers in tiers_by_model.items():
        if len(tiers) <= 1:
            continue

        issues.append(
            ConfigDiagnosticIssue(
                severity="info",
                code="duplicate_model_tiers",
                message=f"{model_name} is configured for multiple tiers: {', '.join(tiers)}.",
                hint="This can be fine for local development, but production tiers usually differ.",
                model=model_name,
            )
        )


def add_runtime_issues(
    issues: list[ConfigDiagnosticIssue],
    settings: DiagnosticSettings,
) -> None:
    environment = str(getattr(settings, "app_environment", "development")).lower()
    if environment != "production":
        return

    if not getattr(settings, "routewise_api_key", ""):
        issues.append(
            ConfigDiagnosticIssue(
                severity="warning",
                code="missing_routewise_api_key",
                message="Production mode is enabled without ROUTEWISE_API_KEY.",
                hint="Set ROUTEWISE_API_KEY to protect model-routing endpoints.",
            )
        )
    if getattr(settings, "cache_backend", "memory") == "memory":
        issues.append(
            ConfigDiagnosticIssue(
                severity="warning",
                code="in_memory_production_cache",
                message="Production mode is using an in-memory exact cache.",
                hint="Set CACHE_BACKEND=redis for shared, restart-safe cache behavior.",
            )
        )
    if not getattr(settings, "request_logging_enabled", False):
        issues.append(
            ConfigDiagnosticIssue(
                severity="warning",
                code="production_logging_disabled",
                message="Production mode has request logging disabled.",
                hint="Enable REQUEST_LOGGING_ENABLED for audit history and metrics.",
            )
        )


def build_config_diagnostics(settings: DiagnosticSettings) -> ConfigDiagnostics:
    issues: list[ConfigDiagnosticIssue] = []

    try:
        catalog = build_model_catalog(settings)
    except Exception as exc:
        issues.append(
            ConfigDiagnosticIssue(
                severity="error",
                code="invalid_model_prices_json",
                message=f"MODEL_PRICES_JSON could not be parsed: {str(exc) or exc.__class__.__name__}.",
                hint="Set MODEL_PRICES_JSON to a JSON object such as {\"model\": [\"0.01\", \"0.02\"]}.",
            )
        )
        return ConfigDiagnostics(status=status_from_issues(issues), issues=issues)

    add_price_issues(issues, catalog)
    add_provider_issues(issues, catalog, settings)
    add_duplicate_model_issues(issues, catalog)
    add_runtime_issues(issues, settings)

    return ConfigDiagnostics(status=status_from_issues(issues), issues=issues)
