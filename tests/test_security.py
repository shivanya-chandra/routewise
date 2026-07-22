from fastapi.testclient import TestClient

from app.core.cache import request_hash
from app.core.security import FixedWindowRateLimiter, api_key_is_valid, parse_cors_origins
from app.main import app, route_rate_limiter


class FakeCache:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.values[key] = answer


ROUTE_PAYLOAD = {
    "user_id": "security-test",
    "messages": [{"role": "user", "content": "Say hello."}],
    "quality_target": 0,
    "max_cost_tier": "small",
}


def test_api_key_validation_is_optional_and_exact() -> None:
    assert api_key_is_valid("", None) is True
    assert api_key_is_valid("secret", "secret") is True
    assert api_key_is_valid("secret", "wrong") is False
    assert api_key_is_valid("secret", None) is False


def test_parse_cors_origins_removes_empty_values() -> None:
    assert parse_cors_origins("http://one.test, ,http://two.test") == [
        "http://one.test",
        "http://two.test",
    ]


def test_fixed_window_rate_limiter_blocks_after_limit() -> None:
    limiter = FixedWindowRateLimiter(requests_per_minute=2)

    assert limiter.check("client", now=0).allowed is True
    assert limiter.check("client", now=1).allowed is True
    blocked = limiter.check("client", now=2)

    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 58
    assert limiter.check("client", now=61).allowed is True


def test_route_endpoints_require_configured_api_key(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.routewise_api_key", "test-secret")
    monkeypatch.setattr("app.main.settings.rate_limit_requests_per_minute", 0)
    monkeypatch.setattr("app.main.cache_client", FakeCache())
    client = TestClient(app)

    denied = client.post("/route/preview", json=ROUTE_PAYLOAD)
    allowed = client.post(
        "/route/preview",
        json=ROUTE_PAYLOAD,
        headers={"X-API-Key": "test-secret"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_responses_include_request_id(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "caller-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "caller-id"


def test_route_middleware_enforces_rate_limit(monkeypatch) -> None:
    messages = ROUTE_PAYLOAD["messages"]
    key = request_hash(messages)
    route_rate_limiter.clear()
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    monkeypatch.setattr("app.main.settings.rate_limit_requests_per_minute", 1)
    monkeypatch.setattr("app.main.settings.request_logging_enabled", False)
    monkeypatch.setattr("app.main.cache_client", FakeCache({key: "Hello!"}))
    client = TestClient(app)

    first = client.post("/route", json=ROUTE_PAYLOAD)
    second = client.post("/route", json=ROUTE_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
