import asyncio

from fastapi import Response

from app.core.model_client import ollama_model_available
from app.main import readiness, readiness_status
from app.schemas import ReadinessCheck


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


def test_readiness_status_is_not_ready_when_any_check_errors() -> None:
    checks = {
        "cache": ReadinessCheck(status="ok", detail="cache works"),
        "database": ReadinessCheck(status="skipped", detail="logging disabled"),
        "model_backend": ReadinessCheck(status="error", detail="Ollama is down"),
    }

    assert readiness_status(checks) == "not_ready"


def test_ollama_model_available_accepts_latest_tag() -> None:
    assert ollama_model_available("ollama/llama3.2", ["llama3.2:latest"])


def test_readiness_endpoint_returns_ready_when_required_checks_pass(monkeypatch) -> None:
    async def fake_list_ollama_models(timeout_seconds: float | None = None) -> list[str]:
        return ["llama3.2:latest"]

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.list_ollama_models", fake_list_ollama_models)
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.readiness_timeout_seconds", 0.1)

    response = Response()

    result = asyncio.run(readiness(response))

    assert response.status_code == 200
    assert result.status == "ready"
    assert result.checks["cache"].status == "ok"
    assert result.checks["database"].status == "skipped"
    assert result.checks["model_backend"].status == "ok"


def test_readiness_endpoint_returns_503_when_model_is_missing(monkeypatch) -> None:
    async def fake_list_ollama_models(timeout_seconds: float | None = None) -> list[str]:
        return []

    monkeypatch.setattr("app.main.cache_client", FakeCache())
    monkeypatch.setattr("app.main.list_ollama_models", fake_list_ollama_models)
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.readiness_timeout_seconds", 0.1)

    response = Response()

    result = asyncio.run(readiness(response))

    assert response.status_code == 503
    assert result.status == "not_ready"
    assert result.checks["model_backend"].status == "error"
