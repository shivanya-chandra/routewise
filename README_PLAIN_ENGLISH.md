# RouteWise Plain-English README

This document explains RouteWise without assuming the reader already knows backend engineering, APIs, caching, or LLM routing.

The short version:

RouteWise is a small backend service that helps decide which AI model should answer a user's prompt.

Instead of sending every prompt to the strongest and most expensive model, RouteWise tries to be careful:

- if it already answered the exact same question, reuse the old answer
- if the question looks simple, use a cheaper model
- if the question looks harder, use a stronger model
- if the first answer looks weak, try again with the strongest model

## Why This Project Exists

AI models cost money to use. Stronger models usually cost more. In many apps, not every request needs the strongest model.

For example, these requests are usually simple:

- "Say hello in one sentence."
- "Rewrite this sentence more clearly."
- "Classify this support ticket."
- "Summarize this short paragraph."

These requests may be harder:

- "Debug this production issue."
- "Explain this architecture in detail."
- "Refactor this code."
- "Reason through this complex tradeoff."

RouteWise is trying to build the layer that makes this decision automatically.

## What We Have Built So Far

We are now in Phase 3.

Phase 1 built the first working foundation.

That foundation can:

- start a local web server
- answer a health check
- receive a route request
- check whether the same prompt was answered before
- decide whether the prompt looks simple or hard
- call a model through LiteLLM
- score the answer with a simple rule
- retry with a stronger model if the first answer looks too weak
- return useful information about what happened
- pass the current automated tests

Phase 2 was about memory. Not model memory, but system memory.

In Phase 2, RouteWise starts recording what happened:

- which request came in
- whether the answer came from cache
- which model was selected first
- which model produced the final answer
- whether fallback happened
- how many tokens were reported
- how long the request took
- whether a model call succeeded or failed

This matters because a production routing system needs to answer questions like:

- are we saving money?
- which prompts are expensive?
- how often do we fall back?
- which models are being used most?
- are cache hits happening?

We proved Phase 2 locally:

- Postgres tables were created: `llm_requests`, `llm_calls`, and `cache_entries`
- `/route` successfully called local Ollama with `llama3.2`
- RouteWise returned a real answer: `Hello!`
- token usage was captured
- `llm_calls` recorded a successful model call
- sending the same request again returned `cache_hit: true`

Phase 3 is about measurement.

In Phase 3, RouteWise starts answering:

- how much did this request probably cost?
- how many tokens did we use?
- how often did cache save us a model call?
- how many model calls succeeded or failed?
- what was the average latency?

Local Ollama models are estimated as zero cost because they run on your own machine. Paid models can be configured with prices through `MODEL_PRICES_JSON`.

We have now proved the first Phase 3 slice locally:

- RouteWise called Ollama and returned `Hello!`
- the response included `estimated_cost_usd`
- Postgres recorded a successful model call with token counts and cost
- sending the same request again used cache instead of calling the model again
- the eval summary counted requests, cache hits, successful calls, failed calls, tokens, latency, and estimated cost
- the project now has a repeatable startup helper so we do not have to remember all the setup commands by hand
- the project now has a request-history endpoint for inspecting recent requests without raw SQL
- the project now has a first deterministic prompt-compression path for long prompts

## What This Phase Accomplished

This phase turned RouteWise from a service that can route one request into a service that can explain what happened across many requests.

Before this phase, RouteWise could receive a prompt, choose a model, call Ollama, cache repeated prompts, and write logs to Postgres. That was useful, but we still had to inspect raw database tables to understand whether the system was helping.

This phase added the first real measurement layer.

RouteWise can now answer questions like:

- how many requests have gone through the system?
- how many were served from cache?
- how often is cache saving us a model call?
- how many model calls succeeded?
- how many model calls failed?
- how many tokens did we use?
- what was the estimated cost?
- how slow or fast were the requests?

