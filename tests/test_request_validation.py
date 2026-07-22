import pytest
from pydantic import ValidationError

from app.schemas import RouteRequest


def test_route_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RouteRequest(
            messages=[{"role": "user", "content": "Hello."}],
            unknown_policy="ignored-before-production-hardening",
        )


def test_route_request_limits_message_count() -> None:
    with pytest.raises(ValidationError):
        RouteRequest(
            messages=[{"role": "user", "content": str(index)} for index in range(101)]
        )


def test_route_request_limits_message_size() -> None:
    with pytest.raises(ValidationError):
        RouteRequest(
            messages=[{"role": "user", "content": "x" * 100_001}]
        )
