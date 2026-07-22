from dataclasses import dataclass

from app.core.router_engine import choose_fallback_model, choose_model, estimate_complexity
from app.schemas import ChatMessage


@dataclass(frozen=True)
class FakeSettings:
    small_model: str = "small"
    medium_model: str = "medium"
    frontier_model: str = "frontier"


def test_simple_prompt_routes_to_small_model() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Summarize this sentence.")],
        settings=FakeSettings(),
        max_cost_tier="frontier",
    )

    assert decision.tier == "small"
    assert decision.model == "small"


def test_medium_prompt_routes_to_medium_model() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Explain this architecture in detail.")],
        settings=FakeSettings(),
        max_cost_tier="frontier",
    )

    assert decision.tier == "medium"
    assert decision.model == "medium"


def test_code_prompt_increases_complexity() -> None:
    score = estimate_complexity(
        [ChatMessage(role="user", content="Debug this code:\n```python\nprint(x)\n```")]
    )

    assert score >= 3


def test_small_cost_cap_forces_small_model() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Debug this production architecture in detail.")],
        settings=FakeSettings(),
        max_cost_tier="small",
    )

    assert decision.tier == "small"


def test_quality_first_policy_promotes_simple_prompt() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Say hello.")],
        settings=FakeSettings(),
        max_cost_tier="frontier",
        routing_policy="quality_first",
    )

    assert decision.tier == "medium"
    assert "quality_first" in decision.reason


def test_cost_first_policy_demotes_medium_prompt() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Explain this architecture in detail.")],
        settings=FakeSettings(),
        max_cost_tier="frontier",
        routing_policy="cost_first",
    )

    assert decision.tier == "small"
    assert "cost_first" in decision.reason


def test_quality_first_policy_still_respects_cost_cap() -> None:
    decision = choose_model(
        [ChatMessage(role="user", content="Say hello.")],
        settings=FakeSettings(),
        max_cost_tier="small",
        routing_policy="quality_first",
    )

    assert decision.tier == "small"
    assert "cost capped at small" in decision.reason
    assert decision.model == "small"


def test_fallback_uses_strongest_allowed_tier() -> None:
    medium_fallback = choose_fallback_model(
        current_tier="small",
        max_cost_tier="medium",
        settings=FakeSettings(),
    )

    assert medium_fallback is not None
    assert medium_fallback.tier == "medium"
    assert medium_fallback.model == "medium"


def test_fallback_is_skipped_at_cost_cap() -> None:
    assert (
        choose_fallback_model(
            current_tier="small",
            max_cost_tier="small",
            settings=FakeSettings(),
        )
        is None
    )
