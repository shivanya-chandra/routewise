# RouteWise Code README

RouteWise is a cost-aware LLM routing gateway. It sits between an application and one or more LLM providers, then decides how to handle each request:

- return a previously cached answer when the exact same prompt was already answered
- send simple prompts to a small or local model
- send harder prompts to a medium or frontier model
- retry with the frontier model when the first answer does not meet the requested quality target

This README is the code-facing guide. For a non-technical explanation of the same project, read `README_PLAIN_ENGLISH.md`.

## Current Phase

The project is in Phase 4.

Phase 1 built the first working backend skeleton:

- FastAPI app boots successfully
- `GET /health` responds with `{"status":"ok"}`
- `POST /route` exists as the main routing endpoint
- request messages are hashed for exact-cache lookup
- routing chooses a small, medium, or frontier model based on prompt complexity
- model calls are isolated behind a LiteLLM wrapper
- answers receive a simple heuristic quality score
- low-quality non-frontier answers can be retried with the frontier model
- token usage fields are included in route responses when the provider returns usage data
- unit tests cover routing, cache keys, and quality scoring

Phase 2 added optional PostgreSQL persistence:

- each route request can be saved to `llm_requests`
- each model call can be saved to `llm_calls`
- cache hits can be recorded as request rows without model-call rows
- model-call errors can be recorded before the exception is re-raised
- request logging is off by default and enabled with `REQUEST_LOGGING_ENABLED=true`
- local table creation can be enabled with `AUTO_CREATE_DB_TABLES=true`

Phase 2 has been validated locally:

- Postgres tables were created
- `/route` successfully called local Ollama `llama3.2`
- successful model calls were written to `llm_calls`
- repeated identical requests returned `cache_hit=true`

Phase 3A added:

- model cost estimation from token usage
- zero-dollar estimates for local Ollama models
- configurable paid-model prices through `MODEL_PRICES_JSON`
- `estimated_cost_usd` in route responses
- a database-backed evaluation summary script
- repeatable local startup through `scripts/dev_start.sh`

Phase 3A has been validated locally:

- `/route` returned a live Ollama answer
- the response included `estimated_cost_usd`
- `llm_calls` recorded a successful model call with token usage and cost
- a repeated identical request returned `cache_hit=true`
- `scripts/run_eval.py --pretty` summarized total requests, cache hits, model-call success/failure, token usage, latency, and estimated cost

Phase 3B added:

- `GET /metrics/summary` so the eval summary is available through the API
- zero-cost persistence for cache-hit request rows

Phase 3C added:

- `GET /requests` for recent request history
- nested model-call details for requests that called a provider
- cache-hit request rows with empty `model_calls`

Phase 3D added:

- deterministic prompt compression for long prompts
- compression settings in `.env`
- response fields that show whether compression happened
- route reasons that record compression when a prompt was shortened
- an optional `bypass_cache` request flag for retesting model/compression behavior

Phase 3E added:

- persisted compression fields on `llm_requests`
- local auto-migration for existing Postgres tables
- compression counts, rates, saved words, and average compression ratio in `GET /metrics/summary`
- per-request compression fields in `GET /requests`

Phase 3F added:

- `GET /metrics/models` for model-by-model usage
- per-model success/error counts and success rate
- per-model token usage, estimated cost, and average latency

Phase 3G added:

- `GET /metrics/routes` for routing-decision breakdowns
- request counts and rates by selected model, final model, and cache-hit status
- fallback, compression, token, cost, quality, and latency metrics by route decision

Phase 3H added:

- `GET /readiness` for deeper local stack checks
- cache read/write probing
- optional Postgres probing when request logging is enabled
- Ollama reachability and local small-model availability checks
- short readiness timeouts so startup problems fail quickly instead of hanging

Phase 3I added:

- `POST /route/preview` for dry-run route inspection
- cache hit/miss/bypass status without calling a model
- selected model, candidate tier, route reason, and compression preview
- a cheap way to inspect routing behavior before spending tokens or writing request logs

Phase 3J added:

- `GET /models/catalog` for configured routing-model visibility
- one row each for the small, medium, and frontier routing tiers
- provider, local-model status, and known/missing price configuration for each tier
- a quick way to check paid-provider pricing setup before relying on cost metrics

Phase 3K added:

- `GET /config/diagnostics` for configuration warnings and action items
- provider inference for common OpenAI-style model names such as `gpt-4o-mini`
- missing price warnings for paid/non-local models
- missing provider API-key warnings when a configured provider requires one
- malformed `MODEL_PRICES_JSON` errors that explain what to fix

Phase 3L added:

- `POST /route/estimate` for request preflight token and cost estimates
- heuristic prompt-token estimates before provider calls
- cache-hit estimates that report zero expected model-call cost
- compression-aware prompt estimates for long prompts
- rough input, output, and total cost estimates when model pricing is known

