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
self-contained, so splitting them would only sever a firm from its own facts; at ~50 documents the
"chunking" problem is really a rendering problem: what belongs in the searchable text. Contact emails
are deliberately *not* embedded — they come from the structured row at answer time, with their grade.
Retrieval is release-gated to **qualifying family offices only**: all 50 gold rows are indexed, but
the gate serves only the 24 affirmed FOs — the 18 reclassified non-FOs (in `reclassified_firms.csv`)
and the 8 quarantined firms never surface. This is a family-office product, so a non-FO must not
appear in an answer at all, which is stronger than labeling it after the fact.

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

## Grounding is now enforced, not just prompted (ADR-0023)

An independent, deterministic post-generation check (`pipeline/rag/checkanswer.py`) gates every answer
before release: every email must belong to a retrieved record, no quarantined address may appear, a
stated count must match the dataset total, and a reclassified non-FO must be labelled as not a family
office. On failure the answer is repaired once, else refused — the verdict is logged and returned in
the API `verification` field, and shown in the UI. Measured over the deployed `answer()` path
(`python -m pipeline.cli rag-eval`, 8 adversarial cases): **grounded 8/8, expectation 7/8** — the one
miss is reported below, not hidden.

## What doesn't (known limits, stated plainly)

- **The check verifies structure, not semantics.** Emails, suppression, counts, and category honesty
  are checked deterministically; free-form *faithfulness* (a grounded-but-misleading sentence) is not.
  An LLM faithfulness judge is the next layer.
- **Out-of-scope queries that share a token with a firm** get answered about that firm ("weather in
  Zurich" → Marcuard). The answer is grounded but off-intent; `rag-eval` flags this case (7/8). A
  relevance/scope gate would close it.
- **No live-traffic groundedness number yet** — only the fixed adversarial suite. The intent
  classifier (ADR-0016) is still unmeasured.
- Render free tier sleeps when idle: first request after a quiet period takes ~30–60s.

## Post-submission upgrade (ADR-0016)

The original build answered every query shape with the same top-k retrieval and recited facts. Now:
a structured-output classifier routes **lookups** to direct name matching, **aggregates** to exact SQL
over `gold.records` (so "how many FOs in New York?" reports the dataset's true count, not a top-5
sample's), and **discovery** to hybrid retrieval with typed state/AUM constraints applied as hard
`WHERE` pre-filters. The answer layer now sees the *full* gold record, and outreach routing is computed
deterministically in Python from the email grades — a D-grade primary email routes the user to the
A-grade secondary contact, the office phone, or LinkedIn instead of dead-ending. Answers are shaped as
analyst advice: verdict first, why-each-firm, how to reach them with verification status in words, one
concrete next step.

## What I would improve, in order

1. An LLM faithfulness judge as a second gate behind the deterministic check (semantic, not just
   structural, grounding).
2. A query→expected-record gold set with measured recall@k on live traffic, plus intent-classifier
   accuracy (the "measured, not asserted" bar, extended from the adversarial suite to real queries).
3. A relevance/scope gate for out-of-scope queries (the one reported eval miss).
4. Keep-warm ping or paid tier to remove the cold start.
