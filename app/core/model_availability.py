from dataclasses import dataclass
from typing import Protocol

from app.core.providers import (
    provider_from_model_name,
    required_env_var_for_provider,
)


class ModelAvailabilitySettings(Protocol):
    openai_api_key: str


class ModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelAvailability:
    available: bool
    reason: str | None = None
    required_env_var: str | None = None


def model_availability(
    model: str,
    settings: ModelAvailabilitySettings,
) -> ModelAvailability:
    if model.startswith("ollama/"):
        return ModelAvailability(available=True)

    provider = provider_from_model_name(model)
    env_var = required_env_var_for_provider(provider)
    if env_var == "OPENAI_API_KEY" and not getattr(settings, "openai_api_key", ""):
        return ModelAvailability(
            available=False,
            reason=(
                f"{model} cannot be called because OPENAI_API_KEY is not configured. "
                "Add it to .env and restart RouteWise."
            ),
            required_env_var=env_var,
        )

    return ModelAvailability(available=True, required_env_var=env_var)