Phase 3M added:

- optional `max_estimated_cost_usd` request budget guardrail
- budget status fields in `POST /route/estimate`
- `/route` preflight blocking before provider calls when known estimated cost exceeds the request budget
- safe handling for unknown prices: RouteWise reports `unknown` instead of blocking when it cannot estimate cost

Phase 3N added:

- fallback-aware budget protection
- `fallback_skipped` and `fallback_skip_reason` in route responses
- frontier fallback is skipped when its known estimated cost exceeds `max_estimated_cost_usd`
- the first model answer is returned instead of making an over-budget fallback call

Phase 3O added:

- persisted policy fields on `llm_requests`
- request logs for budget-blocked `/route` requests
- request-history fields for cache bypass, preflight estimates, budget status, and fallback skip decisions
- metrics for cache-bypassed requests, blocked requests, budget-exceeded requests, and fallback-skipped requests
- routing-decision metrics that show where budget and fallback policies affected traffic

Phase 4A added:

- structured answer-quality assessments with score, label, and reason
- stronger weak-answer detection for responses that ask for more input instead of completing the request
- `quality_label` and `quality_reason` in `POST /route` responses
- persisted quality diagnostics on `llm_requests`
- quality diagnostics in `GET /requests`

Phase 4B added:

- in-process semantic cache preview index
- lexical similarity scoring for cached prompts
- advisory semantic cache candidate fields in `POST /route/preview`
- advisory semantic cache candidate fields in `POST /route/estimate`
- successful model-call routes are indexed for later semantic preview
- semantic candidates are not automatically reused yet; exact cache still controls response reuse

Latest local verification:

```bash
python -m pytest -q
```

Expected result:

```text
72 passed
```

Health check:

```bash
curl http://localhost:8080/health
```

Expected result:

```json
{"status":"ok"}
```

Readiness check:

```bash
curl -s http://localhost:8080/readiness | jq
```

Expected result when the local stack is ready:

```json
{
  "status": "ready",
  "checks": {
    "cache": {
      "status": "ok",
      "detail": "memory cache accepted a short read/write probe."
    },
    "database": {
      "status": "ok",
      "detail": "Postgres accepted a simple select 1 query."
    },
    "model_backend": {
      "status": "ok",
      "detail": "Ollama is reachable and llama3.2 is installed."
    }
  }
}
```

## What Is Working

The foundation works:

- Python dependencies can be installed in a fresh virtual environment.
- The FastAPI server can run locally.
- The health endpoint confirms the server is reachable.
- The local unit tests pass.
- The routing engine can classify prompts by rough complexity.
- The cache key function creates stable hashes for identical requests.
- The quality scorer gives predictable scores for empty, weak, short, and reasonable answers.
- The repository layer can map route and model-call logs into SQLAlchemy rows.
- The route endpoint has optional persistence hooks for request, model-call, fallback, and cache-hit events.
- Route responses include `estimated_cost_usd` when cost can be calculated.
- `scripts/run_eval.py` summarizes request history from Postgres.
- `GET /metrics/summary` exposes the same summary through the API.
- `GET /requests` exposes recent individual request history through the API.
- Long prompts can be compressed before model calls.

## What Is Not Finished Yet

The project is not a full production gateway yet.

Still pending:

- a dashboard for route history and metrics
- paid-provider price configuration for any paid models you use
- semantic cache using embeddings
- smarter semantic compression for long contexts
- evaluation reports for cost savings and quality retention
- stronger quality checks beyond the current heuristic

## Architecture

```text
Client app
  -> RouteWise FastAPI gateway
  -> exact cache lookup
  -> complexity router
  -> optional prompt compression
  -> LiteLLM model call
  -> heuristic quality check
  -> optional frontier fallback
  -> cache final answer
  -> optionally persist request and model-call logs
  -> optionally summarize logs with eval script or metrics API
  -> response returned to client
```

## Request Flow

When a client calls `POST /route`, the app does this:

1. Converts incoming chat messages into dictionaries.
2. Creates an exact cache key using `request_hash`.
3. Checks the configured cache backend.
4. Returns the cached answer immediately if there is an exact hit.
5. Runs `choose_model` if there is no cache hit.
6. Compresses the prompt if compression is enabled and the prompt is above the configured threshold.
7. Calls the selected model through `call_model`.
8. Assesses answer quality with a score, label, and reason.
9. Falls back to the frontier model if the score is below `quality_target` and the first model was not already frontier.
10. Stores the final answer in cache.
11. Optionally persists request and model-call logs when request logging is enabled.
12. Estimates request cost when token usage and model pricing are available.
13. Returns the answer, selected model, final model, cache status, quality score, fallback count, token usage, estimated cost, and compression details.

## Project Layout