In the larger project, this matters because RouteWise is not only trying to call an AI model. It is trying to choose the right model, avoid unnecessary calls, control cost, and prove that the routing decision helped.

At this point, the project has three working layers:

1. Routing layer: decides what should answer.
2. Logging layer: records what happened.
3. Metrics layer: summarizes whether the system is doing something useful.

The next piece adds an inspection layer:

4. History layer: shows the recent individual requests behind the summary.

That means we can see both the big-picture totals and the specific request rows that produced those totals.

The next piece starts reducing work, not only measuring it:

5. Compression layer: shortens long prompts before they are sent to a model.

This first compression version is simple on purpose. It keeps the beginning and end of a long message, removes some of the middle, and inserts a marker that says how many words were omitted. It is not yet a smart semantic summarizer, but it gives us a real and testable path for reducing prompt size.

The next piece makes compression measurable:

6. Compression observability layer: records whether compression happened and summarizes how much text was saved.

That means RouteWise can answer questions like:

- how many requests were compressed?
- what percentage of requests used compression?
- how many prompt words did compression save?
- what was the average compression ratio?

These values appear in the metrics summary and in recent request history.

## What Passing Tests Means

When we ran:

```bash
python -m pytest -q
```

Earlier, Phase 1 had:

```text
10 passed
```

After adding semantic cache preview, the expected count is:

```text
72 passed
```

That means the project has automated checks, and all checks should succeed.

Those checks do not prove the whole product is finished. They prove the current foundation behaves the way we expect in important small cases.

The tests currently check twenty-three main things:

1. Cache keys work.
2. Routing decisions work.
3. Quality scoring works.
4. The new database logging helpers build the right rows.
5. Cost estimation works for local and configured paid models.
6. Evaluation summaries calculate totals, rates, cost, tokens, and latency.
7. The metrics API returns the same summary shape as the evaluation script.
8. The request-history API returns recent requests and their model-call details.
9. Prompt compression skips short prompts and shortens long prompts predictably.
10. Cache bypass is optional and recorded when used.
11. Compression metrics and request-history fields are shaped correctly.
12. Model-usage metrics summarize calls by model and provider.
13. Routing-decision metrics summarize cache paths, selected models, and final models.
14. Readiness checks report whether cache, Postgres, and the local model backend are usable.
15. Route preview explains cache, routing, and compression decisions without calling a model.
16. The model catalog shows configured routing tiers, providers, and price sources.
17. Configuration diagnostics turn missing prices, missing API keys, and invalid price JSON into clear issues.
18. Route estimates calculate rough prompt tokens and cost before calling a model.
19. Budget guardrails block known over-budget requests before model calls.
20. Fallback budget guardrails skip known over-budget fallback calls and return the first answer.
21. Policy observability saves budget, cache-bypass, blocked-request, and fallback-skip decisions into history and metrics.
22. Quality diagnostics explain answer scores with labels and reasons.
23. Semantic cache preview finds similar cached prompts without automatically reusing their answers.

## What the Health Check Means

When we ran:

```bash
curl http://localhost:8080/health
```

We got:

```json
{"status":"ok"}
```

That means the RouteWise server is running and reachable.

In plain terms: the app woke up, opened its door, and answered when we knocked.

This is important because before we test the main AI-routing behavior, we need to know the server itself is alive.

## The Main Idea

Imagine a user sends this prompt:

```text
Explain this architecture in detail.
```

RouteWise does not immediately send it to the most expensive model.

Instead, it asks a sequence of questions:

1. Have I seen this exact prompt before?
2. If yes, can I reuse the previous answer?
3. If not, how hard does this prompt look?
4. Which model should I start with?
5. Did the answer look good enough?
6. If not, should I retry with the strongest model?
7. What should I return to the caller?

That sequence is the heart of the project.

## The Pieces of RouteWise

### 1. The API Server

File: `app/main.py`

The API server is the part that receives requests from the outside world.

Right now it has these important endpoints:

