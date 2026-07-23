# RouteWise

RouteWise is a cost-aware LLM routing gateway built with FastAPI. Applications send chat messages to one endpoint; RouteWise decides whether to reuse a cached answer, choose a small/medium/frontier model, compress a long prompt, enforce a budget, and fall back when an answer is weak.

This is the engineering README. See [README_PLAIN_ENGLISH.md](README_PLAIN_ENGLISH.md) for a from-first-principles explanation.

## Final Release Status

The v1 project is feature complete for local development and portfolio demonstration. It includes:

- exact cache reuse with memory or Redis
- opt-in semantic cache reuse with a strict similarity threshold
- deterministic local hybrid lexical/vector similarity with no embedding service dependency
- PostgreSQL cache hydration across API restarts
- balanced, cost-first, and quality-first routing policies
- prompt complexity scoring and small/medium/frontier model selection
- deterministic long-prompt compression
- preflight token and cost estimates
- first-call and fallback budget guardrails
- structured quality labels and strongest-allowed-tier fallback
- request, model-call, cost, latency, cache, compression, and policy logging
- summary, per-model, per-route, history, diagnostics, catalog, and report APIs
- a user-facing playground with persistent profiles, prompt execution, routing controls, and cost estimates
- a responsive operations dashboard at `/dashboard`
- optional API-key protection, route throttling, CORS configuration, request IDs, and input limits
- Docker packaging, health checks, a startup helper, a smoke test, and GitHub Actions CI

## Architecture

```text
Client
  |
  v
POST /route
  |
  +-- request validation, optional API key, rate limit
  +-- exact cache lookup ----------------------------> return exact answer
  +-- opt-in semantic cache lookup ------------------> return similar answer
  +-- complexity + routing policy + cost-tier cap
  +-- optional prompt compression
  +-- preflight cost estimate + budget check --------> block over-budget call
  +-- selected model call
  +-- quality assessment
  +-- optional strongest-allowed-tier fallback + fallback budget check
  +-- cache answer, persist logs, update semantic index
  v
RouteResponse
```

FastAPI owns the HTTP interface. LiteLLM handles hosted-provider calls. Ollama has a direct local path. Redis is optional for shared exact caching. PostgreSQL stores request history, model calls, and restart-safe cache entries.

## Requirements

- Python 3.12
- Docker Desktop for PostgreSQL and optional Redis
- Ollama with `llama3.2` for the default local model

Install the local model once:

```bash
ollama pull llama3.2
```

## Quick Start

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
./scripts/dev_start.sh
```

The helper checks the Docker server version with a 15-second timeout, starts PostgreSQL, creates or updates tables, checks Ollama, warms the configured local model, and starts the API on port 8080. It uses this narrow daemon probe because `docker info` can be slow even when the containers needed by RouteWise are healthy.

Open another terminal:

```bash
curl http://localhost:8080/health
curl -s http://localhost:8080/readiness | python -m json.tool
./scripts/smoke_test.sh
```

Useful URLs:

- playground: `http://localhost:8080/`
- API docs: `http://localhost:8080/docs`
- operations dashboard: `http://localhost:8080/dashboard`
- health: `http://localhost:8080/health`
- readiness: `http://localhost:8080/readiness`

Stop the API with `Control-C`. Stop local containers with:

```bash
docker compose down
```

## Web Playground

Open `http://localhost:8080/` for the primary RouteWise experience. The playground lets a user:

- create, select, and delete a persistent local profile
- enter a prompt without writing an HTTP request
- choose a maximum model tier and see the configured model for every tier
- compare input/output prices per 1,000 tokens
- choose balanced, cost-first, or quality-first routing
- set a quality target and optional dollar budget
- set a maximum answer length to balance speed, detail, and cost
- allow semantic cache reuse or force a fresh response
- calculate preflight model, token, cache, budget, and cost information
- run the prompt and inspect the answer, final model, cache type, quality, tokens, cost, and route reason
- review recent requests for the selected profile

The maximum-model control is a routing ceiling, not a forced exact-model call. RouteWise may choose a cheaper tier when prompt complexity and policy allow it. This preserves the core purpose of the router.

Profiles are lightweight local RouteWise identities used to group request history. They are not login accounts or an internet-ready authentication system.

## Route Request

```bash
curl --max-time 70 -X POST http://localhost:8080/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "quality_target": 0.9,
    "max_cost_tier": "small",
    "routing_policy": "balanced",
    "allow_semantic_cache": false,
    "bypass_cache": false,
    "max_completion_tokens": 256,
    "max_estimated_cost_usd": 0.01
  }' | python -m json.tool
```