```text
app/
  main.py                  FastAPI app, lifespan setup, /health, /readiness, /route
  config.py                Environment-driven settings
  schemas.py               Pydantic request and response models
  core/
    cache.py               Exact cache hashing plus memory and Redis cache clients
    router_engine.py       Prompt complexity scoring and model-tier selection
    providers.py           Provider inference and provider env-var requirements
    model_catalog.py       Configured routing-model catalog helpers
    config_diagnostics.py  Configuration diagnostics helpers
    model_client.py        Direct Ollama client plus LiteLLM fallback
    quality.py             Heuristic answer scoring
    cost.py                Cost-estimation helpers
    preflight.py           Preflight token and cost estimate helpers
    prompt_compressor.py   Deterministic long-prompt compression helpers
  db/
    models.py              SQLAlchemy models for request and call logging
    session.py             Async database session setup and table initialization
    repository.py          Phase 2 persistence helpers
    metrics.py             Phase 3 summary metrics queries
    history.py             Phase 3 request-history queries
tests/
  test_cache.py            Cache-key behavior
  test_quality.py          Quality-score behavior
  test_router_engine.py    Routing behavior
  test_repository.py       Persistence helper behavior
  test_cost.py             Cost-estimation behavior
  test_eval.py             Metrics summary behavior
  test_metrics_endpoint.py Metrics endpoint behavior
  test_history.py          Request-history behavior
  test_prompt_compressor.py Prompt-compression behavior
  test_cache_bypass.py     Cache-bypass request behavior
  test_model_usage.py      Model-usage metrics behavior
  test_routing_decisions.py Routing-decision metrics behavior
  test_readiness.py        Readiness endpoint behavior
  test_route_preview.py    Route-preview endpoint behavior
  test_model_catalog.py    Configured model-catalog behavior
  test_config_diagnostics.py Configuration diagnostics behavior
  test_route_estimate.py   Route-estimate endpoint behavior
  test_cost_budget.py      Request budget guardrail behavior
scripts/
  dev_start.sh             Repeatable local dev startup helper
  run_eval.py              Database-backed evaluation summary
  seed_requests.py         Future request-seeding helper
```

## Important Files

### `app/main.py`

Owns the running API.

Important pieces:

- `lifespan`: creates either a Redis cache client or an in-memory cache client at startup.
- `GET /health`: returns `{"status":"ok"}` when the app is reachable.
- `GET /readiness`: checks cache, optional Postgres logging, and local Ollama model readiness.
- `POST /route/preview`: explains cache status, selected model, and compression behavior without calling a model.
- `POST /route/estimate`: estimates prompt tokens and rough cost before calling a model.
- `POST /route`: performs cache lookup, model routing, model call, quality scoring, fallback, caching, and response creation.
- `GET /models/catalog`: returns the configured small, medium, and frontier models with provider and price metadata.
- `GET /config/diagnostics`: returns configuration warnings, errors, and hints for missing prices/API keys.
- `GET /metrics/summary`: returns aggregate request, cache, model-call, token, cost, and latency metrics from Postgres.
- `GET /metrics/models`: returns provider/model usage, success rate, token, cost, and latency metrics from Postgres.
- `GET /metrics/routes`: returns routing-decision usage grouped by selected/final model and cache-hit status.
- `GET /requests`: returns recent request rows with nested model-call details.

### `app/config.py`

Loads settings from environment variables and `.env`.

Important settings:

```env
CACHE_BACKEND=memory
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://routewise:routewise@localhost:5432/routewise
REQUEST_LOGGING_ENABLED=false
AUTO_CREATE_DB_TABLES=false
SMALL_MODEL=ollama/llama3.2
MEDIUM_MODEL=gpt-4o-mini
FRONTIER_MODEL=gpt-4o
MODEL_CALL_TIMEOUT_SECONDS=60
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HTTP_TIMEOUT_SECONDS=60
READINESS_TIMEOUT_SECONDS=3
MODEL_PRICES_JSON={}
PREFLIGHT_DEFAULT_COMPLETION_TOKENS=256
EXACT_CACHE_TTL_SECONDS=86400
SEMANTIC_CACHE_PREVIEW_ENABLED=true
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.80
PROMPT_COMPRESSION_ENABLED=true
PROMPT_COMPRESSION_WORD_THRESHOLD=600
PROMPT_COMPRESSION_TARGET_WORDS=350
OPENAI_API_KEY=
```

Use `CACHE_BACKEND=memory` when developing without Redis.

Use `REQUEST_LOGGING_ENABLED=false` while you only want the lightweight Phase 1 path. Set it to `true` when Postgres is running and you want Phase 2 request logging.

### `app/schemas.py`

Defines the API shape.

Request model:

