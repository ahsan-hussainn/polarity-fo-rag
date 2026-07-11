# ADR-0007: Pipeline architecture — staged medallion DAG, over-discover then filter

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

ADR-0006 set the storage layers (bronze/silver/gold). This decides the *flow* that populates them and how a
record earns promotion to the final 50. Realities from ADR-0004/0005 shape it: firm-level data from ADV/990-PF
is strong and verifiable; principal name+title is a separate enrichment step (not in ADV bulk); emails verify
only with honest grading; and enrichment sources (websites, filings) fail unpredictably.

## Decision

A **7-stage DAG** that **over-discovers then filters** to the best 50, each stage idempotent and writing
provenance, orchestrated by a lightweight Python CLI (not a DAG framework).

1. **Discover** — ADV bulk (name/free-text/client-mix filters) + 990-PF (ProPublica) -> bronze candidate pool
   (target a few hundred, not 50).
2. **Resolve & dedup** — normalize names/addresses, merge cross-source duplicates -> silver entities.
3. **Firm enrich** — fetch firm website (raw -> bronze): investment thesis, description, sectors, team page,
   and any real email on the domain (to establish the email pattern). 13F holdings for signals. -> silver.
4. **Principal ID** — select the best decision-maker (CIO/MD/President/Partner, not a back-office title) from
   website / 990-PF XML / ADV individual filing; capture LinkedIn URL if publicly findable. -> silver.
5. **Contact intelligence** — infer principal email from the domain pattern; run the pluggable verifier
   (syntax+MX -> SMTP RCPT + per-domain catch-all probe -> Reoon API fallback); assign grade+code+explanation
   (ADR-0005). Firm phone from ADV; principal direct phone usually an honest blank. -> silver.
6. **Validate & score** — every high-value cell carries `*_source` + `*_verification`; compute per-record
   actionability and completeness scores; measure the validators against a hand-built **ground-truth set** of
   known valid / invalid / catch-all emails to get real false-positive/false-negative rates. -> silver.
7. **Promote** — rank by actionability + verification quality, promote the top 50 that clear the bar to gold;
   export CSV/XLSX.

### Principles enforced in code

- **Over-discover, filter down.** Attrition is absorbed by the funnel, never by lowering standards or guessing
  to hit 50. Report the funnel (discovered -> enriched -> shippable) as an honest signal.
- **LLM extracts, never invents.** The model only structures *fetched real content*; it never generates a fact
  (email, name, AUM) that gets marked verified. Every high-value cell traces to a source and is verified first.
- **Graceful degradation.** A stage failing a record yields an honest blank, not a crash and not a fabrication.
- **Idempotent + provenance-carrying.** Bronze is immutable; re-runs don't duplicate. Designed so the stages
  can later be scheduled unattended (Stage 2 agent) without a redesign.

### Orchestration

A Python package + CLI, one command per stage over the Postgres medallion schemas, plus `run all`.
Layout: `pipeline/{bronze,silver,gold,verify}/*.py`, `db.py`, `config.py`, `cli.py`.

## Options considered

- **Staged CLI DAG, over-discover then filter (chosen).**
- **Heavy orchestrator (Airflow / Prefect / Dagster):** rejected. Over-engineering for 50 records; revisit only
  if Stage 2 demands real scheduling at scale.
- **One monolithic script:** rejected. No layer separation (a graded requirement), hard to re-run or verify per
  stage, and drifts toward the notebook/tutorial shape the brief rejects.
- **Discover exactly 50, then enrich:** rejected. Attrition would leave holes and create pressure to guess to
  fill quota. Over-discovery is what lets us hit 50 *actionable + verified* records honestly.

## Why this over the others

Staged + idempotent gives the layer separation that is scored, reproducibility (real git history, re-runnable
stages), and provenance (a record's bronze->gold journey *is* the validation chain deliverable). Over-discovery
is the mechanism that reconciles "exactly 50 records" with "never fabricate."

## Assumptions and risks

- Website enrichment (Stage 3) and principal ID (Stage 4) are the fragile, variable stages; graceful
  degradation mitigates, but they cap real coverage.
- A few-hundred candidate pool is *assumed* enough to yield 50 after attrition. Validate empirically; if not,
  widen discovery (more name patterns, more sources) rather than lower the bar.
- LLM extraction quality on messy HTML is uncertain; always verify extracted high-value cells against source.

## What would change this

Worse-than-expected attrition -> widen discovery, do not lower standards. If Stage 2 requires true
unattended scheduling/scale, introduce a real orchestrator then, as its own decision.

## Deferred (their own future ADRs)

- ADR-0008: specific LLM/model for extraction.
- Later: RAG chunking, embedding model, retrieval + serving, once the gold schema is frozen.
