from dataclasses import dataclass
from typing import Protocol

from app.schemas import ChatMessage


class RouterSettings(Protocol):
    small_model: str
    medium_model: str
    frontier_model: str


@dataclass(frozen=True)
class RouterDecision:
    tier: str
    model: str
    reason: str


def estimate_complexity(messages: list[ChatMessage]) -> int:
    text = "\n".join(message.content for message in messages)
    words = text.split()
    score = 0

    if len(words) > 200:
        score += 2
    elif len(words) > 80:
        score += 1

    hard_keywords = [
        "architecture",
        "complexity",
        "debug",
        "explain in detail",
        "in detail",
        "optimize",
        "production",
        "proof",
        "reason",
        "refactor",
    ]
    lower_text = text.lower()
    score += sum(1 for keyword in hard_keywords if keyword in lower_text)

    if "```" in text:
        score += 2

    return score


def choose_model(
    messages: list[ChatMessage],
    settings: RouterSettings,
    max_cost_tier: str,
) -> RouterDecision:
    score = estimate_complexity(messages)

    if max_cost_tier == "small":
        return RouterDecision(
            tier="small",
            model=settings.small_model,
            reason=f"cost capped at small; complexity score={score}",
        )

    if score <= 1:
        return RouterDecision(
            tier="small",
            model=settings.small_model,
            reason=f"low complexity score={score}",
        )

    if score <= 3 and max_cost_tier in {"medium", "frontier"}:
        return RouterDecision(
            tier="medium",
            model=settings.medium_model,
            reason=f"medium complexity score={score}",
        )

    if max_cost_tier == "medium":
        return RouterDecision(
            tier="medium",
            model=settings.medium_model,
            reason=f"cost capped at medium; complexity score={score}",
        )

    return RouterDecision(
        tier="frontier",
        model=settings.frontier_model,
        reason=f"high complexity score={score}",
    )