- `user_id`: optional caller identifier
- `messages`: required chat messages with `role` and `content`
- `quality_target`: desired score from `0.0` to `1.0`
- `max_cost_tier`: maximum allowed model tier, one of `small`, `medium`, or `frontier`
- `bypass_cache`: optional debugging flag that skips cache lookup and forces a fresh model call
- `max_estimated_cost_usd`: optional preflight budget; `/route` blocks before a model call when known estimated cost exceeds this value

Response model:

- `request_id`: unique ID for the request
- `answer`: final answer text
- `selected_model`: first model chosen by the router
- `final_model`: model that produced the final answer
- `cache_hit`: whether cache served the response
- `cache_bypassed`: whether the request intentionally skipped cache lookup
- `fallback_count`: number of fallback attempts
- `fallback_skipped`: whether a fallback was considered but skipped
- `fallback_skip_reason`: explanation when fallback was skipped
- `route_reason`: explanation of the routing decision
- `quality_score`: heuristic score for the final answer
- `quality_label`: short quality category such as `empty`, `refusal`, `needs_input`, `short`, `complete`, or `cache_hit`
- `quality_reason`: human-readable explanation for the quality label
- `prompt_tokens`, `completion_tokens`, `total_tokens`: usage fields when available
- `estimated_cost_usd`: estimated cost for the model calls used by the route
- `prompt_compressed`: whether the prompt was shortened before the model call
- `original_prompt_words`, `compressed_prompt_words`: word counts before and after compression
- `compression_ratio`: compressed word count divided by original word count when compression happened

Route preview response:

- `input_hash`: exact-cache hash for the request messages
- `cache_status`: `hit`, `miss`, or `bypassed`
- `would_call_model`: whether a real `/route` request would need a model call
- `selected_model`: `cache` for cache hits, otherwise the model RouteWise would call
- `candidate_model`, `candidate_tier`: router-selected model and tier even when the actual request would be served from cache
- `route_reason`: human-readable explanation of the dry-run decision
- `semantic_cache_candidate`: whether a similar cached prompt was found
- `semantic_cache_input_hash`, `semantic_cache_score`, `semantic_cache_reason`: advisory semantic cache candidate details
- `prompt_compressed`, `original_prompt_words`, `compressed_prompt_words`, `compression_ratio`: compression preview fields when a model call would happen

Route estimate response:

- `cache_status`: `hit`, `miss`, or `bypassed`
- `would_call_model`: whether a real request would need a provider call
- `selected_model`, `candidate_model`, `candidate_tier`: routing choice information
- `price_source`: `cache`, `configured`, `built_in`, `local_zero`, or `missing`
- `original_estimated_prompt_tokens`: prompt estimate before compression
- `estimated_prompt_tokens`: prompt estimate after any compression that would be applied
- `estimated_completion_tokens`: configured placeholder for expected output tokens
- `estimated_total_tokens`: prompt estimate plus expected completion estimate
- `estimated_input_cost_usd`, `estimated_output_cost_usd`, `estimated_total_cost_usd`: rough estimates when pricing is known
- `max_estimated_cost_usd`: optional caller-supplied budget
- `budget_status`: `not_set`, `within_budget`, `exceeds_budget`, or `unknown`
- `budget_exceeded`: whether the known estimate exceeds the supplied budget
- `semantic_cache_candidate`: whether a similar cached prompt was found
- `semantic_cache_input_hash`, `semantic_cache_score`, `semantic_cache_reason`: advisory semantic cache candidate details
- `estimate_note`: reminder that provider-reported token usage may differ

Model catalog response:

- `models`: one row for each configured routing tier
- each model includes `tier`, `model`, `provider`, and `is_local`
- `price_source`: `configured`, `built_in`, `local_zero`, or `missing`
- `input_price_per_1k`, `output_price_per_1k`: known price configuration when available

Config diagnostics response:

- `status`: `ok` when no warnings/errors exist, otherwise `needs_attention`
- `issues`: configuration findings with severity, code, message, optional hint, optional tier, and optional model
- missing prices are warnings because routing can still work, but cost estimation will be incomplete
- malformed `MODEL_PRICES_JSON` is an error because price parsing cannot be trusted

Metrics summary response:

- `total_requests`: number of persisted `/route` requests
- `cache_hits`: number of persisted requests served from exact cache
- `cache_hit_rate`: cache hits divided by total requests
- `cache_bypassed_requests`: number of requests that intentionally skipped cache lookup
- `compressed_requests`: number of persisted requests where prompt compression ran
- `compression_rate`: compressed requests divided by total requests
- `prompt_words_saved`: total original prompt words minus compressed prompt words
- `average_compression_ratio`: average compressed/original ratio for compressed requests
- `blocked_requests`: number of persisted requests stopped before a provider call
- `budget_exceeded_requests`: number of persisted requests whose known estimate exceeded the caller budget
- `fallback_skipped_requests`: number of persisted requests where fallback was skipped by policy
- `total_fallbacks`: total fallback attempts
- `successful_model_calls`: number of successful provider calls
- `failed_model_calls`: number of failed provider calls
- `prompt_tokens`, `completion_tokens`, `total_tokens`: aggregate token usage
- `estimated_cost_usd`: aggregate estimated provider cost
- `average_request_latency_ms`, `average_model_call_latency_ms`: average latency measurements

