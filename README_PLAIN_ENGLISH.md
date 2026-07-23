# RouteWise, Explained From the Beginning

This document assumes you have never built a backend, called an AI model, used a cache, or worked with a database.

## What RouteWise Is

Imagine an application has three AI workers:

- a small worker that is quick and cheap
- a medium worker that can handle harder requests
- a frontier worker that is strongest but usually costs more

Without RouteWise, the application must choose a worker itself every time. Many applications simply send everything to the strongest model. That works, but it can waste money and time.

RouteWise sits between the application and those workers. The application sends every AI request to RouteWise. RouteWise then decides what should happen.

Its job is to answer five questions:

1. Have we already answered this exact request?
2. Have we answered a very similar request that the caller permits us to reuse?
3. If a model is needed, how strong does it need to be?
4. Is the expected cost allowed?
5. If the first answer is weak, may we try a stronger model?

That makes RouteWise an AI routing gateway.

## How a Person Uses It

Open:

```text
http://localhost:8080/
```

This is the RouteWise playground. A person does not need to write a POST request or use Swagger for normal testing.

First, create a local user profile. The profile gives RouteWise a stable user ID so the page can show that person's recent requests. These profiles are not passwords or internet login accounts. They are simple local identities for this project.

Then:

1. Enter a prompt.
2. Choose the maximum model tier.
3. Choose balanced, cost-first, or quality-first routing.
4. Set the quality target.
5. Optionally set a dollar cost limit.
6. Choose a maximum answer length. Shorter limits are usually faster and cheaper; longer limits allow more detail.
7. Decide whether similar cached answers are allowed.
8. Click **Estimate** to see the likely model, tokens, cost, cache state, availability, and budget result without calling a model.
9. Click **Run prompt** to get the answer.

The response area shows the final model, exact or semantic cache usage, token counts, estimated cost, quality result, fallback count, and RouteWise's reason for the decision.

The model menu displays the model, price, and availability for each tier. It is a maximum-model control rather than a command to force one exact model. RouteWise can still choose a cheaper model when that is the sensible route.

## Why It Exists

AI models can charge for the text sent to them and the text they generate. Larger models also tend to be slower. A real application therefore needs more than a button that says "call the AI." It needs a decision layer.

For example, "Say hello" does not need the same model as "Debug this production architecture and explain the tradeoffs." RouteWise notices that difference.

It also tries to avoid paying twice for the same work. If the answer is already in cache, RouteWise can return it without contacting a model.

## What Happens to One Request

Suppose a user asks:

```text
Say hello in one sentence.
```

The request moves through RouteWise in this order.

### 1. RouteWise checks the request

It makes sure there is at least one message, each message has an allowed role, text is not empty, and the request is not unreasonably large. Unknown fields are rejected instead of being silently ignored.

If the owner configured a RouteWise API key, the caller must also send that key. The server can limit how many real route calls one caller makes per minute.

### 2. RouteWise checks exact cache

A cache is a place that stores work we may reuse.

RouteWise turns the complete original message list into a stable fingerprint called an input hash. The same messages produce the same hash. Different messages normally produce a different hash.

If that hash already has an answer, RouteWise returns the answer immediately. No AI model is called, token usage is zero for this request, and estimated cost is zero.

### 3. RouteWise may check semantic cache

Two prompts can mean nearly the same thing without being character-for-character identical:

```text
Say hello in one sentence.
Please say hello in one sentence.
```

RouteWise creates a small local vector representation of the words and character patterns, combines that with token overlap, and calculates a similarity score.

Similar answers are not reused automatically. The caller must explicitly send:

```json
"allow_semantic_cache": true
```

The score must also pass a stricter reuse threshold, and the source answer must still exist. This protects the main goal of caching without quietly returning a merely related answer.

`bypass_cache: true` skips both exact and semantic reuse. That option exists for testing or when a caller genuinely needs a fresh model answer.

### 4. RouteWise estimates difficulty

If there is no usable cached answer, RouteWise reads the prompt and gives it a simple complexity score.

Longer text, code blocks, and words such as "architecture," "debug," "production," "proof," or "refactor" increase the score.

The score is not artificial intelligence. It is a transparent rule that is easy to test and explain.

### 5. RouteWise applies the routing policy

The caller can choose one of three policies:

- `balanced` follows prompt complexity directly
- `cost_first` tries one model tier cheaper
- `quality_first` tries one model tier stronger

The caller also supplies a maximum cost tier. That cap always wins. If the request says "never go above small," even the quality-first policy remains on the small model.

