from types import SimpleNamespace

from app.core.model_availability import model_availability


def test_local_model_is_available_without_provider_credentials() -> None:
    availability = model_availability(
        "ollama/llama3.2",
        SimpleNamespace(openai_api_key=""),
    )

    assert availability.available is True
    assert availability.reason is None
    assert availability.required_env_var is None


def test_openai_model_explains_missing_api_key() -> None:
    availability = model_availability(
        "gpt-4o-mini",
        SimpleNamespace(openai_api_key=""),
    )

    assert availability.available is False
    assert availability.required_env_var == "OPENAI_API_KEY"
    assert "OPENAI_API_KEY is not configured" in (availability.reason or "")


def test_openai_model_is_available_when_api_key_is_configured() -> None:
    availability = model_availability(
        "gpt-4o",
        SimpleNamespace(openai_api_key="test-key"),
    )

    assert availability.available is True
    assert availability.required_env_var == "OPENAI_API_KEY"