Model usage response:

- `models`: one row per model/provider pair found in `llm_calls`
- each model includes total calls, successful calls, failed calls, success rate, token totals, estimated cost, and average latency

Routing decisions response:

- `routes`: one row per selected model, final model, and cache-hit combination found in `llm_requests`
- each route includes request count/rate, fallbacks, compression count/savings, budget-exceeded count, fallback-skipped count, token totals, estimated cost, average quality, and average latency

Readiness response:

- `status`: `ready` when required checks pass, otherwise `not_ready`
- `checks.cache`: confirms the configured cache can save and read a short probe value
- `checks.database`: confirms Postgres accepts `select 1` when request logging is enabled; skipped when logging is disabled
- `checks.model_backend`: confirms local Ollama is reachable and the configured small model is installed when `SMALL_MODEL` is an Ollama model

Request history response:

- `requests`: newest persisted requests first
- each request includes selected/final model, cache status, route reason, tokens, estimated cost, latency, quality score, quality diagnostics, fallback count, compression details, policy fields, and creation time
- quality diagnostics include `quality_label` and `quality_reason`
- policy fields include request status, cache bypass, preflight token/cost estimates, budget status, budget exceeded, fallback skipped, and fallback skip reason
- each request includes `model_calls`, a list of provider calls for that request
- cache-hit rows have an empty `model_calls` list because cache hits do not call a model

### `app/core/cache.py`

Provides exact caching.

The key idea is simple: identical message lists should produce identical cache keys. Different content should produce different keys.

Current cache options:

- `MemoryExactCache`: local process memory, easiest for development
- `RedisExactCache`: Redis-backed cache for a more realistic deployment

This module also contains `MemorySemanticCacheIndex`, an advisory in-process similarity index. It uses lexical token overlap to find similar cached prompts for preview/estimate responses. It does not serve cached answers automatically.

### `app/core/router_engine.py`

Chooses which model tier to use.

Current heuristic:

- longer prompts increase complexity
- words like `architecture`, `debug`, `optimize`, `production`, and `refactor` increase complexity
- code blocks increase complexity
- a low score routes to the small model
- a medium score routes to the medium model
- a high score routes to the frontier model
- `max_cost_tier` can cap the route to a cheaper tier

This is intentionally simple for Phase 1. It gives us a visible, testable routing policy before we add more advanced evaluation.

### `app/core/model_client.py`

Calls model providers.

For `ollama/...` models, it calls Ollama directly through the local HTTP API. This keeps local development fast and avoids heavier provider imports.

For non-Ollama models, it falls back to LiteLLM. This lets the rest of the app call one function, `call_model`, instead of hard-coding one provider.

### `app/core/quality.py`

Scores answers using a simple heuristic.

The quality layer now returns a structured assessment:

- `score`: numeric value used by fallback decisions
- `label`: compact category for API responses and request history
- `reason`: human-readable explanation for debugging

Current labels and scores:

- `empty`: empty answer, score `0.0`
- `refusal`: refusal-like answer, score `0.40`
- `needs_input`: answer asks for more context instead of completing the request, score `0.45`
- `short`: answer under 20 words, score `0.65`
- `complete`: longer reasonable-looking answer, score `0.92`
- `cache_hit`: cached answer reused without a fresh quality assessment, score `1.0`

This is still not a true quality judge. It is the first Phase 4 step toward better fallback decisions and more explainable answer evaluation.

### `app/core/cost.py`

Estimates request cost from token usage.

Current behavior:

- local Ollama models estimate to `$0`
- unknown paid models return `None` unless configured
- paid model prices can be supplied through `MODEL_PRICES_JSON`

Example:

```env
MODEL_PRICES_JSON={"paid/model":{"input_per_1k":"0.01","output_per_1k":"0.02"}}
```

The route response includes `estimated_cost_usd`, and persisted request/model-call logs store estimated cost when available.

### `app/core/prompt_compressor.py`

Shortens long prompts before model calls.

Current behavior:

- compression only runs when enabled and the prompt is above `PROMPT_COMPRESSION_WORD_THRESHOLD`
- system messages are preserved
- long non-system messages keep their beginning and end
- the omitted middle is replaced with a marker that says how many words were removed
- cache keys still use the original request, not the compressed prompt

This is intentionally deterministic. It gives us a measurable compression path before adding semantic summarization or embedding-aware compression.

### `app/db/repository.py`

Converts route events into database rows.

It defines two logging objects:

- `RouteRequestLog`: one row for the overall `/route` request
- `ModelCallLog`: one row for each model call attempted during that request

