from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    from app.db.models import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                """
                alter table llm_requests
                    add column if not exists prompt_compressed boolean default false,
                    add column if not exists original_prompt_words integer,
                    add column if not exists compressed_prompt_words integer,
                    add column if not exists compression_ratio numeric,
                    add column if not exists request_status varchar default 'success',
                    add column if not exists cache_bypassed boolean default false,
                    add column if not exists preflight_estimated_prompt_tokens integer,
                    add column if not exists preflight_estimated_completion_tokens integer,
                    add column if not exists preflight_estimated_total_tokens integer,
                    add column if not exists preflight_estimated_cost_usd numeric,
                    add column if not exists max_estimated_cost_usd numeric,
                    add column if not exists budget_status varchar,
                    add column if not exists budget_exceeded boolean default false,
                    add column if not exists quality_label varchar,
                    add column if not exists quality_reason text,
                    add column if not exists fallback_skipped boolean default false,
                    add column if not exists fallback_skip_reason text
                """
            )
        )
        await connection.execute(
            text(
                """
                update llm_requests
                set cache_bypassed = true
                where cache_bypassed = false
                    and route_reason ilike '%cache bypassed%'
                """
            )
        )
        await connection.execute(
            text(
                """
                with compressed_history as (
                    select
                        id,
                        substring(
                            route_reason
                            from 'prompt compressed ([0-9]+)->[0-9]+ words'
                        )::numeric as original_words,
                        substring(
                            route_reason
                            from 'prompt compressed [0-9]+->([0-9]+) words'
                        )::numeric as compressed_words
                    from llm_requests
                    where prompt_compressed = false
                        and route_reason ilike '%prompt compressed %->% words%'
                )
                update llm_requests as target_request
                set
                    prompt_compressed = true,
                    original_prompt_words = coalesce(
                        target_request.original_prompt_words,
                        compressed_history.original_words::integer
                    ),
                    compressed_prompt_words = coalesce(
                        target_request.compressed_prompt_words,
                        compressed_history.compressed_words::integer
                    ),
                    compression_ratio = coalesce(
                        target_request.compression_ratio,
                        compressed_history.compressed_words
                            / nullif(compressed_history.original_words, 0)
                    )
                from compressed_history
                where target_request.id = compressed_history.id
                    and compressed_history.original_words is not null
                    and compressed_history.compressed_words is not null
                """
            )
        )
        await connection.execute(
            text(
                """
                update llm_requests
                set
                    quality_label = case
                        when cache_hit then 'cache_hit'
                        when quality_score is null then null
                        when quality_score >= 0.90 then 'complete'
                        when quality_score >= 0.60 then 'short'
                        when quality_score > 0 then 'weak'
                        else 'empty'
                    end,
                    quality_reason = case
                        when cache_hit then 'Exact cached answer reused; no fresh quality assessment ran.'
                        when quality_score is null then null
                        when quality_score >= 0.90 then 'Backfilled from historical quality score.'
                        when quality_score >= 0.60 then 'Backfilled from historical quality score.'
                        when quality_score > 0 then 'Backfilled from historical quality score.'
                        else 'Backfilled from historical quality score.'
                    end
                where quality_label is null
                """
            )
        )


async def close_db() -> None:
    await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
