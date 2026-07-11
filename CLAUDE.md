# CLAUDE.md — project context

Family Office Dataset + Micro-RAG. PolarityIQ Differentiator, Stage 1, Task 1.
Read this first each session. Keep it current.

## The one thing that matters most

**The dataset is the product; the pipeline is the delivery mechanism.** A sophisticated RAG on a thin or
unverified dataset fails, flatly. Effort goes to the *data* first: real family offices, actionable contact
intelligence, and per-cell verification. The RAG is how a client uses that data, not the point of it.

## Hard constraints (from the assessment brief)

- **50 real family office records**, produced by an **automated pipeline** (discover -> enrich -> validate).
  Manual spot-checks, judgment, and validation notes are allowed; **manual compilation is not.**
- **Dataset is pass/fail.** Scored on (1) actionability: could a fund manager act on this record today?
  and (2) verification: every high-value cell carries its basis (source + method). Reviewers sample-check.
- **Honesty beats coverage-theater.** An honest blank marked "could not verify" scores as candor. A guessed
  value dressed as verified is **disqualifying**. But a mostly-blank file is not sellable and also fails.
- **Visible reasoning or it is not evaluated.** Observed vs assumed, believed vs verified, what would change
  the conclusion. This lives in `adr/` and in honest commits, not a final polish pass.
- **Real git history.** Do not squash/strip/recreate history. No ZIP submission. Build incrementally.
- **Production-shaped RAG.** Deployable (not localhost/notebook), structured + semantic retrieval, grounding
  discipline (refuse when ungrounded), failure handling, layer separation, a live URL.
- **Ethics/legal:** principal emails/phones are PII. Source only from legitimately public data; mark honest
  blanks rather than guess.

## Deliverables

1. CSV/XLSX of 50 validated records. 2. Methodology summary. 3. Three records with a full validation chain.
4. Public/shared GitHub repo (share with optimize@falconscaling.com) with the full pipeline + real history.
5. Live URL doing real queries on real results. 6. Doc note (stack, chunking, embedding, retrieval,
what works/doesn't, improvements). Plus a half-page build session summary (actual hours, no padding).

## Stack (see ADRs for the why)

- Data + retrieval: **Supabase** — Postgres (structured) + `pgvector` (semantic) + `tsvector` (lexical). [ADR-0002]
- Schema: **mirrors FO-MAX sample**, extended with per-cell `*_source` + `*_verification`. [ADR-0003]
- Reasoning trail: **self-built lightweight ADRs**; `/adr` to add one. [ADR-0001]
- Pipeline / RAG API / UI / embedding model: **not yet decided** (record an ADR when chosen).

## Reference: FO-MAX sample schema (32 cols)

Entity: name, validation period, data completion score, description, investment thesis, investing sectors,
domain, website, URL quality, corporate LinkedIn, street/city/state/country.
Contact: first/last/full name, job title, location, LinkedIn, **primary email + validation code +
code explanation + quality assessment + phone**, then the same block for a **secondary email**.
(In the sample, all contact-intelligence cells are `Hidden` — that redaction marks the paid value.)

## Architecture Decision Records

| # | Title | Status |
|---|-------|--------|
| [0001](./adr/0001-adopt-lightweight-adr-system.md) | Adopt a lightweight, self-built ADR system | Accepted |
| [0002](./adr/0002-data-and-retrieval-store-supabase.md) | Supabase as data + retrieval store | Accepted |
| [0003](./adr/0003-dataset-schema-mirrors-fo-max.md) | Dataset schema mirrors FO-MAX, verifiability-first | Accepted |