Important response fields include the selected/final model, cache type, whether the fresh response was cached, routing reason, policy, fallback decision, quality label, tokens, estimated cost, latency, and compression result. `finish_reason`, `answer_truncated`, and `max_completion_tokens` distinguish a complete response from one that reached its output limit.

If `ROUTEWISE_API_KEY` is configured, add:

```bash
-H "X-API-Key: $ROUTEWISE_API_KEY"
```

## Cache Behavior

Exact cache reuse is automatic unless `bypass_cache` is `true`. The key is based on the original normalized message list, so prompt compression does not change cache identity.

The cache fingerprint includes a schema version. Version 2 was introduced with finish-reason tracking so older entries that may contain unrecognized truncated answers are not restored after an upgrade.

Semantic cache reuse is deliberately stricter:

- the caller must send `allow_semantic_cache: true`
- `SEMANTIC_CACHE_REUSE_ENABLED` must be true
- similarity must meet `SEMANTIC_CACHE_REUSE_SIMILARITY_THRESHOLD`
- the candidate answer must still exist in exact cache
- `bypass_cache: true` disables both exact and semantic reuse

The local index combines token overlap with a deterministic hashed character/word vector. This avoids an external embedding dependency while providing a vector similarity signal. It is useful for close rewrites, not a substitute for a large semantic embedding model.

When request logging is enabled, successful model answers are upserted into `cache_entries`. API startup hydrates both the exact cache and semantic index from the latest saved rows, so memory-cache reuse can survive a restart.

## Routing Policies

`routing_policy` changes how aggressively RouteWise selects model tiers:

| Policy | Behavior |
| --- | --- |
| `balanced` | Uses prompt complexity directly. This is the default. |
| `cost_first` | Moves one tier cheaper when possible. |
| `quality_first` | Moves one tier stronger when the cost-tier cap permits it. |

`max_cost_tier` always remains the upper bound. A quality-first request capped at `small` still uses the small model.

## Cost and Fallback Safety

`POST /route/estimate` predicts prompt/completion tokens and estimated cost without calling a model. The estimate uses the request's `max_completion_tokens`, so the playground's answer-length control affects both the estimate and the real provider limit. RouteWise also gives the provider a short budget instruction asking it to finish within that allowance; those instruction tokens are included in the estimate. `max_estimated_cost_usd` applies the same estimate before a real call.

- known over-budget first calls return HTTP 402 before provider usage
- unknown prices report `budget_status: "unknown"` and do not create a false block
- models missing required credentials are priced but marked unavailable and are not called
- an over-budget fallback is skipped and the first answer is returned
- `max_cost_tier` also caps fallback, so a small-tier request never jumps to a paid frontier model
- a failed fallback returns the usable first answer and records the failed attempt
- fresh answers enter cache only when they meet the request's quality target
- answers stopped by the output-token limit are labeled `truncated`, are not cached, and tell the caller to raise `max_completion_tokens`
- local Ollama models use a built-in zero-dollar price
- GPT-4o mini and GPT-4o have built-in standard prices
- custom or updated paid prices can override built-ins through `MODEL_PRICES_JSON`

Example:

```env
MODEL_PRICES_JSON={"gpt-4o-mini":["0.00015","0.00060"],"gpt-4o":["0.0025","0.0100"]}
```

Values are input and output dollars per 1,000 tokens. The GPT defaults come from the official [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) and [GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o) model pages. `MODEL_PRICES_JSON` remains available because provider prices and account terms can change.

Pricing and availability are deliberately separate. RouteWise can show a useful estimate for a paid model without spending money, but a live OpenAI request requires `OPENAI_API_KEY`. The playground labels unavailable tiers and stops immediately with a setup message instead of waiting for a provider timeout.

Local Ollama latency depends on model loading, context size, available unified memory, and answer length. `scripts/dev_start.sh` warms the configured local model, API requests keep it loaded for `OLLAMA_KEEP_ALIVE`, `OLLAMA_CONTEXT_LENGTH` avoids an unnecessarily large local context, and `max_completion_tokens` limits generation work. The playground defaults to 256 answer tokens; 32, 64, or 128 can trade detail for speed, while 512 suits longer explanations. A cold first request can still take longer than later warm requests.