- `GET /health`
- `GET /readiness`
- `POST /route/preview`
- `POST /route/estimate`
- `POST /route`
- `GET /models/catalog`
- `GET /config/diagnostics`
- `GET /metrics/summary`
- `GET /metrics/models`
- `GET /metrics/routes`
- `GET /requests`

An endpoint is just a URL that the app knows how to answer.

`GET /health` answers the question:

```text
Is the server alive?
```

`GET /readiness` answers the bigger setup question:

```text
Is the local stack ready to serve real RouteWise requests?
```

It checks whether the cache can read and write a tiny test value, whether Postgres responds when request logging is enabled, and whether local Ollama has the configured small model installed.

`POST /route/preview` answers:

```text
What would RouteWise do with this request if I sent it for real?
```

It can show whether the request would hit cache, which model would be selected, why that model was selected, and whether the prompt would be compressed. It does not call the model.

`POST /route/estimate` answers:

```text
Roughly how many tokens and dollars might this request use?
```

It uses a simple local token estimate and the configured model prices. It does not call the model, so the final provider-reported token count can still differ.

`GET /models/catalog` answers:

```text
Which models is RouteWise configured to use?
```

It lists the small, medium, and frontier models. For each one, it shows the provider, whether the model is local, and whether RouteWise knows the model's price.

`GET /config/diagnostics` answers:

```text
Does my RouteWise configuration need attention?
```

It turns setup gaps into readable warnings, such as missing paid-model prices or a missing provider API key.

`POST /route` answers the bigger question:

```text
Given this prompt, which model should handle it, and what answer should we return?
```

`GET /metrics/summary` answers:

```text
What has RouteWise been doing recently?
```

It summarizes logged requests, cache hits, model-call success and failure, token usage, cost, and latency.

`GET /metrics/models` answers:

```text
Which models are doing the work?
```

It groups model-call logs by model and provider. For each model, it shows total calls, successful calls, failed calls, success rate, token usage, estimated cost, and average latency.

`GET /metrics/routes` answers:

```text
What decisions did RouteWise make?
```

It groups request logs by selected model, final model, and cache-hit status. That lets us see how many requests went through cache, how many used a real model, how often fallback happened, and how each route path performed.

`GET /requests` answers:

```text
What are the most recent individual requests?
```

It returns recent request rows, newest first. For requests that called a model, it includes the model-call details inside that request. For cache hits, the model-call list is empty because no model call was needed.

### 2. The Health Check

File: `app/main.py`

The health check returns:

```json
{"status":"ok"}
```

This does not mean every feature is finished. It means the backend process is running and can respond.

It is like checking whether the lights are on before testing the machinery.

### 2A. The Readiness Check

File: `app/main.py`

The readiness check returns a more detailed answer:

```json
{
  "status": "ready",
  "checks": {
    "cache": {"status": "ok", "detail": "memory cache accepted a short read/write probe."},
    "database": {"status": "ok", "detail": "Postgres accepted a simple select 1 query."},
    "model_backend": {"status": "ok", "detail": "Ollama is reachable and llama3.2 is installed."}
  }
}
```

This is different from the health check.

The health check only says:

```text
The API process is alive.
```

The readiness check says:

```text
The important local pieces RouteWise depends on are usable.
```

If Ollama is closed, Docker/Postgres is down, or the configured local model is missing, readiness can return `not_ready` and explain which piece needs attention.

### 3. The Route Endpoint

File: `app/main.py`

The route endpoint is the main feature.

It accepts a request that contains:

- who the user is, if we know that
- the chat messages
- the requested quality target
- the maximum model cost tier we are allowed to use

Then it returns:

- the answer
- the model it selected first
- the model that produced the final answer
- whether the answer came from cache
- whether it had to fall back to a stronger model
- why it made the routing decision
- token usage when the provider reports it
- estimated cost when RouteWise can calculate it

### 4. The Request Schema

File: `app/schemas.py`

