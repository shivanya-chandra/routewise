import asyncio
from dataclasses import dataclass

from app.core.config_diagnostics import build_config_diagnostics
from app.main import config_diagnostics


@dataclass(frozen=True)
class FakeSettings:
    small_model: str = "ollama/llama3.2"
    medium_model: str = "gpt-4o-mini"
    frontier_model: str = "gpt-4o"
    model_prices_json: str = ""
    openai_api_key: str = ""


def test_config_diagnostics_reports_missing_paid_model_setup() -> None:
    diagnostics = build_config_diagnostics(FakeSettings())
    codes = [issue.code for issue in diagnostics.issues]

    assert diagnostics.status == "needs_attention"
    assert codes.count("missing_model_price") == 2
    assert codes.count("missing_provider_api_key") == 1
    assert all(issue.severity == "warning" for issue in diagnostics.issues)


def test_config_diagnostics_is_ok_when_prices_and_api_key_are_configured() -> None:
    settings = FakeSettings(
        model_prices_json=(
            '{"gpt-4o-mini": ["0.01", "0.02"], "gpt-4o": ["0.03", "0.06"]}'
        ),
        openai_api_key="test-key",
    )

    diagnostics = build_config_diagnostics(settings)

    assert diagnostics.status == "ok"
    assert diagnostics.issues == []


def test_config_diagnostics_reports_invalid_price_json() -> None:
    diagnostics = build_config_diagnostics(FakeSettings(model_prices_json="{bad-json"))

    assert diagnostics.status == "needs_attention"
    assert diagnostics.issues[0].severity == "error"
    assert diagnostics.issues[0].code == "invalid_model_prices_json"


def test_config_diagnostics_endpoint_returns_issue_rows(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.small_model", "ollama/llama3.2")
    monkeypatch.setattr("app.main.settings.medium_model", "gpt-4o-mini")
    monkeypatch.setattr("app.main.settings.frontier_model", "gpt-4o")
    monkeypatch.setattr("app.main.settings.model_prices_json", "")
    monkeypatch.setattr("app.main.settings.openai_api_key", "")

    response = asyncio.run(config_diagnostics())

    assert response.status == "needs_attention"
    assert len(response.issues) == 3
    assert response.issues[0].code == "missing_model_price"
