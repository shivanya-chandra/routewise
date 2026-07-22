import asyncio
import uuid
from decimal import Decimal

from app.db.models import LLMCall, LLMRequest
from app.db.repository import (
    ModelCallLog,
    RouteRequestLog,
    add_route_log,
    decimal_from_float,
    provider_from_model,
    sum_model_call_costs,
    sum_nullable_int,
)


class FakeSession:
    def __init__(self) -> None:
        self.objects: list[object] = []
        self.flush_count = 0

    def add(self, row: object) -> None:
        self.objects.append(row)

    async def flush(self) -> None:
        self.flush_count += 1


def test_decimal_from_float_uses_string_conversion() -> None:
    assert decimal_from_float(0.92) == Decimal("0.92")
    assert decimal_from_float(None) is None


def test_provider_from_model_reads_litellm_prefix() -> None:
    assert provider_from_model("ollama/llama3.2") == "ollama"
    assert provider_from_model("openai/gpt-4o-mini") == "openai"
    assert provider_from_model("gpt-4o-mini") == "openai"


def test_sum_helpers_ignore_missing_values() -> None:
    request_id = uuid.uuid4()
    call_logs = [
        ModelCallLog(
            request_id=request_id,
            model="small",
            provider=None,
            status="success",
            prompt_tokens=10,
            completion_tokens=5,
            estimated_cost_usd=Decimal("0.001"),
            latency_ms=100,
        ),
        ModelCallLog(
            request_id=request_id,
            model="frontier",
            provider=None,
            status="success",
            prompt_tokens=None,
            completion_tokens=7,
            estimated_cost_usd=Decimal("0.002"),
            latency_ms=200,
        ),
    ]

    assert sum_nullable_int([call.prompt_tokens for call in call_logs]) == 10
    assert sum_nullable_int([None, None]) is None
    assert sum_model_call_costs(call_logs) == Decimal("0.003")
    assert sum_model_call_costs([]) is None


def test_add_route_log_maps_dataclasses_to_sqlalchemy_rows() -> None:
    request_id = uuid.uuid4()
    request_log = RouteRequestLog(
        id=request_id,
        user_id="test-user",
        input_hash="abc123",
        selected_model="small",
        final_model="frontier",
        route_reason="fallback used",
        cache_hit=False,
        request_status="success",
        cache_bypassed=True,
        semantic_cache_hit=True,
        semantic_cache_input_hash="source-hash",
        semantic_cache_score=Decimal("0.98"),
        semantic_cache_method="hash_embedding",
        routing_policy="quality_first",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost_usd=Decimal("0.003"),
        preflight_estimated_prompt_tokens=12,
        preflight_estimated_completion_tokens=256,
        preflight_estimated_total_tokens=268,
        preflight_estimated_cost_usd=Decimal("0.004"),
        max_estimated_cost_usd=Decimal("0.01"),
        budget_status="within_budget",
        budget_exceeded=False,
        latency_ms=123,
        quality_score=Decimal("0.92"),
        quality_label="complete",
        quality_reason="Answer has enough substance.",
        fallback_count=1,
        fallback_skipped=True,
        fallback_skip_reason="fallback skipped in test",
    )
    call_log = ModelCallLog(
        request_id=request_id,
        model="frontier",
        provider=None,
        status="success",
        prompt_tokens=10,
        completion_tokens=5,
        estimated_cost_usd=Decimal("0.003"),
        latency_ms=120,
    )
    session = FakeSession()

    asyncio.run(add_route_log(session, request_log, [call_log]))  # type: ignore[arg-type]

    assert len(session.objects) == 2
    assert session.flush_count == 1
    assert isinstance(session.objects[0], LLMRequest)
    assert isinstance(session.objects[1], LLMCall)
    assert session.objects[0].id == request_id
    assert session.objects[0].request_status == "success"
    assert session.objects[0].cache_bypassed is True
    assert session.objects[0].semantic_cache_hit is True
    assert session.objects[0].semantic_cache_input_hash == "source-hash"
    assert session.objects[0].semantic_cache_score == Decimal("0.98")
    assert session.objects[0].semantic_cache_method == "hash_embedding"
    assert session.objects[0].routing_policy == "quality_first"
    assert session.objects[0].preflight_estimated_total_tokens == 268
    assert session.objects[0].preflight_estimated_cost_usd == Decimal("0.004")
    assert session.objects[0].budget_status == "within_budget"
    assert session.objects[0].quality_label == "complete"
    assert session.objects[0].quality_reason == "Answer has enough substance."
    assert session.objects[0].fallback_count == 1
    assert session.objects[0].fallback_skipped is True
    assert session.objects[0].fallback_skip_reason == "fallback skipped in test"
    assert session.objects[0].prompt_compressed is False
    assert session.objects[0].original_prompt_words is None
    assert session.objects[1].request_id == request_id
    assert session.objects[1].status == "success"
