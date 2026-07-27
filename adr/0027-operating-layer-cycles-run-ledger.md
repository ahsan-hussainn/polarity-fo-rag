# ADR-0027: The operating layer — scheduled cycles, run ledger, evidence-based staleness

- **Date:** 2026-07-27
- **Status:** Accepted

## Context

The Stage 2 brief judges the system by what it did while running: ≥2 scheduler-triggered runs ≥48h
apart on a platform that keeps its own run history, ≥1 real dependency failure met while running,
and a cross-run staleness/trust event with a captured, evidence-based reason — the brief is explicit
that a clock-based expiry does not count (observed: our `is_stale` was exactly that). Observed: the
repo had zero operating machinery — no scheduler, no run concept, no persisted logs, no cost ledger
(embedding/RAG usage was discarded); ADR-0007 deliberately deferred this to Stage 2. Assumed: 6h
cadence gives enough cycles (~12–14 in-window) for natural evidence drift.

## Decision

A new `ops` schema is the system's memory: `runs` (one ledger row per run), `run_events` (every
model/external/db action with duration + tokens + USD), `observations` (per-record evidence
baselines), `trust_events` (what changed, the evidence, the action), `query_log` (ADR-0026 Layer 3,
now built). One CLI entrypoint `operate` runs a cycle — observe all held records (bounded pool of
8: website status + normalized text hash; held ADV filing date; email grades), compare against the
latest observation from an earlier run, write trust events on change, then rebuild gold → export →
incremental rag-index → reconcile — scheduled by **GitHub Actions** cron `23 */6 * * *` with a
`concurrency` group so runs can never overlap. Staleness = a later cycle's observation
contradicting an earlier cycle's, never a timer.

## Options considered

- **GitHub Actions (chosen):** free, the repo already lives there, run history with per-run detail
  pages is platform-kept (the required screenshots + shareable read access), secrets managed.
- **Render cron job:** rejected — paid instance type, and it would couple the serving deploy to the
  operating schedule; a bad cycle could never be allowed to take the live URL down with it.
- **cron-job.org hitting an HTTP endpoint:** rejected — cycles run minutes, not seconds; a web
  request is the wrong shape (timeouts), and it would put pipeline execution inside the serving
  process.
- **In-process scheduler (APScheduler thread in the FastAPI app):** rejected — dies with every
  Render restart/idle spin-down, and its run history would be our own logs, which the brief
  distrusts by design ("a platform that keeps its own run history").

## Why this over the others

The run history IS a deliverable, so the scheduler had to be a third party that keeps it. Separating
the operating layer (GH runners) from the serving layer (Render) means a failed cycle marks itself
failed in the Actions tab without touching the live URL. Odd-minute cron dodges top-of-hour runner
congestion. Cost/latency instrumentation lives in the ledger from day 1 because the architecture
notes must be computed from artifacts, and the day-2 checkpoint predictions are read off it.

## Assumptions and risks

Assumes GH cron actually fires ~6-hourly (it can lag 15–60 min; harmless at this cadence) and the
Supabase pooler accepts runner connections (verified: cycle #1 ran clean end-to-end, 50/50 fetches,
15/15 reconcile, 6.1 min). Risks, stated plainly: v1 trust events on website change are
`action='flagged'` — the materiality classifier (re-extract + field diff → refresh/quarantine) is
day-2 work, so a cosmetic page edit and a real change currently log the same way, honestly labeled
as unclassified; per-event inserts are one round trip each (~150/cycle), acceptable at 50 records,
a known batching TODO at 500; SMTP verification is impossible from runners (port 25 blocked) and
MillionVerifier credits are exhausted (verified −10), so cycles must not attempt email verification
until a fresh key lands — the verifier seam and a preflight will gate this.

## What would change this

If a cycle's wall-clock approaches the 6h cadence (or GH's 45-min job timeout) as the record count
climbs toward 500, batching of ledger writes and a split of observe/rebuild into separate jobs
happens before the cadence is touched. If GH cron proves unreliable across a day (>1 missed slot),
add a second schedule line as jitter tolerance. If reviewers need in-window evidence beyond the
Actions tab, `ops.runs` is exportable as-is — that, not screenshots, is the primary record.
