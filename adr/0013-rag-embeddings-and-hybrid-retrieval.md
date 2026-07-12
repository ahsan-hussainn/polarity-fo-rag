# ADR-0013: RAG index — OpenAI embeddings + hybrid (pgvector + tsvector) retrieval

- **Date:** 2026-07-13
- **Status:** Accepted (reverses the locked-stack "local sentence-transformers" choice; see below)

## Context

The Micro-RAG must answer questions over the gold dataset ("family offices investing in healthcare in
California", "who runs investments at Oak Hill and is their email verified") with grounded, cited
answers — and it must be **deployable**, not a notebook. Two facts shape the index:

- Observed: the corpus is tiny — **59 gold documents** (one prose record per firm). At that size an
  exact vector scan is instant; an approximate-nearest-neighbour (ANN) index buys nothing yet.
- Observed (deployment constraint): the locked stack said "local sentence-transformers embeddings," but
  `sentence-transformers` pulls in `torch` (~2 GB resident). Free web-service tiers (Render/Railway/Fly)
  give **256–512 MB RAM** — the model would not load, so local embeddings would make the deploy *fail*,
  contradicting the one hard requirement. The build machine also has neither installed.
- Observed: an OpenAI key is already in use for extraction; **text-embedding-3-small** (1536-d) costs
  ~$0.0002 for all 59 docs and needs no model in the container.

## Decision

Embed each gold record's prose with **OpenAI `text-embedding-3-small`**, stored in **Supabase pgvector**
(`gold.rag_docs`, migration 0006), behind an `embed()` seam so the provider is swappable. Retrieve
**hybrid**: dense cosine (pgvector) fused with lexical Postgres full-text (`tsvector`) via **Reciprocal
Rank Fusion (RRF)**. No ANN index at 59 rows (documented in the migration; add `hnsw` when the corpus
reaches thousands).

## Options considered

- **OpenAI embeddings + hybrid RRF (chosen).**
- **Local sentence-transformers (`all-MiniLM-L6-v2`, 384-d):** free and offline, the original plan.
  Rejected as primary purely on deployability — torch will not fit a free tier, and the differentiator
  is the dataset/validation, not owning the embedder. Kept as a seam swap for a self-hosted run.
- **Vector-only or lexical-only retrieval:** rejected. Pure vector misses exact firm names / sector
  terms; pure lexical misses paraphrase ("wealthy families' investment firm" ≠ "family office"). The
  corpus is small and heterogeneous, exactly where hybrid earns its keep.
- **Weighted score blend instead of RRF:** rejected as the default — it needs per-corpus weight tuning
  we cannot yet justify; RRF is rank-based, parameter-light, and robust out of the box.

## Why this over the others

The deployable constraint is non-negotiable and it eliminates local torch on a free tier, so the honest
move is OpenAI embeddings behind a seam — cheap, tiny to ship, and reversible. Hybrid + RRF is the
low-risk retrieval choice for a small, name-heavy corpus: it needs no tuning and degrades gracefully
(if one signal is weak, the other still ranks). Keeping both signals in one Postgres table (dense
column + generated `tsvector`) means a single round-trip, no extra infrastructure.

## Assumptions and risks

- Assumption: 1536-d exact scan stays instant at this scale. True for tens–low-thousands of rows; the
  migration notes the `hnsw` upgrade point.
- Risk: embedding provider lock-in / cost at scale. Mitigated by the `embed()` seam (swap to local ST or
  another API) and by the trivial corpus cost.
- Risk: RRF can under-weight a strongly-relevant single-signal hit. Acceptable at K≈5 over 59 docs;
  revisit with weights only if retrieval quality measurably suffers.
- The grounding step (separate) must answer only from retrieved records and cite them, or the honesty
  the dataset earns is lost at the last mile — enforced in the answer prompt, not here.

## What would change this

A corpus in the thousands adds an `hnsw` index; tens of thousands or a privacy requirement would justify
paying the deploy cost of local embeddings (bigger host) via the seam. If hybrid retrieval quality is
measurably poor on a held-out query set, move from RRF to a tuned weighted blend or a reranker.