## API Surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | User-facing RouteWise playground. |
| `GET` | `/health` | Process health check. |
| `GET` | `/readiness` | Cache, database, and Ollama dependency checks. |
| `GET` | `/users` | List persistent local user profiles. |
| `POST` | `/users` | Create a local user profile. |
| `DELETE` | `/users/{user_id}` | Delete a local profile while retaining request history. |
| `POST` | `/route` | Route and answer a request. |
| `POST` | `/route/preview` | Show cache/routing/compression decisions without a model call. |
| `POST` | `/route/estimate` | Show token, cost, budget, and semantic-cache preflight data. |
| `GET` | `/requests` | Recent requests with nested model calls. |
| `GET` | `/metrics/summary` | Aggregate cache, token, cost, failure, fallback, and latency metrics. |
| `GET` | `/metrics/models` | Per-model usage and reliability. |
| `GET` | `/metrics/routes` | Per-routing-decision outcomes. |
| `GET` | `/metrics/report` | Combined dashboard/report payload with recommendations. |
| `GET` | `/models/catalog` | Configured tiers, providers, and price sources. |
| `GET` | `/config/diagnostics` | Actionable configuration warnings. |
| `GET` | `/dashboard` | Responsive operations dashboard. |

`/metrics/report` returns a clean zero-data report when request logging is disabled. Database-backed endpoints return HTTP 503 with a useful message when their required storage is unavailable.

## PostgreSQL Data

`AUTO_CREATE_DB_TABLES=true` creates tables and applies additive local migrations.

- `llm_requests`: one row for each route outcome, including cache, policy, budget, quality, compression, and fallback fields
- `llm_calls`: one row per provider attempt, including status, tokens, cost, latency, and errors
- `cache_entries`: latest successful answer and serialized original messages per exact input hash
- `user_profiles`: persistent local display names used by the playground

Inspect the latest requests without SQL:

```bash
curl -s "http://localhost:8080/requests?limit=5" | python -m json.tool
```

Or query PostgreSQL directly:

```bash
docker compose exec postgres psql -P pager=off -U routewise -d routewise \
  -c "select id, request_status, selected_model, final_model, cache_hit, semantic_cache_hit, latency_ms from llm_requests order by created_at desc limit 5;"
```

## Evaluation and Dashboard

Command-line summary:

```bash
python scripts/run_eval.py --pretty
```

API report:

```bash
curl -s http://localhost:8080/metrics/report | python -m json.tool
```

The dashboard consumes that report and displays request volume, cache savings, provider success, tokens, cost, latency, fallbacks, recommendations, model performance, and recent requests. It has verified desktop and mobile layouts.

## Configuration

All settings use environment variables and can be placed in `.env`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | Enables additional production diagnostics when set to `production`. |
| `ROUTEWISE_API_KEY` | empty | Protects all `/route*` and `/users*` endpoints when set. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `0` | Per-process `/route` limit; zero disables it. |
| `CORS_ALLOWED_ORIGINS` | empty | Comma-separated allowed browser origins. |
| `CACHE_BACKEND` | `memory` | `memory` or `redis`. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. |
| `DATABASE_URL` | local Postgres URL | Async SQLAlchemy database URL. |
| `REQUEST_LOGGING_ENABLED` | `false` | Enables request/model/cache persistence. |
| `AUTO_CREATE_DB_TABLES` | `false` | Creates and additively upgrades local tables. |
| `SMALL_MODEL` | `ollama/llama3.2` | Small routing tier. |
| `MEDIUM_MODEL` | `gpt-4o-mini` | Medium routing tier. |
| `FRONTIER_MODEL` | `gpt-4o` | Frontier routing tier and fallback. |
| `MODEL_CALL_TIMEOUT_SECONDS` | `60` | Whole model-call timeout. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_HTTP_TIMEOUT_SECONDS` | `60` | Direct Ollama HTTP timeout. |
| `OLLAMA_KEEP_ALIVE` | `30m` | How long Ollama keeps the local model loaded after a call. |
| `OLLAMA_CONTEXT_LENGTH` | `2048` | Ollama context window used per local request; lower values use less memory. |
| `READINESS_TIMEOUT_SECONDS` | `3` | Per-dependency readiness timeout. |
| `MODEL_PRICES_JSON` | empty | Optional paid-model price overrides. |
| `PREFLIGHT_DEFAULT_COMPLETION_TOKENS` | `256` | Fallback completion limit for internal model calls. |
| `EXACT_CACHE_TTL_SECONDS` | `86400` | Exact response lifetime in seconds. |
| `SEMANTIC_CACHE_PREVIEW_ENABLED` | `true` | Builds and queries the local similarity index. |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` | `0.80` | Advisory candidate threshold. |
| `SEMANTIC_CACHE_REUSE_ENABLED` | `true` | Allows opt-in semantic answer reuse. |
| `SEMANTIC_CACHE_REUSE_SIMILARITY_THRESHOLD` | `0.95` | Strict answer-reuse threshold. |
| `SEMANTIC_CACHE_HYDRATION_LIMIT` | `1000` | Maximum persisted entries loaded at startup. |
| `SEMANTIC_CACHE_EMBEDDING_DIMENSIONS` | `256` | Local hashed-vector dimensions. |
| `PROMPT_COMPRESSION_ENABLED` | `true` | Enables long-prompt compression. |
| `PROMPT_COMPRESSION_WORD_THRESHOLD` | `600` | Minimum words before compression. |
| `PROMPT_COMPRESSION_TARGET_WORDS` | `350` | Approximate compressed size. |
| `OPENAI_API_KEY` | empty | Required before live OpenAI calls. |