A schema defines the shape of valid input and output.

For this project, a message needs:

- a `role`, such as `user`, `assistant`, or `system`
- `content`, which is the text of the message

The schema helps reject malformed requests before the app tries to process them.

### 5. The Settings

File: `app/config.py`

Settings tell the app how to behave in this environment.

Examples:

- should cache use memory or Redis?
- what is the small model called?
- what is the medium model called?
- what is the frontier model called?
- where is the database?
- how long should cached answers live?

These values can come from `.env`, so we do not have to hard-code secrets or machine-specific setup into the code.

### 6. The Cache

File: `app/core/cache.py`

The cache stores answers that have already been created.

The current cache is exact. That means the prompt must match exactly.

Example:

```text
Explain polymorphism.
```

and

```text
Explain polymorphism!
```

are different strings, so the current exact cache treats them as different prompts.

RouteWise now also has semantic cache preview.

That does not reuse the answer yet. It only says:

```text
This new prompt looks similar to something already cached.
```

That is safer as a first step. We can inspect similarity before letting the app automatically reuse a non-exact cached answer.

### 7. The Cache Key

File: `app/core/cache.py`

The app turns the incoming messages into a hash.

A hash is a short, fixed-length fingerprint for some input text.

If the same messages come in again, the same hash is produced. If the messages change, the hash changes.

That lets RouteWise ask:

```text
Have I already answered this exact request?
```

### 8. The Router

File: `app/core/router_engine.py`

The router decides which model tier should handle the prompt.

It uses a simple complexity score.

The score goes up when:

- the prompt is long
- the prompt contains harder words like `architecture`, `debug`, `production`, or `refactor`
- the prompt includes a code block

Then the router chooses:

- small model for simple prompts
- medium model for moderate prompts
- frontier model for hard prompts

The caller can also set a maximum cost tier. For example, if the caller says `max_cost_tier` is `small`, RouteWise must stay with the small model even if the prompt looks harder.

### 9. The Model Client

File: `app/core/model_client.py`

The model client is the part that actually talks to the AI model provider.

This project can call local Ollama models directly. That is useful because local development should not depend on a heavy provider wrapper when all we need is `http://localhost:11434`.

For non-Ollama models, the project still uses LiteLLM. LiteLLM gives us one common way to call different model providers.

That means RouteWise can call `call_model`, and the client decides whether to use the direct Ollama path or LiteLLM.

One practical detail: local Ollama sometimes needs a few seconds to load a model the first time it is used. That is why the project now has a startup helper that warms the model before we send a real `/route` request.

### 10. The Quality Score

File: `app/core/quality.py`

After the model answers, RouteWise gives the answer a rough quality score.

The scoring is still intentionally simple, but it now gives three pieces of information:

- a numeric score
- a short label
- a plain-English reason

Current labels:

- `empty`: the answer is blank
- `refusal`: the answer refuses or avoids the request
- `needs_input`: the answer asks for more context instead of completing the request
- `short`: the answer is probably too thin for a high quality target
- `complete`: the answer has enough substance for the current heuristic
- `cache_hit`: RouteWise reused a cached answer

This is not real human judgment. It is a first Phase 4 step toward more explainable fallback behavior.

Later, this should become more sophisticated.

### 11. The Fallback

File: `app/main.py`

Fallback means:

```text
The first answer was not good enough, so try again with a stronger model.
```

For example, if RouteWise starts with the small model and gets a weak answer, it can retry with the frontier model.

This matters because the cheapest model is not always good enough.

The goal is balance:

- save money when the cheap model is enough
- use the stronger model when quality needs it

### 12. Token Usage

File: `app/core/model_client.py`

Many model providers report token usage.

Tokens are chunks of text that models process. More tokens usually means more cost.

RouteWise includes these fields when available:

- prompt tokens
- completion tokens
- total tokens

These fields will become more important when we add cost tracking.

### 13. Cost Estimation

File: `app/core/cost.py`

