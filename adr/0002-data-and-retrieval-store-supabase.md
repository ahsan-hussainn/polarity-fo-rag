# ADR-0002: Supabase (Postgres + pgvector + tsvector) as data + retrieval store

- **Date:** 2026-07-11
- **Status:** Accepted

## Context

Observed (fact): The task requires *both* structured and semantic retrieval, a deployable (non-localhost)
architecture, and clean separation between data, retrieval, and presentation layers. The data itself
(family office records) is highly relational and filter-heavy: the dominant query shape is structured, e.g.
`sector = real estate AND country = US AND has_verified_email = true`, alongside semantic queries over free
text like thesis and description.

Assumed (unverified): dataset scale stays small (50 validated records, low hundreds of chunks). No need for
large-scale approximate-nearest-neighbor performance.

## Decision

Use Supabase as the single hosted store: Postgres for structured columns and SQL filters, `pgvector` for
semantic similarity, and Postgres `tsvector` for lexical/full-text. Retrieval is a hybrid over all three.

## Options considered

- **Supabase / Postgres + pgvector + tsvector (chosen):** one deployed system covers structured, semantic,
  and lexical retrieval.
- **Pinecone (or other pure vector DB) + separate SQL store:** rejected for this data. Pure vector means we
  still need a relational store for the structured filters, so two systems to deploy and keep in sync. Its
  scale advantage is irrelevant at 50 records.
- **Qdrant with payload filtering:** closer (structured filters on metadata), but still not relational;
  counts, joins, and aggregations over investor attributes are awkward, and it is a second datastore.

## Why this over the others

The data is relational and the queries are filter-heavy, so a relational store is the honest home. Supabase
folds semantic and lexical into that same store, satisfying "structured AND semantic" with one deployed
system and the fewest moving parts, which also matters for the Stage 2 "operate it unattended" requirement.

## Assumptions and risks

- Risk: if the real task data turns out to be a large unstructured-text corpus, a dedicated vector DB would
  win. Low likelihood given the schema is tabular investor records.
- Risk: Supabase free-tier limits (row caps, cold starts). Acceptable at this scale; verify before the demo.

## What would change this

A shift to large-scale or heavily unstructured data, or free-tier limits that block the live demo, would
push us to a dedicated vector DB plus a lightweight relational store.
