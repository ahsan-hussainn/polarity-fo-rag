# RAG documentation note — stack, chunking, embedding, retrieval; what works, what doesn't

Deliverable #6. Live at the submitted URL; run locally with `uvicorn pipeline.rag.app:app`.

## Stack

- **Data:** Supabase Postgres — one system provides structured (SQL), semantic (`pgvector`), and
  lexical (`tsvector`) retrieval (ADR-0002). The RAG reads only `gold.records` / `gold.rag_docs`.
- **Serving:** one FastAPI app (page + `/query` API + `/health`) on Render, stateless compute,
  auto-deploy on push (ADR-0014). Layers are separate modules: data (`db.py` + migrations), retrieval
  (`rag/retrieve.py`), generation (`rag/answer.py`), presentation (`rag/app.py` + `index.html`).
- **Models:** OpenAI `text-embedding-3-small` for embeddings, `gpt-4o-mini` for grounded answering.

## Chunking strategy

**One document per firm** — the gold record rendered to prose (name, location with the state spelled
out, founded year, AUM, thesis, description, sectors, primary contact). Records are short and
self-contained, so splitting them would only sever a firm from its own facts; at 50 documents the
"chunking" problem is really a rendering problem: what belongs in the searchable text. Contact emails
are deliberately *not* embedded — they come from the structured row at answer time, with their grade.

## Embedding model

`text-embedding-3-small` (1536-d) behind an `embed()` seam. The original plan was local
sentence-transformers; reversed (ADR-0013) because torch cannot fit a free-tier container and
deployability is a hard requirement. Whole-corpus embedding costs ~$0.0002, so re-indexing after every
dataset change is free in practice.

## Retrieval approach

**Hybrid with Reciprocal Rank Fusion:** dense cosine over pgvector and Postgres full-text ranking run
independently; a record's score is Σ 1/(60+rank) across the lists. Rank-based fusion needs no score
normalization or weight tuning, and a record strong on either signal surfaces. No ANN index at 50 rows
(exact scan is instant; the migration documents the `hnsw` upgrade point). Grounding: the answer model
receives *only* the retrieved records, must cite firms by name, must state each email's verification
grade in words, and answers "not in the dataset" rather than inventing; when nothing matches exactly it
says so and offers nearest records, clearly labeled.

## What works

- Verified-contact questions ("who runs X, can I email them?") answer with the grade attached — the
  dataset's honesty survives to the UI, where each source card shows the A–F badge.
- Hybrid rescues both failure modes at this corpus size: exact firm names (lexical) and paraphrases
  like "firms for wealthy families" (semantic).
- Failure handling: empty question → 400; no hits → explicit refusal; upstream exception → logged
  server-side, generic message to the client; UI renders errors without dying.

## What doesn't (known limits, stated plainly)

- **No true structured-filter leg.** "Family offices in California under $1B AUM" is answered by
  text-matching, not a SQL `WHERE`. Mitigated by rendering full state names and AUM into the indexed
  prose; a filter-extraction step feeding typed SQL predicates is the right fix.
- **Grounding is prompt-enforced, not verified post-hoc.** No automatic check that every cited firm was
  in the retrieved set. Spot-checked manually; a citation-verifier would make it measured.
- **No retrieval gold set yet.** Unlike the dataset (measured FP/FN), the RAG has no recall@k number —
  the honest gap in our own evidence standard, and the first improvement below.
- Render free tier sleeps when idle: first request after a quiet period takes ~30–60s.

## What I would improve, in order

1. A query→expected-record gold set with measured recall@k and a groundedness check (the same
   "measured, not asserted" bar the dataset already meets).
2. Filter extraction → SQL predicates (state, sector, AUM range) as a third retrieval leg.
3. Post-answer citation verification (every named firm must appear in the retrieved set).
4. Keep-warm ping or paid tier to remove the cold start.