Cost estimation turns token usage into an estimated dollar amount.

For example, if a paid model charges one price for input tokens and another price for output tokens, RouteWise can estimate:

```text
input token cost + output token cost = estimated request cost
```

Local Ollama models are treated as zero cost in dollars because they run locally.

For paid models, prices can be configured with `MODEL_PRICES_JSON`.

The `/route` response now includes:

```text
estimated_cost_usd
```

The database logs also store estimated cost when it can be calculated.

### 14. The Database Pieces

Files:

- `app/db/models.py`
- `app/db/session.py`
- `app/db/repository.py`

The database work is now connected behind a switch.

The models describe tables for:

- requests
- model calls
- cache entries

The repository file now contains the helper code that can save route history.

The honest status is:

```text
RouteWise can now write request and model-call logs when request logging is enabled.
```

It is still optional. By default, request logging is off so the app can run easily without Postgres.

To turn it on, we run the server with:

```text
REQUEST_LOGGING_ENABLED=true
AUTO_CREATE_DB_TABLES=true
```

Then RouteWise can create the tables locally and save rows while requests happen.

To avoid repeating all the setup commands manually, use:

```bash
scripts/dev_start.sh
```

That one command starts Postgres, creates the tables, checks Ollama, warms the local model, and starts the API with the settings we used during the successful test.

### 15. Evaluation Summary

Files:

- `app/db/metrics.py`
- `scripts/run_eval.py`
- `app/main.py`

The evaluation summary reads the database logs and reports what RouteWise has been doing.

It can report:

- total requests
- cache hits
- cache hit rate
- total fallbacks
- successful model calls
- failed model calls
- prompt tokens
- completion tokens
- total tokens
- estimated cost
- average request latency
- average model-call latency

Run it from the terminal with:

```bash
python scripts/run_eval.py --pretty
```

Or call it through the API with:

```bash
curl http://localhost:8080/metrics/summary
```

This turned the report into a backend feature, not just a developer script.

### 16. Prompt Compression

File: `app/core/prompt_compressor.py`

Prompt compression means:

```text
Make a long prompt shorter before sending it to the model.
```

This matters because long prompts usually use more tokens. More tokens can mean slower responses and higher cost.

The first version is deterministic. That means it follows simple rules instead of asking another AI model to summarize the prompt.

Current behavior:

- short prompts are not changed
- long prompts can be shortened before the model call
- system messages are preserved
- long user messages keep the beginning and the end
- the removed middle is replaced with a marker that says how many words were omitted
- the `/route` response says whether compression happened

This is a first step. Later, compression can become smarter by summarizing meaning instead of just preserving the edges of the text.

RouteWise also stores compression details in request history. That lets us measure how often compression happened and how much text was saved.

### 17. Cache Bypass For Testing

Normal cache behavior should stay on. If the exact same original prompt comes in twice, RouteWise should reuse the cached answer.

For development, though, sometimes we want to force a fresh model call. That is useful when testing prompt compression, model latency, or provider behavior.

For that case, `/route` accepts:

```json
"bypass_cache": true
```

That tells RouteWise:

```text
Do not use an existing cached answer for this request.
```

The request can still refresh the cache after the model returns. The response includes `cache_bypassed`, and the route reason records `cache bypassed` so we can see that the flag was used.

### 18. Readiness Checks

`GET /health` only proves that the API process is reachable.

`GET /readiness` goes deeper. It checks whether the pieces RouteWise depends on are actually usable:

- cache can save and read a tiny value
- Postgres responds when request logging is enabled
- Ollama is reachable when the small model is local
- the configured local small model is installed

This matters because many problems we hit earlier were not code bugs. They were setup problems: Docker was closed, Postgres was not running, Ollama was missing, or the local model needed to warm up.

Readiness gives one place to check those conditions before testing `/route`.

### 19. Route Preview

`POST /route/preview` is a dry run.