### 6. RouteWise may shorten a long prompt

Very long prompts can use many tokens. RouteWise has a deterministic compression step that keeps useful sections from the beginning and end while removing part of the middle.

The original prompt still controls the cache key. Compression only changes what is sent to the model. This means repeating the same original prompt can still find the same cached answer.

The response and database record show whether compression happened, the original word count, the compressed word count, and the ratio.

### 7. RouteWise estimates cost before spending money

Before calling a model, RouteWise estimates prompt tokens and uses the answer-length limit selected by the user as the maximum number of completion tokens.

For local Ollama, estimated dollar cost is zero. RouteWise includes standard built-in prices for GPT-4o mini and GPT-4o. The owner can override those prices when provider pricing or account terms change.

The caller can set a maximum estimated cost. If a known price exceeds that budget, RouteWise stops before contacting the provider and returns an HTTP 402 response.

If the model price is unknown, RouteWise says the budget result is unknown. It does not pretend the request is free, and it does not block based on an invented number.

Knowing a model's price does not mean RouteWise has permission to call it. OpenAI models need `OPENAI_API_KEY`. Without that key, the page still shows their estimated cost, labels them unavailable, and stops immediately with a setup message. It does not make the user wait for a request that cannot succeed.

### 8. RouteWise calls the chosen model

The default small model is `llama3.2` running locally through Ollama. Hosted models are called through LiteLLM.

A timeout prevents one provider call from waiting forever. RouteWise uses non-blocking HTTP for Ollama, so a slow generation does not freeze estimates or other API requests. Missing credentials return a clear setup error; other provider failures return a detailed gateway error. Both can be recorded in the database with their latency and error message.

The startup helper sends a tiny warm-up request and RouteWise asks Ollama to keep the model loaded for 30 minutes. RouteWise also uses a smaller 2048-token local context so the default model fits more reliably on an 8 GB Mac. This reduces loading delays and memory pressure. The first request after Ollama starts can still be slower, and longer answer limits naturally take more generation time.

### 9. RouteWise checks answer quality

The first quality checker uses simple, explainable categories:

- `empty`: no useful answer
- `refusal`: the model appears to refuse
- `needs_input`: the model asks for missing information
- `short`: the answer may be too thin for a high target
- `complete`: the answer has enough substance for this rule
- `cache_hit` or `semantic_cache_hit`: an existing answer was reused

If the score is below the caller's target, RouteWise considers a stronger model up to the caller's maximum allowed tier.

### 10. RouteWise checks the fallback budget

The fallback receives its own estimate. If the stronger model would break the caller's budget, RouteWise returns the first answer and explains that fallback was skipped. The cost-tier cap also applies to fallback, so a request capped at `small` never jumps to a paid frontier model. If the fallback provider itself fails, RouteWise keeps the usable first answer and records the failed attempt.

Otherwise, RouteWise calls the frontier model and counts one fallback.

### 11. RouteWise stores the result

A fresh answer goes into exact cache and the semantic index only when it meets the request's quality target. A weak answer returned because fallback was unavailable is not saved for automatic reuse.

When database logging is on, RouteWise also saves the answer and original messages in PostgreSQL. When the API restarts, it loads recent saved entries back into memory. That is why cache knowledge can survive a restart even when the fast cache itself uses memory.

### 12. RouteWise returns an explanation

The final response contains the answer and a record of what happened:

- which model was selected
- which model finally answered
- whether exact or semantic cache was used
- which routing policy was applied
- why the route was chosen
- whether fallback happened or was skipped
- quality score, label, and explanation
- token counts
- estimated cost
- compression information

The goal is not only to make a decision. The goal is to make that decision understandable.

## The Three Kinds of Memory

RouteWise uses three related forms of memory.

### Exact cache

This is the fastest and safest reuse. Only the same original message list matches.

The local development default stores values in the API process. Redis can be used when several API processes need to share the cache.

### Semantic index

This stores a numeric representation of prompts so RouteWise can find close rewrites. Reuse is opt-in and uses a strict threshold.

### PostgreSQL

PostgreSQL is the permanent record. It stores user profiles, requests, model attempts, and cache entries. It is slower than an in-memory lookup but survives process restarts and supports history and reports.

## What the Database Records

The `llm_requests` table records one overall outcome per route request. It includes model choices, cache behavior, policy, budget status, quality, compression, fallback, latency, tokens, and cost.

The `llm_calls` table records each attempt to contact a model. A request may have zero calls because cache answered it, one normal call, or two calls when fallback happened.

