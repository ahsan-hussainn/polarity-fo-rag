# ADR-0014: RAG serving — one FastAPI app (page + API), deployed on Render

- **Date:** 2026-07-13
- **Status:** Accepted

## Context

The brief's hard line is "deployable, not a localhost/notebook/Streamlit-demo." The retrieval core
(ADR-0013) works; it now needs to be *served* at a public URL. Two things shape the choice:

- Observed: the whole pipeline is Python, and the data already lives in Supabase (deployed). The serving
  layer is therefore **stateless compute** — it holds no data, it queries Supabase and OpenAI per
  request. That makes the deployable unit small.
- Observed: the retrieval path needs a **persistent Postgres connection** and outbound OpenAI calls per
  request — a shape that fits a long-lived container far better than a serverless function (cold starts,
  no connection reuse, awkward psycopg on Lambda/Vercel-Python).

## Decision

Serve with **one FastAPI app** (`pipeline/rag/app.py`): `GET /` returns the single-page UI
(`index.html`), `POST /query` runs the grounded retrieval, `GET /health` for the platform check. Page and
API share an origin, so there is no separate frontend, no CORS, and no JS build step. Deploy on **Render**
as a free **web service** (`render.yaml`): git-connected, `uvicorn ... --port $PORT`, secrets pasted as
dashboard env vars (never committed), auto-redeploy on push.

## Options considered

- **One FastAPI app (page + API) on Render (chosen).** Single deployable Python unit, cohesive with the
  pipeline, same-origin, real container that fits pgvector + OpenAI.
- **Next.js/Vercel frontend + separate Python API.** The locked stack named Vercel. Rejected as default:
  two codebases and two deploys, plus CORS, for a UI that is intentionally one search box. Vercel is also
  serverless — the wrong runtime for a persistent-connection Python service. (A Vercel front-end talking
  to this same API stays possible later; it just is not worth it now.)
- **Streamlit / Gradio.** Rejected outright — the brief explicitly excludes a Streamlit-style demo, and
  they hide the request/serving layer we want to own and show.
- **Serverless (Vercel Python / AWS Lambda).** Rejected: cold starts, no connection pooling, and packaging
  psycopg/OpenAI into a function is friction for zero benefit at this scale.

## Why this over the others

It is the smallest thing that satisfies "deployable" honestly: a real, always-reachable URL backed by a
real container, in one language, reusing `pipeline.db` and the same seams as the rest of the system.
Same-origin serving removes an entire class of frontend/deploy complexity (CORS, a second build, a second
host). Render's git-connected web service gives auto-deploy and a health check with a one-file config.

## Assumptions and risks

- Risk: Render's free tier sleeps after ~15 min idle → first request cold-starts in ~30–60 s. Acceptable
  for a demo; a keep-warm ping or the paid tier removes it. Documented, not hidden.
- Risk: secrets management. `DATABASE_URL` / `OPENAI_API_KEY` are `sync:false` in `render.yaml` and pasted
  in the dashboard, so they never enter git.
- Assumption: Supabase's Session pooler is reachable from Render (IPv4, port 5432) — the same string that
  works locally.

## What would change this

Real user traffic → paid tier or a keep-warm; a richer UI (filters, maps, saved queries) → a dedicated JS
frontend calling this same `/query` API (the split we deliberately avoided now becomes worth it). Neither
changes the API contract or the retrieval core.