That means RouteWise looks at the request and explains what would happen, but it does not actually call Ollama or OpenAI.

It can tell us:

- whether the exact prompt is already in cache
- whether cache was intentionally bypassed
- whether a real model call would happen
- which model tier would be chosen
- which model would be selected
- why that model was selected
- whether a similar cached prompt exists
- whether the prompt would be compressed before the model call

This is useful because it lets us test routing behavior without waiting for a model response and without adding extra rows to the request log.

In plain terms:

```text
/route/preview explains the plan.
/route executes the plan.
```

### 20. Route Estimate

`POST /route/estimate` is also a dry run, but it answers a different question.

Route preview asks:

```text
What would RouteWise do?
```

Route estimate asks:

```text
Roughly how much text and cost are we looking at?
```

It estimates:

- the prompt tokens before compression
- the prompt tokens after compression
- a default expected number of completion tokens
- the total estimated tokens
- the input cost, output cost, and total cost when pricing is known

This is only an estimate. Real providers count tokens using their own tokenizers, so the final values from a real `/route` call can be different.

For cache hits, the estimated model-call cost is zero because no model call should happen.

### 21. Budget Guardrails

Budget guardrails let the caller say:

```text
Do not start a model call if the known estimated cost is above this amount.
```

The request field is:

```json
"max_estimated_cost_usd": 0.001
```

This builds on route estimates.

If RouteWise knows the model price and the estimated cost is above the budget, a real `/route` request stops before calling the model provider.

Budget guardrails also protect fallback.

If the first model gives an answer but the answer scores below the requested quality target, RouteWise may want to try the frontier model. Before it does that, it checks the fallback estimate against the same budget.

If the fallback would exceed the budget, RouteWise skips the fallback and returns the first answer. The response says:

```json
"fallback_skipped": true
```

If RouteWise does not know the model price, the budget status becomes:

```text
unknown
```

In that case RouteWise does not block automatically, because it cannot prove the request is over budget.

For local Ollama models, the estimated dollar cost is zero, so they normally stay within any non-negative budget.

### 22. Policy Observability

Policy observability means RouteWise does not only make a decision. It also remembers the decision.

For example, if a request is blocked before calling a model because the known estimate is above the caller's budget, RouteWise now saves that blocked request in `llm_requests`.

That matters because a dashboard or report can later answer:

- how many requests were blocked before spending money?
- how many requests intentionally bypassed cache?
- how many requests exceeded the caller's known budget?
- how many fallback calls were skipped because they would be too expensive?
- which routing paths are most affected by budget policy?

These fields appear in recent request history and in metrics:

- `GET /requests`
- `GET /metrics/summary`
- `GET /metrics/routes`

In plain terms:

```text
Before this step, RouteWise could enforce the budget.
After this step, RouteWise can also explain how often that policy mattered.
```

### 23. Model Catalog

`GET /models/catalog` shows the model ladder RouteWise is currently configured to use.

RouteWise has three routing tiers:

- small
- medium
- frontier

The catalog shows which model is assigned to each tier.

It also shows:

- the provider name, when the model name includes one
- whether the model is local
- whether the price came from built-in defaults
- whether the price came from `MODEL_PRICES_JSON`
- whether the price is missing

This matters because RouteWise can only estimate cost when it knows the model's input and output token prices.

For local Ollama models, cost is treated as zero dollars.

For paid models, a missing price does not mean the model cannot run. It means RouteWise cannot estimate its cost yet.

### 23. Configuration Diagnostics

`GET /config/diagnostics` is the next step after the model catalog.

The catalog says:

```text
Here is what RouteWise is configured to use.
```

Diagnostics says:

```text
Here is what looks incomplete or risky in that configuration.
```

For example, diagnostics can warn us when:

- a paid model has no price entry
- OpenAI-style models are configured but `OPENAI_API_KEY` is missing
- `MODEL_PRICES_JSON` is not valid JSON
- the same model is reused for multiple tiers

