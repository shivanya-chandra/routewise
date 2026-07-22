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


TIER_ORDER = ("small", "medium", "frontier")


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
    routing_policy: str = "balanced",
) -> RouterDecision:
    score = estimate_complexity(messages)
    base_index = 0 if score <= 1 else 1 if score <= 3 else 2
    cap_index = TIER_ORDER.index(max_cost_tier)

    if routing_policy == "cost_first":
        policy_index = max(0, base_index - 1)
    elif routing_policy == "quality_first":
        policy_index = min(2, base_index + 1)
    else:
        policy_index = base_index

    selected_index = min(policy_index, cap_index)
    tier = TIER_ORDER[selected_index]
    model = {
        "small": settings.small_model,
        "medium": settings.medium_model,
        "frontier": settings.frontier_model,
    }[tier]

    if max_cost_tier == "small" or cap_index < policy_index:
        reason = f"cost capped at {max_cost_tier}; complexity score={score}"
    else:
        complexity_label = {0: "low", 1: "medium", 2: "high"}[base_index]
        reason = f"{complexity_label} complexity score={score}"

    if routing_policy != "balanced":
        reason = f"{reason}; routing policy={routing_policy}"

    return RouterDecision(tier=tier, model=model, reason=reason)


def choose_fallback_model(
    current_tier: str,
    max_cost_tier: str,
    settings: RouterSettings,
) -> RouterDecision | None:
    current_index = TIER_ORDER.index(current_tier)
    cap_index = TIER_ORDER.index(max_cost_tier)
    if current_index >= cap_index:
        return None

    tier = TIER_ORDER[cap_index]
    model = {
        "small": settings.small_model,
        "medium": settings.medium_model,
        "frontier": settings.frontier_model,
    }[tier]
    return RouterDecision(
        tier=tier,
        model=model,
        reason=f"quality fallback to allowed {tier} tier",
    )
