import hmac
import time
from dataclasses import dataclass, field


def api_key_is_valid(configured_key: str, provided_key: str | None) -> bool:
    if not configured_key:
        return True
    if not provided_key:
        return False
    return hmac.compare_digest(configured_key, provided_key)


def parse_cors_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int | None = None


@dataclass
class FixedWindowRateLimiter:
    requests_per_minute: int
    windows: dict[str, tuple[int, float]] = field(default_factory=dict)

    def check(self, identity: str, now: float | None = None) -> RateLimitDecision:
        if self.requests_per_minute <= 0:
            return RateLimitDecision(allowed=True, remaining=0)

        current_time = time.monotonic() if now is None else now
        count, started_at = self.windows.get(identity, (0, current_time))
        elapsed = current_time - started_at
        if elapsed >= 60:
            count, started_at = 0, current_time

        if count >= self.requests_per_minute:
            retry_after = max(1, int(60 - elapsed))
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        count += 1
        self.windows[identity] = (count, started_at)
        return RateLimitDecision(
            allowed=True,
            remaining=max(0, self.requests_per_minute - count),
        )

    def clear(self) -> None:
        self.windows.clear()