The in-memory rate limiter is suitable for one API process. Multi-instance deployments should put a distributed limiter at the gateway or use Redis-backed rate limiting.

## Tests

Run everything:

```bash
python -m pytest -q
```

Current expected result:

```text
128 passed
```

The suite covers cache keys and expiry, semantic scoring/reuse/hydration, all routing policies, prompt compression, quality/fallback, provider availability and errors, built-in and overridden prices, output limits, cost and budget checks, database mapping, user profiles, history/metrics/report builders, diagnostics, readiness, authentication, throttling, request IDs, validation limits, playground/dashboard delivery, and end-to-end route behavior.

CI runs compile checks and the full suite on Python 3.12 for pushes and pull requests.

## Docker

Validate Compose without starting services:

```bash
make compose-config
```

Start only infrastructure for local development:

```bash
docker compose up -d postgres
docker compose up -d redis
```

Build and run the complete container profile:

```bash
docker compose --profile app up --build
```

The app container connects to Ollama on the Mac through `host.docker.internal`.

On an 8 GB Mac, Docker Desktop's default VM memory limit can compete with a local Ollama model. In Docker Desktop, open **Settings > Resources > Advanced**, set the memory limit to about 2 GB for this single-Postgres development setup, and apply the restart. Docker documents that the default allocation is 50% of host memory; larger container workloads may need a higher limit.

## Repository Layout

```text
app/
  main.py                 HTTP lifecycle, endpoints, and route pipeline
  schemas.py              request/response validation contracts
  config.py               environment-backed settings
  playground.py           user-facing prompt and cost-control application
  dashboard.py            dependency-free operations dashboard
  core/
    cache.py              exact cache and hybrid semantic index
    router_engine.py      complexity scoring and routing policies
    model_client.py       Ollama and LiteLLM provider calls
    prompt_compressor.py  deterministic long-prompt compression
    quality.py            answer quality assessment
    preflight.py          token, cost, and budget estimates
    security.py           API-key and rate-limit helpers
    report.py             operational recommendations
  db/
    models.py             SQLAlchemy tables
    session.py            engine, sessions, and additive migrations
    repository.py         route/model/cache persistence
    users.py              persistent user-profile operations
    history.py            recent request query and shaping
    metrics.py            aggregate, model, and route metrics
scripts/
  dev_start.sh            guarded local startup
  smoke_test.sh           health, readiness, preview, playground, and dashboard checks
  run_eval.py             command-line evaluation summary
tests/                    unit, integration, and end-to-end regression suite
```

## Known Boundaries

- Quality assessment is deterministic and explainable, but it is not a human or model-based judge.
- Local hash embeddings improve close-text matching, but deep paraphrase detection needs a dedicated embedding model/vector store.
- Preflight token counts are heuristics; provider-reported usage remains authoritative.
- API-key middleware and the in-memory rate limiter are intentionally lightweight. Internet-facing deployments should also use TLS, a secrets manager, centralized rate limiting, and managed observability.
- Playground profiles group local usage history; production identity requires real authentication and authorization.
- Paid providers require credentials and current prices; the automated suite mocks provider calls and never spends paid tokens.

Within those boundaries, RouteWise v1 is a complete working routing gateway: it makes decisions, controls cost, reuses work, records outcomes, explains behavior, and exposes an operator-facing view of the system.
