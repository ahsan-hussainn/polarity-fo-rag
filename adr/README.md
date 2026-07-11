# Architecture Decision Records (ADRs)

This folder is the reasoning trail for the project. Every non-trivial decision, "why this and not that",
gets a short record here. The point is not process for its own sake. It is that this assessment is scored
on **visible thinking**: what we observed vs assumed, believed vs verified, and what would change our mind.
ADRs are where that lives.

## Rules we hold ourselves to

- **Write it when the decision is made, not after.** A record reconstructed at the end is a summary, not a
  decision. Commit the ADR near the commit that acts on it.
- **Record the options we rejected and why.** A decision with no alternatives is an opinion.
- **State what would change it.** If nothing would, it is not a real decision.
- **Keep it short.** A screen or less. Judgment, not volume.
- **Revising is allowed.** Supersede an ADR with a new one when evidence demands it. Do not silently edit
  history; add `Superseded by ADR-XXXX` to the old one.

## Format

Files are `NNNN-kebab-title.md`, four-digit sequential. Use [`_template.md`](./_template.md), or run
`/adr` in Claude Code to scaffold one. Keep the index in [`../CLAUDE.md`](../CLAUDE.md) in sync.

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](./0001-adopt-lightweight-adr-system.md) | Adopt a lightweight, self-built ADR system | Accepted |
| [0002](./0002-data-and-retrieval-store-supabase.md) | Supabase (Postgres + pgvector + tsvector) as data + retrieval store | Accepted |
| [0003](./0003-dataset-schema-mirrors-fo-max.md) | Dataset schema mirrors the FO-MAX sample, with a verifiability-first contact layer | Accepted |
| [0004](./0004-sourcing-strategy-public-regulatory-data.md) | Sourcing family offices from public regulatory + disclosure data (ADV, 990-PF, 13F) | Accepted |
| [0005](./0005-email-verification-and-honest-grading.md) | Email verification with a pluggable verifier and honest two-axis grading | Accepted |
| [0006](./0006-medallion-pipeline-in-postgres.md) | Medallion pipeline (bronze/silver/gold) lightweight in Postgres | Accepted |