It also has helper functions for:

- extracting provider names from LiteLLM-style model names
- converting float quality scores into `Decimal`
- summing token and cost fields across multiple model calls
- saving the request row and related call rows in one session

### `app/db/metrics.py`

Reads persisted logs and builds aggregate metrics.

Both `scripts/run_eval.py` and `GET /metrics/summary` use this module, so the CLI report and API report stay consistent.

### `app/db/history.py`

Reads recent request rows and their related model-call rows.

`GET /requests` uses this module to return inspectable request history without needing manual SQL.

## Local Setup

From the project directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Run tests:

```bash
python -m pytest -q
```

Run the API with memory cache:

```bash
CACHE_BACKEND=memory uvicorn app.main:app --port 8080 --ws none --loop asyncio
```

Check server health:

```bash
curl http://localhost:8080/health
```

For Phase 2 and Phase 3 local development, prefer the startup helper:

```bash
scripts/dev_start.sh
```

That command:

- starts Docker Postgres
- waits until Postgres is ready
- creates the local tables when needed
- checks that Ollama is reachable
- warms the local Ollama model before the first `/route` call
- starts the API with request logging, memory cache, and a longer local-model timeout

## Enabling Phase 2 PostgreSQL Logging

Start Postgres:

```bash
docker compose up -d postgres
```

Run the API with request logging and local table creation:

```bash
REQUEST_LOGGING_ENABLED=true \
AUTO_CREATE_DB_TABLES=true \
CACHE_BACKEND=memory \
MODEL_CALL_TIMEOUT_SECONDS=60 \
OLLAMA_BASE_URL=http://localhost:11434 \
uvicorn app.main:app --port 8080 --ws none --loop asyncio
```

The shorter version is:

```bash
scripts/dev_start.sh
```

With those flags, `/route` will try to write:

- one row to `llm_requests` for every route request
- one row to `llm_calls` for every real model call

Cache hits still create an `llm_requests` row, but they do not create an `llm_calls` row because no model was called.

## Running Phase 3 Evaluation

After sending a few `/route` requests with request logging enabled, run:

```bash
python scripts/run_eval.py --pretty
```

Or call the API endpoint:

```bash
curl http://localhost:8080/metrics/summary
```

Inspect recent request history:

```bash
curl "http://localhost:8080/requests?limit=5"
```

The output includes:

- total requests
- cache hit count and rate
- fallback count
- successful and failed model-call counts
- prompt, completion, and total tokens
- estimated cost
- average request latency
- average model-call latency

Recent local Phase 3A validation produced:

```json
{
  "total_requests": 8,
  "cache_hits": 3,
  "cache_hit_rate": 0.375,
  "successful_model_calls": 3,
  "failed_model_calls": 2,
  "prompt_tokens": 93,
  "completion_tokens": 9,
  "total_tokens": 102,
  "estimated_cost_usd": "0E-8"
}
```

## Testing `POST /route`

In a second terminal, send a request:

```bash
curl -X POST http://localhost:8080/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "quality_target": 0,
    "max_cost_tier": "small"
  }'
```

This endpoint requires a working model backend. For example:

- if `SMALL_MODEL=ollama/llama3.2`, Ollama must be running locally and the model must be available
- if using OpenAI models, `OPENAI_API_KEY` must be set

To force a fresh model call during testing, add `bypass_cache`:

```bash
curl -X POST http://localhost:8080/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "compression-test",
    "messages": [
      {"role": "user", "content": "Use a unique long prompt here."}
    ],
    "quality_target": 0,
    "max_cost_tier": "small",
    "bypass_cache": true
  }'
```

This skips cache lookup for that request, records `cache bypassed` in `route_reason`, and can still refresh the cache after the model call succeeds.

## Previewing a Route Without Calling a Model

Use `POST /route/preview` when you want to inspect what RouteWise would do without paying the cost of a provider call:

```bash
curl -s -X POST http://localhost:8080/route/preview \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "preview-test",
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "quality_target": 0,
    "max_cost_tier": "small"
  }' | jq
```

Expected shape:

```json
{
  "input_hash": "2833211db2d5ef186b8c713a0d4c4c5e9155303c3e024fc9bfc0dc53a7cdb9e8",
  "cache_status": "miss",
  "would_call_model": true,
  "selected_model": "ollama/llama3.2",
  "candidate_model": "ollama/llama3.2",
  "candidate_tier": "small",
  "route_reason": "cost capped at small; complexity score=0",
  "prompt_compressed": false,
  "original_prompt_words": 5,
  "compressed_prompt_words": 5,
  "compression_ratio": null
}
```

This endpoint does not call Ollama/OpenAI, does not write a request log, and does not update the cache. It only previews the decision.

## Estimating Tokens and Cost Before a Route

