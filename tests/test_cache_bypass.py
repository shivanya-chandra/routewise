from app.main import route_reason_with_cache_bypass
from app.schemas import RouteRequest


def test_route_request_does_not_bypass_cache_by_default() -> None:
    request = RouteRequest(
        messages=[{"role": "user", "content": "Say hello."}],
    )

    assert request.bypass_cache is False


def test_route_request_accepts_cache_bypass() -> None:
    request = RouteRequest(
        messages=[{"role": "user", "content": "Say hello."}],
        bypass_cache=True,
    )

    assert request.bypass_cache is True


def test_route_reason_records_cache_bypass() -> None:
    reason = route_reason_with_cache_bypass("cost capped at small", True)

    assert reason == "cost capped at small; cache bypassed"


def test_route_reason_omits_cache_bypass_when_disabled() -> None:
    reason = route_reason_with_cache_bypass("cost capped at small", False)

    assert reason == "cost capped at small"
