# ADR-0017: RAG latency — stream the answer, reuse every connection, parallelize independent calls

- **Date:** 2026-07-14
- **Status:** Accepted

## Context

Queries felt slow. Measured (not guessed) with a per-stage profile, twice, steady-state ~16–17s:

| Stage | Time | Cause |
|---|---|---|
| Answer generation | ~10s | 350–450 tokens generated, nothing shown until the last one |
| Query embedding | ~3s | fresh OpenAI client (new TLS handshake) per call |
| Intent classification | 1.5–2.5s | ditto, and run serially before the embedding |
| DB connect | ~1s | fresh psycopg connection to the Supabase pooler per query |
| All retrieval SQL | ~0.5s | — |

The database and retrieval were innocent. The cost was network round-trips, amplified by building a
new OpenAI client three times per query and a new Postgres TLS connection per request — and by the
answer's richer analyst format (ADR-0016) roughly tripling completion length.

## Decision

Four changes:

1. **Stream the answer.** New `answer_stream()` generator and `POST /query/stream` (NDJSON events):
   one `meta` line (intent + full sources) the moment retrieval finishes, then `delta` text chunks,
   then `done`. The UI renders the coverage cards at ~2s and the brief flows in as it generates.
   `/query` stays unchanged as the plain request/response contract (CLI, API clients, UI fallback).
2. **One shared OpenAI client** (`pipeline/rag/oai.py`) — the SDK client is thread-safe and holds a
   keep-alive pool; intent/embed/answer all reuse it.
3. **Pooled DB connections** (`db.get_pool()`, psycopg_pool, autocommit, max 4) for the serving
   path. A bare cached connection would race across FastAPI's worker threads; the pool is the
   correct primitive. Batch pipeline stages keep plain `get_conn()`.
4. **Classify ∥ embed.** The intent call and the query embedding are independent; the embedding now
   runs speculatively in a thread while classification decides the route. On lookup/aggregate paths
   the vector goes unused (~$0.0000004 wasted — cheaper than serializing every discovery query).

## Measured result (same machine, same query)

Coverage cards (meta) at **1.6s**, first answer text at **2.3s**, complete at ~8s — against 16–17s
to first paint before. Perceived latency moved from "generation finished" to "retrieval finished."

## Assumptions and risks

- Render's free-tier cold start (~30–60s after idle) is unaffected — that is the tier, not the code.
- Streaming responses pass through Render's proxy unbuffered (`X-Accel-Buffering: no` set); if a
  proxy ever buffers, the UI falls back to `/query` automatically (and a server-reported error does
  NOT trigger the fallback, to avoid re-running a failed query at double cost).
- Numbers were measured from a high-RTT network; absolute times on Render will differ, the
  structural wins (handshake reuse, parallelism, streaming) hold anywhere.

## What would change this

Real traffic would justify caching intent classifications for repeated queries and a regex
pre-router for obvious aggregates (skipping LLM call #1 entirely); neither is worth it at demo scale.