This endpoint does not call any model provider. It only reads local settings and explains what may need fixing before live traffic.

### 24. The Tests

Folder: `tests/`

Tests are small automated checks that prove the code behaves as expected.

Current tests check:

- the same prompt creates the same cache hash
- different prompt content creates a different cache hash
- simple prompts route to the small model
- medium prompts route to the medium model
- code prompts are considered harder
- a small cost cap forces the small model
- empty answers score zero
- refusal-like answers score low
- short answers score below the default quality target
- reasonable answers score above the default quality target
- database helper functions prepare request and model-call rows correctly
- local Ollama cost is estimated as zero
- configured paid model prices calculate estimated cost
- evaluation summaries calculate useful metrics from logs
- the metrics endpoint returns the evaluation summary through the API
- request-history helpers nest model calls under the request that caused them
- the request-history endpoint returns recent request rows through the API
- prompt-compression helpers skip short prompts
- prompt-compression helpers shorten long prompts while preserving important edges
- prompt-compression helpers preserve system instructions
- cache bypass is opt-in and recorded when used
- compression metrics and request-history fields are shaped correctly
- model-usage metrics summarize calls by model and provider
- routing-decision metrics summarize cache paths, selected models, and final models
- readiness checks report cache, database, and local model-backend status
- route preview explains cache, routing, and compression decisions without model calls
- model catalog shows configured routing tiers, providers, and price sources
- configuration diagnostics report missing prices, missing API keys, and invalid price JSON
- route estimates calculate heuristic prompt tokens and rough cost before model calls
- budget guardrails block known over-budget requests before model calls
- fallback budget guardrails skip known over-budget fallback calls
- policy observability records cache bypass, blocked requests, budget outcomes, and skipped fallbacks in history and metrics
- quality diagnostics explain answer scores with labels and reasons
- semantic cache preview finds similar cached prompts without automatically reusing their answers

Passing tests mean the foundation behaves correctly for the cases we currently know to check.

## What Still Needs To Be Proven

The health check and tests are good signs, but they are not the finish line.

We have now proven:

- `POST /route` works with a real model provider
- the app can call Ollama or OpenAI correctly
- repeated prompts actually hit cache through the API
- PostgreSQL logging works with a live Docker Postgres database
- cost and token data appear in both API responses and database logs
- the evaluation summary works against real local request history
- recent individual request history can be read through `GET /requests`
- long prompts can be compressed before model calls
- compression savings can be measured through metrics and request history
- local stack readiness can be checked through `GET /readiness`
- routing decisions can be previewed through `POST /route/preview` without calling a model
- route token and cost estimates can be inspected through `POST /route/estimate`
- known over-budget requests can be blocked with `max_estimated_cost_usd`
- known over-budget fallbacks can be skipped with the same budget guardrail
- budget and fallback policy outcomes can be inspected through request history and metrics
- answer quality labels and reasons can be inspected through route responses and request history
- similar cached prompts can be previewed through route preview and route estimate
- configured routing models and price sources can be inspected through `GET /models/catalog`
- configuration issues can be inspected through `GET /config/diagnostics`

We still need to prove:

- weak live answers trigger fallback correctly
- Redis cache works when enabled
- the evaluation summary against a larger real request set

## The Current Status In One Sentence

Phase 1 built the gateway foundation, Phase 2 proved database observability, Phase 3 added cost estimation, compression, metrics, diagnostics, budgets, and policy observability, and Phase 4 has started smarter routing with quality diagnostics and semantic cache preview.

## What Comes Next

The latest practical step added semantic cache preview:

```text
Advisory similar-prompt detection
```

That lets RouteWise say when a new prompt looks similar to something already cached, without automatically reusing that answer yet.

After that, the next product work is:

- test configured paid-model prices against a real paid provider
- test fallback with a live weak answer
- measure prompt-compression savings on real long prompts
- improve quality scoring further
- build evaluation reports