Use `POST /route/estimate` when you want a rough token and cost estimate before a real provider call:

```bash
curl -s -X POST http://localhost:8080/route/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "estimate-test",
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "quality_target": 0,
    "max_cost_tier": "small"
  }' | jq
```

Expected shape for a cache miss on local Ollama:

```json
{
  "input_hash": "2833211db2d5ef186b8c713a0d4c4c5e9155303c3e024fc9bfc0dc53a7cdb9e8",
  "cache_status": "miss",
  "would_call_model": true,
  "selected_model": "ollama/llama3.2",
  "candidate_model": "ollama/llama3.2",
  "candidate_tier": "small",
  "price_source": "built_in",
  "original_estimated_prompt_tokens": 14,
  "estimated_prompt_tokens": 14,
  "estimated_completion_tokens": 256,
  "estimated_total_tokens": 270,
  "estimated_input_cost_usd": "0E-8",
  "estimated_output_cost_usd": "0E-8",
  "estimated_total_cost_usd": "0E-8",
  "max_estimated_cost_usd": null,
  "budget_status": "not_set",
  "budget_exceeded": false,
  "prompt_compressed": false,
  "original_prompt_words": 5,
  "compressed_prompt_words": 5,
  "compression_ratio": null,
  "estimate_note": "Heuristic preflight estimate; actual provider token usage and cost may differ."
}
```

This endpoint does not call providers, does not write request logs, and does not update cache. It uses a simple local token heuristic, so provider-reported usage after a real `/route` call can differ.

To test a budget guardrail, add `max_estimated_cost_usd`:

```bash
curl -s -X POST http://localhost:8080/route/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "estimate-test",
    "messages": [
      {"role": "user", "content": "Explain this architecture in detail."}
    ],
    "quality_target": 0,
    "max_cost_tier": "frontier",
    "max_estimated_cost_usd": 0.001
  }' | jq
```

When pricing is configured and the estimate is above the budget, `/route/estimate` returns `budget_status: "exceeds_budget"`. A real `POST /route` request with the same budget will stop before calling the provider.

If pricing is missing, the budget status is `unknown`. RouteWise does not block in that case because it cannot prove the request exceeds the budget.

Budget checks also apply to fallback. If the first model answers but scores below `quality_target`, RouteWise estimates the frontier fallback before calling it. When that known fallback estimate exceeds `max_estimated_cost_usd`, the fallback is skipped and the response includes `fallback_skipped: true`.

## Inspecting Configured Models and Prices

Use `GET /models/catalog` to see the routing models RouteWise is currently configured to use:

```bash
curl -s http://localhost:8080/models/catalog | jq
```

Expected shape:

```json
{
  "models": [
    {
      "tier": "small",
      "model": "ollama/llama3.2",
      "provider": "ollama",
      "is_local": true,
      "price_source": "built_in",
      "input_price_per_1k": "0",
      "output_price_per_1k": "0"
    },
    {
      "tier": "medium",
      "model": "gpt-4o-mini",
      "provider": "openai",
      "is_local": false,
      "price_source": "missing",
      "input_price_per_1k": null,
      "output_price_per_1k": null
    },
    {
      "tier": "frontier",
      "model": "gpt-4o",
      "provider": "openai",
      "is_local": false,
      "price_source": "missing",
      "input_price_per_1k": null,
      "output_price_per_1k": null
    }
  ]
}
```

`missing` does not stop routing. It means RouteWise can call the model if the provider is configured, but cost estimation for that model will be `null` until `MODEL_PRICES_JSON` includes a price entry.

## Checking Configuration Diagnostics

Use `GET /config/diagnostics` to convert config gaps into action items:

```bash
curl -s http://localhost:8080/config/diagnostics | jq
```

Shortened expected shape when paid OpenAI models are configured without prices or an API key:

```json
{
  "status": "needs_attention",
  "issues": [
    {
      "severity": "warning",
      "code": "missing_model_price",
      "message": "medium model gpt-4o-mini has no price configuration.",
      "hint": "Add this model to MODEL_PRICES_JSON so RouteWise can estimate cost for successful calls.",
      "tier": "medium",
      "model": "gpt-4o-mini"
    },
    {
      "severity": "warning",
      "code": "missing_provider_api_key",
      "message": "openai models are configured, but OPENAI_API_KEY is not set.",
      "hint": "Set OPENAI_API_KEY before routing live requests to openai models.",
      "tier": null,
      "model": null
    }
  ]
}
```

This endpoint does not call providers. It only inspects local settings.

## Test Coverage

Current test files:

