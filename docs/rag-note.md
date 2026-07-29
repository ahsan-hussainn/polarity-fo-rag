# RAG documentation note — stack, chunking, embedding, retrieval; what works, what doesn't

Deliverable #6. Live at the submitted URL; run locally with `uvicorn pipeline.rag.app:app`.

**Counts here are stamped to the pre-window sign-off (2026-07-22) unless marked otherwise.** The set
changes every operating cycle; regenerate live figures from `python -m pipeline.cli reconcile` or
`GET /stats`. Stage 2 additions (the `fit_rank` extension and the goal agent) are in their own
section near the end.

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
Retrieval is release-gated to **qualifying records only**: every held row is indexed, but the gate
serves only records whose `release_state` is `qualifying`; reclassified non-FOs and quarantined firms
never surface. Under ADR-0028 "qualifying" is three labelled categories rather than two, so a record
that is *counted* but is not a standalone family office (an advisory firm with an evidenced FO
practice) is retrievable **and carries its label on every surface** — the answer prompt, the
deterministic category check, the UI card, and the per-category `/stats` split. Presenting one as
simply "a family office" is a blocking failure, not a warning.

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
- **Out-of-scope queries that share a token with a firm** used to get answered about that firm
  ("weather in Zurich" → Marcuard) — grounded but off-intent. **Closed** by ADR-0026's deterministic
  cosine-distance scope floor, which refuses before retrieval rather than hoping the prompt declines.
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

## Stage 2: what the retrieval layer gained

**`fit_rank` — the new retrieval capability** (`pipeline/rag/fit.py`, ADR-0030), served at
`POST /fit` and available to the agent as a tool. Stage 1 retrieval answers "which records match
this query." `fit_rank` answers "rank the *whole* qualifying set against this investor mandate, and
say how much to trust each ranking." It is deterministic — the only model call is embedding the
mandate — and every rank is a weighted sum of named, inspectable components shipped in the output.

The design decision worth the space: **the confidence tier comes from evidence *presence*, not score
magnitude.** A record can sit at the top on document similarity and still be labelled
`insufficient_evidence` because nothing in it evidences the mandate. That is the difference between
a ranking a buyer can act on and one that merely looks confident, and it is what lets the agent
abstain instead of laundering a high score into a claim.

**The goal agent** (`/agent`, ADR-0031) uses retrieval as a tool rather than being a retrieval
front-end: it decomposes a goal, calls tools repeatedly, compares, and returns a structured answer
with per-pick confidence and explicit abstentions. Six tools, one of which (`record_history`) reads
the operating ledger and is the only way to ask what *changed* rather than what *is*. The release
gate around it is code, not prompt: grounded firms only, verbatim emails, tier ceilings, no
recommending firms the system holds but does not release.

## What I would improve, in order

1. An LLM faithfulness judge as a second gate behind the deterministic check (semantic, not just
   structural, grounding) — a grounded-but-misleading sentence still passes today.
2. A query→expected-record gold set with measured recall@k on live traffic, plus intent-classifier
   accuracy (the "measured, not asserted" bar, extended from the adversarial suite to real queries).
3. Firm-name grounding in `checkanswer`. It is listed in the module's own docstring history but was
   never implemented — free-text firm-name detection is noisy, so firm honesty currently rests on
   the email checks plus the blocking category check. Stated because the docstring used to imply
   otherwise.
4. `fit_rank` weights are pre-registered, not tuned. They are defensible and inspectable but have
   never been measured against a preference set, because none exists.
5. Keep-warm ping or paid tier to remove the cold start.
