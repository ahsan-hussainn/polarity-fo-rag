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

**Measured (two probes).** Nearest-record cosine distance:

| Class | nearest distance |
|---|---|
| prototypical in-scope (6 queries) | 0.239 – 0.498 |
| clearly out-of-scope — weather, geography, sport, code (6 queries) | 0.786 – 0.995 |

For these two classes the separation is clean (~0.29 gap), and the "weather in Zurich" collision
(0.786) that defeats token-matching sits firmly on the out-of-scope side. **But a follow-up adversarial
probe (run before this ADR was accepted, reported not hidden) shows the boundary is NOT clean once you
leave the prototypical set:**

| Class | nearest distance | at floor 0.64 |
|---|---|---|
| near-domain out-of-scope — "venture capital firms", "private equity firms in NY", "wealth management firms", "RIAs in Texas" | 0.55 – 0.69 | **4 of 8 leak** (answered as FOs) |
| oblique but genuine in-scope — "who backs deep tech founders", "climate direct deals" | 0.44 – 0.79 | **2 of 4 false-refused** |

These two bands **overlap**, so no single global threshold separates them: lower it to stop
false-refusing real questions and more near-domain queries leak; raise it and more real questions are
refused. The reason is structural — cosine distance to the nearest FO record conflates two questions
it cannot tell apart: *(a) is this about the wealth-management domain at all?* (distance answers this
well) and *(b) is this about a **family office** specifically, vs. a VC / PE / hedge fund / RIA?*
(distance cannot — those entities embed right next to family offices). The product's identity is (b).

## Decision

A **deterministic relevance floor** runs on every query before routing (`answer._route`, using
`retrieve.nearest_distance`): if the nearest qualifying record's cosine distance exceeds
`RELEVANCE_FLOOR` (or the index is empty), the query is out-of-scope → the answer layer returns an
honest refusal that states what the system *does* answer, with no sources and no generation.

**Scope of this decision (deliberately bounded).** This is the **first layer** of scope control — a
*pure* out-of-scope guard that reliably refuses queries not about the wealth-management domain at all
(weather, geography, sport, general knowledge, unrelated counts). It is **not** the complete answer to
"only respond about family offices": the measured overlap above means it does not reliably separate
near-domain non-FO entities (VC/PE/hedge funds/RIAs) from genuine FO questions. That separation needs a
second layer (see *What would change this*) and is tracked as follow-on work, not claimed here.

- **Threshold pre-registered at 0.64** — the midpoint of the prototypical separation gap (worst
  in-scope 0.498, best clearly-out-of-scope 0.786), chosen from the structure of the gap, **not** tuned
  to make the eval pass (mandate: set the threshold before measuring). Env-overridable
  (`RAG_RELEVANCE_FLOOR`). The follow-up probe shows this number is right for the pure-OOS job and
  cannot be right for the near-domain job — a threshold move cannot fix the latter (the bands overlap).
- **Unfiltered by design** — the floor measures topicality over *all* qualifying records, independent
  of any state/AUM constraint, so "family offices in Ohio" stays in scope even if Ohio is sparse. The
  typed filters narrow; they do not decide scope.
- **Applies on every path**, not just discovery — this also closes the aggregate-path hole where an
  out-of-scope count ("how many countries in Africa") would be answered off the dataset total.
- **Measured, not just asserted** — `rag-eval` gains three clear out-of-scope cases (including one with
  no token collision) plus a false-positive guard (a restrictive in-scope filter that must NOT be
  refused). The eval does **not** yet assert on the near-domain cases, because the current single-signal
  design would not pass them — they are the acceptance test for the second layer.

## Options considered

- **Option A (chosen):** deterministic cosine-distance floor over the retrieved evidence.
- **Option B:** add an `out_of_scope` label to the LLM intent classifier and refuse on it. Rejected as
  the *primary* control: model-dependent and non-deterministic (the same objection ADR-0023 makes to a
  self-grading generator), and it introduces a false-positive path that could wrongly refuse real
  dataset questions. The deterministic floor is reproducible in the eval and cannot be talked out of a
  verdict. (An entity-intent classifier — anchor-centroid preferred over LLM — is in fact needed as the
  *second* layer to separate near-domain non-FO entities the floor cannot; it augments the floor, it
  does not replace it. See *What would change this*.)
- **Option C:** threshold on the RRF fusion score. Rejected: rank-based, so it carries no absolute
  relevance signal — every query's top hit scores the same.
- **Option D:** do nothing, keep disclosing the gap. Rejected: the gap is broader than the disclosure
  framed it (it affects *any* out-of-scope query, not only token-colliding ones), and it is cheaply
  closable by a control consistent with ADR-0023.

## Why this over the others

Same principle as the answer-verification floor: a control must *change what ships*, deterministically
and visibly. Raw cosine distance is the one available signal that is independent of the generator,
reproducible in the eval, and cheap (one indexed `limit 1` query per request). It closes the pure
out-of-scope case fully and cheaply — the right first layer. It does not, on its own, close the
near-domain case; the honesty of this ADR is in stating that boundary rather than implying one number
solved the whole "only answer about family offices" goal.

## Assumptions and risks

- **Near-domain leakage is real and measured (4/8), not hypothetical.** Queries about adjacent finance
  entities (VC, PE, hedge funds, RIAs) can sit below the floor and be answered as if about family
  offices. A single cosine threshold cannot close this — it is the motivation for the second layer.
- **This gets worse as the dataset grows.** The near-domain queries already sit at 0.55–0.62 with only
  24 records. Stage 2 takes the corpus to 500: a denser embedding space means the nearest neighbour to
  *any* query is closer on average, so more near-domain queries fall below any fixed floor. The floor
  should be treated as drift-prone and monitored, not set-and-forget.
- The threshold is calibrated on a small, prototypical set; it is a defensible midpoint for the pure-OOS
  job, not a large-sample estimate. The env override and the eval's false-positive guard exist for this;
  the number must be revisited against real traffic.
- The floor judges *topicality*, not *answerability within topic* — an in-scope-but-absent firm
  ("Blackstone Family Office") still passes the floor (it is topical) and is handled by the existing
  refuse-don't-invent behavior, not here.
- Embedding-model-specific: the distance scale is a property of text-embedding-3-small — recalibrate on
  any embedding swap.
- One extra `limit 1` vector query per request. Negligible against the LLM round-trips, and it reuses
  the embedding already computed speculatively for discovery.

## What would change this — the second layer (planned)

The distance floor answers "is this in the domain?" A robust "only answer about family offices" needs a
control that answers "is this about a *family office* vs. an adjacent entity?", which distance cannot:

1. **Entity-intent disambiguation** — an anchor-centroid classifier (embed a handful of canonical
   "this is a family-office question" vs. "this is a not-an-FO-entity question" phrases; classify by
   nearest centroid). Deterministic, cheap, and it learns the boundary *direction* rather than a
   radius, so it can separate the overlapping bands the floor cannot. (A small LLM classifier is the
   less-preferred alternative — model-dependent, per the ADR-0023 objection.)
2. **Boundary observability** — log every query's nearest distance + decision so the boundary can be
   recalibrated from real traffic and drift (as the corpus grows to 500) is caught, not discovered by a
   user. This is what makes the gate mature for an *operated* system.
3. The near-domain `rag-eval` cases become passing acceptance tests once the second layer lands.

Until then, this ADR records a bounded first layer with its limits stated, not a solved problem.