- `tests/test_cache.py`
- `tests/test_semantic_cache.py`
- `tests/test_quality.py`
- `tests/test_router_engine.py`
- `tests/test_repository.py`
- `tests/test_cost.py`
- `tests/test_eval.py`
- `tests/test_metrics_endpoint.py`
- `tests/test_history.py`
- `tests/test_prompt_compressor.py`
- `tests/test_cache_bypass.py`
- `tests/test_model_usage.py`
- `tests/test_routing_decisions.py`
- `tests/test_readiness.py`
- `tests/test_route_preview.py`
- `tests/test_model_catalog.py`
- `tests/test_config_diagnostics.py`
- `tests/test_route_estimate.py`
- `tests/test_cost_budget.py`

Current coverage is focused on Phase 1 routing behavior plus the first Phase 2 persistence helpers:

- cache hashes are stable for identical messages
- cache hashes change when message content changes
- semantic-cache helpers tokenize prompts, score overlap, and find advisory candidates
- simple prompts route to small models
- medium-complexity prompts route to medium models
- code prompts increase complexity
- cost caps can force a cheaper model
- empty answers score `0.0`
- refusal-like answers score low
- short answers score below the default target
- reasonable answers score above the default target
- repository helpers extract model providers
- repository helpers sum nullable token and cost values
- repository helpers map log objects into SQLAlchemy rows
- cost helpers estimate local Ollama as zero cost
- cost helpers support configured paid-model prices
- eval helpers summarize request and model-call logs
- the metrics endpoint returns the same summary shape used by the eval script
- request-history helpers nest model calls under their parent request
- the request-history endpoint returns recent request rows through the API
- prompt-compression helpers skip short prompts
- prompt-compression helpers shorten long prompts while preserving message edges
- prompt-compression helpers preserve system instructions
- cache bypass is opt-in and recorded in route reasons
- model-usage helpers summarize calls by model and provider
- routing-decision helpers summarize selected/final model choices and cache-hit paths
- readiness helpers report cache, database, and local model-backend status
- route-preview helpers explain cache, routing, and compression decisions without model calls
- model-catalog helpers expose configured tiers, providers, and price sources
- config-diagnostics helpers report missing prices, missing API keys, and invalid price JSON
- route-estimate helpers calculate heuristic token and cost estimates before model calls
- cost-budget helpers flag over-budget estimates, block `/route` before first provider calls, and skip over-budget fallback calls
- policy-observability helpers persist and summarize cache bypass, blocked requests, budget outcomes, and skipped fallbacks
- quality-assessment helpers explain why an answer was scored as empty, refusal, needs-input, short, complete, or cache-hit
- semantic-cache preview helpers expose similar cached prompts without reusing answers automatically

## Phase Roadmap

### Phase 1: Working Gateway Skeleton

Status: mostly complete.

Done:

- FastAPI app
- health endpoint
- route endpoint
- exact cache support
- complexity router
- LiteLLM client wrapper
- heuristic quality scoring
- frontier fallback path
- token usage fields
- unit tests

Still planned:

- fallback behavior with real model responses

### Phase 2: Persistence and Observability

Status: validated locally.

Done:

- save each request to PostgreSQL
- save each model call to PostgreSQL
- record latency, selected model, final model, token usage, and cost estimate

Still planned:

- add a dashboard for route history

### Phase 3: Cost, Compression, and Evaluation

Status: Phase 3A through Phase 3O complete.

Done:

- estimate cost per request
- support configurable model prices
- include `estimated_cost_usd` in route responses
- summarize request logs with `scripts/run_eval.py`
- measure cache hit rate, token usage, failures, latency, and estimated cost
- validate live Ollama cost logging and cache-hit behavior
- add `scripts/dev_start.sh` to make local startup repeatable
- add `GET /metrics/summary` for API-accessible eval metrics
- add `GET /requests` for recent request-history inspection
- add deterministic prompt compression for long prompts
- add `bypass_cache` for compression/model retesting without changing the original prompt
- persist compression fields for metrics and request history
- add `GET /metrics/models` for model-by-model usage metrics
- add `GET /metrics/routes` for routing-decision metrics
- add `GET /readiness` for cache, Postgres, and Ollama readiness checks
- add `POST /route/preview` for dry-run route inspection
- add `GET /models/catalog` for configured model and price visibility
- add `GET /config/diagnostics` for configuration warnings and action items
- add `POST /route/estimate` for preflight token and cost estimates
- add `max_estimated_cost_usd` budget guardrails for known preflight costs
- add fallback-aware budget protection
- persist policy decisions into request history and metrics

Still planned:

- measure token reduction and quality retention on larger real request sets
- add smarter semantic compression

### Phase 4: Smarter Routing

Status: Phase 4B complete.

Done:

- add structured quality assessment labels and reasons
- expose quality diagnostics in route responses and request history
- persist quality diagnostics with request logs
- add advisory semantic cache preview with lexical similarity scoring
- expose semantic cache candidates in route preview and route estimate

Planned:

- embedding-based similarity lookup
- safe semantic-cache response reuse policy
- more nuanced routing policies
- production deployment hardening
