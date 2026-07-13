# ADR-0016: RAG answer layer — intent routing, typed filters, and actionability-shaped answers

- **Date:** 2026-07-13
- **Status:** Accepted

## Context

Post-submission review of the RAG layer found three real problems:

1. **The answer layer saw a fraction of gold.** `retrieve.hybrid()` selected ~13 of the record's
   fields; AUM, firm phone, corporate LinkedIn, the description, the secondary contact chain, and the
   per-email plain-English explanations never reached the model. Worst case: records whose primary
   email is D but whose *secondary* is A read as dead ends when they are not.
2. **Answers recited facts instead of advising.** No verdict, no prioritization, no next step — a
   fact dump per firm, when the brief's own definition of an actionable record ("whom to contact, why
   them, why now") is a ready-made answer template.
3. **One retrieval mode served three query shapes.** Top-k retrieval cannot answer an aggregate
   honestly: asked "how many FOs in New York?", the model sees 5 records and reports a number that is
   grounded in the sample and wrong about the dataset — a grounding failure disguised as honesty.

## Decision

Three changes, one seam each:

- **Intent routing** (`pipeline/rag/intent.py`): a structured-output classification call extracts
  `{intent: discovery|lookup|aggregate, firm_name, state, sector_term, min/max_aum_usd}`.
  Lookups match the named firm directly (no embedding round-trip); aggregates run **exact SQL** over
  `gold.records` and pass the true dataset count to the model; discovery stays hybrid. The classifier
  **fails open** to unfiltered discovery — a broken classifier must never take retrieval down.
- **Typed filters as pre-filters, not ranked legs**: state and AUM constraints become WHERE clauses
  on both ranking queries. If the user asked for California, a Texas firm is wrong, not lower-ranked.
  Sector deliberately stays semantic/lexical (uncontrolled vocabulary; a hard filter would silently
  drop true matches) except in the aggregate path, where keyword matching is used and *labelled
  approximate* to the model. When hard filters match nothing, retrieval falls back to unfiltered and
  the model is told the results are nearest matches only.
- **Actionability-shaped answers**: retrieval now returns the full record; outreach channel routing is
  computed **in Python** (`answer.best_channel`), not left to the model — A/B email → email that
  contact; else A/B secondary → route through them, saying why; else office phone; else LinkedIn.
  The system prompt mandates verdict-first, why-them-per-firm, how-to-reach with verification status
  in plain words, and one concrete next step. The UI source cards carry AUM, location, title, phone,
  LinkedIn, ADV filing link, and a best-channel chip.

## Why this over the others

- Channel routing in Python keeps a correctness-critical judgment deterministic and testable; the
  model only phrases it. This is the same principle as provenance stamping in extraction (ADR-0008):
  the LLM never decides what we can compute.
- SQL for aggregates is the only honest option; prompt engineering cannot make a 5-record window
  count 50 records.
- An extra classification call (~1s, ~$0.0001) per query is the cost; acceptable against answering
  count questions wrongly.

## Assumptions and risks

- The classifier can mis-extract a filter (e.g. hallucinate a state). Mitigations: conservative
  extraction rules, fail-open on error, and the nearest-match fallback when filters over-constrain.
  Not yet measured — the retrieval gold set (rag-note "what I'd improve" #1) now has one more job.
- Two LLM calls per query on Render free tier adds latency (~1s). Acceptable.
- `by_name` uses ILIKE containment; an ambiguous fragment returns up to 3 candidates and the model
  disambiguates in prose.

## What would change this

A measured retrieval gold set covering all three intents (the next build); persistent low classifier
accuracy would argue for heuristic pre-routing (regex for "how many/largest") before the LLM call.
