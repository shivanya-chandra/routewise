import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LLMRequest(Base):
    __tablename__ = "llm_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    input_hash: Mapped[str] = mapped_column(String, index=True)
    selected_model: Mapped[str] = mapped_column(String)
    final_model: Mapped[str] = mapped_column(String)
    route_reason: Mapped[str] = mapped_column(Text)
    request_status: Mapped[str] = mapped_column(String, default="success")
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_bypassed: Mapped[bool] = mapped_column(Boolean, default=False)
    semantic_cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    semantic_cache_input_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    semantic_cache_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    semantic_cache_method: Mapped[str | None] = mapped_column(String, nullable=True)
    routing_policy: Mapped[str] = mapped_column(String, default="balanced")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    preflight_estimated_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preflight_estimated_completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preflight_estimated_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preflight_estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    max_estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    budget_status: Mapped[str | None] = mapped_column(String, nullable=True)
    budget_exceeded: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    quality_label: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_compressed: Mapped[bool] = mapped_column(Boolean, default=False)
    original_prompt_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compressed_prompt_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compression_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_requests.id"))
    model: Mapped[str] = mapped_column(String)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    input_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
