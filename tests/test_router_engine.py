from dataclasses import dataclass

from app.core.router_engine import choose_model, estimate_complexity
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
    assert decision.model == "small"
