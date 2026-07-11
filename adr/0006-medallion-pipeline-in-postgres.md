# ADR-0006: Medallion pipeline (bronze/silver/gold) implemented lightweight in Postgres

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

The pipeline needs to separate *raw observation* from *verified truth* and carry provenance/lineage, because
the brief requires per-cell verification ("where it came from and how you confirmed it") and a full
validation chain for 3 sample records. A medallion (bronze/silver/gold) architecture maps onto this naturally.

## Decision

Three schemas in the same Supabase Postgres (ADR-0002), not heavy data-lake tooling:

- **Bronze:** raw, immutable captures from each source. One row per fetch: `source`, `source_url`,
  `fetched_at`, `raw` (JSON/text). Append-only. This is the provenance backbone.
- **Silver:** normalized, deduplicated, entity-resolved, and **validated** records. Each high-value cell gets
  a paired `*_source` and `*_verification` (method + code + confidence). This is the validation layer.
- **Gold:** the curated 50 records that clear the actionability + verification bar, served to the RAG.

Kept distinct from all of this: a small, hand-labeled **validation ground-truth set** used to measure the
silver validators' false-positive / false-negative rates. This is NOT the gold table; the name collision
("gold layer" vs "gold set") is real and we avoid it by always calling the latter the "ground-truth set."

## Options considered

- **Lightweight medallion in Postgres (chosen).**
- **Flat single-table dataset:** rejected. No separation of raw vs verified, and provenance/lineage becomes an
  afterthought bolted on, which is exactly what the verification requirement punishes.
- **Heavy medallion (Spark / Delta Lake / orchestration framework):** rejected. Over-engineering for 50
  records; burns clock and signals the wrong thing. Medallion is a *logical* pattern here, not a tooling choice.
- **Files-on-disk stages:** rejected. Less queryable, weaker provenance, and it drifts toward a
  notebook/script shape the brief warns against.

## Why this over the others

The value of medallion here is lineage and epistemic separation (observed vs verified), not scale. Postgres
schemas give us that at the right weight, keep everything queryable for the RAG, and let a record's journey
from bronze to gold *be* the validation chain deliverable.

## Assumptions and risks

- Terminology collision (gold table vs ground-truth set) could confuse a reviewer; mitigated by naming.
- At 50 records this is arguably more structure than strictly needed; justified because the lineage is itself
  a graded deliverable, not just plumbing.

## What would change this

A shift to large-scale or heavily unstructured data would justify real data-lake tooling. Nothing at this
scale should.
