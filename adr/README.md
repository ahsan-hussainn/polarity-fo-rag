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
| [0007](./0007-pipeline-architecture-staged-medallion-dag.md) | Pipeline architecture: staged medallion DAG, over-discover then filter | Accepted |
| [0008](./0008-extraction-llm-openai-behind-pluggable-seam.md) | OpenAI (gpt-4o-mini) as the extraction LLM, behind a provider-agnostic seam | Accepted |
| [0009](./0009-silver-schema-firm-and-people-split.md) | Silver schema: firm + person split, believed vs verified cells | Accepted |
| [0010](./0010-email-verification-api-millionverifier.md) | Email verification via API (MillionVerifier) behind the verifier seam | Accepted |
| [0011](./0011-gold-record-shape-and-primary-contact.md) | Gold record shape: FO-MAX-mirroring, primary contact by seniority | Accepted |
| [0012](./0012-fo-max-parity-enrichment.md) | FO-MAX parity enrichment: held-data fields + search-assisted LinkedIn | Accepted |
| [0013](./0013-rag-embeddings-and-hybrid-retrieval.md) | RAG index: OpenAI embeddings + hybrid (pgvector + tsvector) retrieval | Accepted |
| [0014](./0014-rag-serving-fastapi-and-render.md) | RAG serving: one FastAPI app (page + API), deployed on Render | Accepted |
| [0015](./0015-gold-curation-gate.md) | Gold curation gate: entity validity is validated, not assumed | Accepted |
| [0016](./0016-rag-intent-routing-and-actionable-answers.md) | RAG: intent routing, typed filters, actionability-shaped answers | Accepted |
| [0017](./0017-rag-latency-streaming-and-connection-reuse.md) | RAG latency: streaming answers, connection reuse, parallel calls | Accepted |
| [0018](./0018-ui-coverage-desk-presentation.md) | Presentation: "Coverage Desk" UI designed around grade + routing | Accepted |
| [0019](./0019-release-and-quarantine-policy.md) | Release and quarantine policy for vendor-rejected contact data | Accepted |
| [0020](./0020-affirmative-entity-standard.md) | Affirmative entity standard and identity resolution | Accepted |
| [0021](./0021-decision-maker-evidence-standard.md) | Decision-maker evidence standard | Accepted |
| [0022](./0022-contact-selection-allocation-authority.md) | Contact selection: allocation authority first, conditioned on entity category | Accepted |
