# ADR-0026: Out-of-scope relevance floor (deterministic scope gate)

- **Date:** 2026-07-22
- **Status:** Accepted
- **Relates to:** ADR-0023 (answer-verification floor — this is the "scope/relevance gate" its
  *What would change this* section named), ADR-0016 (intent routing)

## Context

**Observed (live, on the deployed app).** The RAG answered out-of-scope questions by pitching family
offices. "What is the capital of France?" returned a five-firm outreach list; "What is the weather in
Zurich today?" returned Marcuard. Both passed the ADR-0023 grounding check — because that check is
*structural*: it verifies the answer only cites retrieved firms/emails/counts, not that the query was
ever about the dataset. The failure was not a tuning miss but a structural gap across three layers:

1. **The intent classifier has no out-of-scope class** — `intent.py` is `Literal["discovery",
   "lookup", "aggregate"]` and the prompt defines `discovery` as "everything else," so any unrelated
   query is routed to discovery retrieval.
2. **`hybrid()` had no relevance floor** — the vector leg orders by cosine distance with no threshold,
   so for *any* embeddable query it returns 20 candidates; `scores` is never empty; discovery always
   returns k firms. The `if not hits` refusal in `answer()` was therefore dead code on the discovery
   path.
3. **The RRF score cannot serve as a floor** — RRF is rank-based, so the top hit of every query scores
   ~`1/(RRF_K+1)` ≈ 0.0164 regardless of true similarity (both the in-scope and out-of-scope live
   answers showed `score: 0.0164`). The signal RRF discards — the *raw cosine distance* — is the one
   that separates the classes.

**Measured (calibration probe, 12 queries).** Nearest-record cosine distance:

| Class | nearest distance | 
|---|---|
| in-scope (6 queries) | 0.239 – **0.498** |
| out-of-scope (6 queries) | **0.786** – 0.995 |

Clean separation, ~0.29 gap. The "weather in Zurich" collision (0.786) that defeats token-matching
sits firmly on the out-of-scope side.

## Decision

A **deterministic relevance floor** runs on every query before routing (`answer._route`, using
`retrieve.nearest_distance`): if the nearest qualifying record's cosine distance exceeds
`RELEVANCE_FLOOR` (or the index is empty), the query is out-of-scope → the answer layer returns an
honest refusal that states what the system *does* answer, with no sources and no generation.

- **Threshold pre-registered at 0.64** — the midpoint of the observed separation gap (worst in-scope
  0.498, best out-of-scope 0.786), chosen from the structure of the gap, **not** tuned to make the
  eval pass (mandate: set the threshold before measuring). Env-overridable (`RAG_RELEVANCE_FLOOR`).
- **Unfiltered by design** — the floor measures topicality over *all* qualifying records, independent
  of any state/AUM constraint, so "family offices in Ohio" stays in scope even if Ohio is sparse. The
  typed filters narrow; they do not decide scope.
- **Applies on every path**, not just discovery — this also closes the aggregate-path hole where an
  out-of-scope count ("how many countries in Africa") would be answered off the dataset total.
- **Measured, not just asserted** — `rag-eval` gains three clean out-of-scope cases (including one with
  no token collision) plus a false-positive guard (a restrictive in-scope filter that must NOT be
  refused).

## Options considered

- **Option A (chosen):** deterministic cosine-distance floor over the retrieved evidence.
- **Option B:** add an `out_of_scope` label to the LLM intent classifier and refuse on it. Rejected as
  the *primary* control: model-dependent and non-deterministic (the same objection ADR-0023 makes to a
  self-grading generator), and it introduces a false-positive path that could wrongly refuse real
  dataset questions. The deterministic floor is reproducible in the eval and cannot be talked out of a
  verdict. (An LLM scope hint could augment later, but it is not needed: the floor + the existing
  grounding check already cover the space, including adversarial injection.)
- **Option C:** threshold on the RRF fusion score. Rejected: rank-based, so it carries no absolute
  relevance signal — every query's top hit scores the same.
- **Option D:** do nothing, keep disclosing the gap. Rejected: the gap is broader than the disclosure
  framed it (it affects *any* out-of-scope query, not only token-colliding ones), and it is cheaply
  closable by a control consistent with ADR-0023.

## Why this over the others

Same principle as the answer-verification floor: a control must *change what ships*, deterministically
and visibly. Raw cosine distance is the one available signal that is independent of the generator,
reproducible in the eval, and cheap (one indexed `limit 1` query per request). It turns a documented
weakness into a measured control.

## Assumptions and risks

- The threshold is calibrated on 12 queries; it is a defensible midpoint, not a large-sample estimate.
  The wide gap (0.29) gives margin, but an unusual in-scope phrasing could sit high, or an out-of-scope
  query embedding-near a firm could sit low. The env override and the eval's false-positive guard exist
  for exactly this; the number should be revisited against real traffic.
- The floor judges *topicality*, not *answerability within topic* — an in-scope-but-absent firm
  ("Blackstone Family Office") still passes the floor (it is topical) and is handled by the existing
  refuse-don't-invent behavior, not here.
- One extra `limit 1` vector query per request. Negligible against the LLM round-trips, and it reuses
  the embedding already computed speculatively for discovery.

## What would change this

A measured out-of-scope miss/false-positive on real traffic that moves the threshold off 0.64; a
larger labelled calibration set replacing the 12-query midpoint; or an embedding-model change (the
distance scale is model-specific — recalibrate on any swap of text-embedding-3-small).