The `cache_entries` table stores the latest successful answer for each exact prompt hash, together with the original messages needed to rebuild the semantic index.

The `user_profiles` table stores the local names created through the playground. Deleting a profile does not erase historical request records.

## Playground and Operations

RouteWise has two web views:

- `http://localhost:8080/` is where a person creates a profile, writes prompts, controls routing and cost, and reads answers.
- `http://localhost:8080/dashboard` is where an operator reviews system-wide volume, cache savings, reliability, tokens, latency, and cost.

Swagger at `http://localhost:8080/docs` remains available for developers who want to call each API directly.

## What the Dashboard Shows

Open:

```text
http://localhost:8080/dashboard
```

The dashboard shows:

- number of requests
- cache hit rate
- successful and failed model calls
- estimated cost
- token usage
- words saved by compression
- average request time
- fallback count
- recommendations based on current metrics
- performance by model
- recent request outcomes

The page works on desktop and mobile. If logging is disabled, it shows a clean zero-data state instead of a database error.

## How to Run It

You need Python 3.12, Docker Desktop, and Ollama.

In the project folder:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
ollama pull llama3.2
./scripts/dev_start.sh
```

Keep that terminal open. The server is supposed to keep running there.

In a second terminal:

```bash
cd ~/Code/routewise
source .venv/bin/activate
./scripts/smoke_test.sh
```

The startup helper avoids the problems we encountered earlier:

- it checks whether Docker is actually ready instead of hanging forever
- it waits for PostgreSQL
- it creates and updates the database tables
- it checks whether Ollama is reachable
- it warms the local model before starting the API

If Docker Desktop is not ready, the helper stops with a direct message. If Ollama is missing, it tells you before Uvicorn starts.

An 8 GB Mac has little room for Docker and a local AI model at the same time. Docker Desktop normally offers half of the computer's memory to its Linux virtual machine. For this project, which only needs one small PostgreSQL container, open **Docker Desktop > Settings > Resources > Advanced** and use a memory limit of about 2 GB. This leaves more memory for Ollama. Increase it again if you later run larger container workloads.

## How to Test It

Run:

```bash
python -m pytest -q
```

The current expected result is:

```text
123 passed
```

That means 123 automated scenarios behaved as expected. The tests include small functions, profile management, web-page delivery, API behavior, security controls, semantic reuse, restart hydration, budget blocking, fallback, model pricing and availability, Ollama output limits, provider errors, metrics, reporting, and complete route flows.

Passing tests do not mean every future provider and deployment can never fail. They mean the behavior RouteWise owns is repeatable and protected against known regressions.

The project also has a GitHub Actions workflow. GitHub runs compile checks and all tests whenever code is pushed or used in a pull request.

## What Health and Readiness Mean

`GET /health` answers one small question: is the FastAPI process alive enough to answer HTTP?

`GET /readiness` asks a deeper question: are the services needed for useful work available? It checks cache, PostgreSQL when logging is enabled, and the local Ollama model when configured.

A healthy process can still be unready. For example, FastAPI may be running while Ollama is closed. That distinction is intentional.

## What Security Was Added

The final version can require an `X-API-Key` header on route and profile endpoints. The playground has an API access field for this key. This prevents an unauthenticated caller from spending model tokens or changing profiles when the service is exposed.

It can also limit real route requests per minute and returns a request ID header for tracing one HTTP request through logs.

Request sizes and message counts are bounded. Browser origins can be explicitly allowed with CORS settings.

These controls are a strong local and demonstration baseline. A public internet service should additionally use HTTPS, secret storage, centralized rate limiting, backups, and managed monitoring.

## What "Finished" Means Here

RouteWise v1 now completes the project loop:

1. Receive and validate an AI request.
2. Avoid unnecessary model work with cache.
3. Select a model according to difficulty, policy, and a cost cap.
4. Reduce long prompt size.
5. Estimate and enforce cost before spending.
6. Judge the first answer and fall back safely when needed.
7. Record every important outcome.
8. Restore cached knowledge after restart.
9. Let people create profiles and use routing, cache, quality, and cost controls through a real web interface.
10. Summarize system behavior through APIs and an operations dashboard.
11. Protect the route surface and verify behavior automatically.

There are always possible future upgrades, such as a large embedding model, a learned quality judge, or distributed cloud infrastructure. Those are extensions, not missing pieces in this v1 goal.

The final project is a working, explainable, cost-aware LLM gateway rather than a collection of disconnected demos.
