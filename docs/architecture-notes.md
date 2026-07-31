# Architecture notes

**DRAFT — day 3 (2026-07-29).** Structure and decisions are settled; every figure marked `[regen]`
is regenerated from the artifact before submission (`reconcile`, `ops-export`, `/stats`), never
hand-carried. The brief asks for two to three pages total, so each section stays short and every
claim points at a file, a table, or a run.

---

## 1 · Retrieval extension

**What was added: `fit_rank`** (`pipeline/rag/fit.py`, ADR-0030), served at `POST /fit` and
available to the agent as a tool.

Stage 1 retrieval answers *"which records match this query"* — lookup, exact filters, hybrid top-k.
`fit_rank` answers a different question: *"rank the whole qualifying dataset against this investor
mandate, and tell me how much to trust each ranking."* What the Stage 1 system could not do is
produce a **defensible ordering with a per-record confidence**, because ranking by embedding
distance alone cannot distinguish a firm that states a healthcare mandate from one that merely
sounds like it might.

The design decision that matters: **the confidence tier is a function of evidence *presence*, not
score magnitude.** A record can rank highly on document similarity and still be labelled
`insufficient_evidence`, because nothing in it evidences the mandate. That is what lets the agent
abstain honestly instead of laundering a high score into a confident claim — the exact failure the
brief warns about ("a strong system does not confidently launder weak evidence into a clean
answer").

Deliberately deterministic: the only model call is embedding the mandate. Every component
(semantic affinity, stated-sector evidence, record confidence, reachability, signal recency) ships
in the output with pre-registered weights, so a user can see *why* a firm ranks where it does.

**Considered and rejected:** a learned re-ranker (no labelled relevance data, and unexplainable
ranking is unsellable to a buyer who must justify an approach list); an LLM-as-judge scorer
(ADR-0023's objection — a release-relevant judgement that can be talked out of a failure);
sector-classification of every record up front (would have manufactured labels where the source text
supports none, which is the same laundering in a different place). Two measured failures shaped the
scorer — a generic-token stoplist and the `"lower-middle-market"` → `["lower","middle"]` regression
on the verbatim Goal 2 mandate; both are detailed under §6 rather than repeated here.

### Source classes: what each can and cannot establish

| source | can establish | cannot establish | material blind spot |
|---|---|---|---|
| **SEC Form ADV** (bulk feed) | legal entity, CRD, AUM, client mix, address, phone, filing date | what the firm *is* (name and structure are self-reported marketing) | **single-family offices are exempt from registration** — measured: 0 SFOs across 341 ADV-sourced candidates |
| **State ADV feed** | same shape, smaller advisers | same | same registry, same blind spot — this is one source wearing two hats |
| **Firm websites** | what the firm says about itself: FO practice, thesis, team, published contacts | truth of the claim — a wealth manager publishes the same words a family office does | ~49% of queued candidates carry no usable firm domain; bot-shielding rising |
| **SEC 13F** (ADR-0035) | entity existence, exact registered name, CIK/EIN, address, phone, institutional scale | anything about what the firm is — no client mix, no self-description, **no website** | reaches ADV-exempt SFOs (Duquesne), but proof rate is low: the privacy that exempts them also keeps them off the web |
| **IAPD live** (ADR-0036) | current filing date, registration scope, registered name | anything historical beyond the current record | CRD-keyed only; 13F candidates are outside its reach by construction |
| **MillionVerifier** | deliverability of an address — the `VERIFIED_API` grades in the shipped set were produced pre-window (Stage 1), while the credential was live | whether an address belongs to the named person | **credential has returned HTTP 403 on every operating-window run** — the cycle records the 403 each run rather than re-claiming the capability, so no address was (re)graded during the window |

The load-bearing split, and it is the brief's own framing: **ADV surfaces a candidate; the firm's
own site establishes identity.** That is exactly how the inclusion gate scores, and why an affirm
requires published self-evidence (ADR-0033).

---

## 2 · Agentic vs deterministic boundary

**Agentic — the model decides what happens next:** which tools to call, in what order, how many
times, when it has enough, and how to compose the final answer (`pipeline/agent/loop.py`). Given
"find LPs for a healthcare fund," nothing in the code dictates that it should call `fit_rank` before
`structured_search`, or that it should deepen a promising firm with `get_record`. That is genuine
planning over a goal, and it is where a model earns its place: the decomposition differs per goal in
ways a fixed pipeline would have to enumerate in advance.

**Deterministic, deliberately — code decides what may be claimed:**

| control | where | why not a model |
|---|---|---|
| the tool set | `agent/tools.py` | a tool cannot return data release policy suppresses; a prompt can be argued with |
| grounding set | `loop.py` | the closed world an answer may draw evidence from — membership is a fact, not a judgement |
| output contract | `submit_answer` + Pydantic | the only exit; schema-validated |
| release gate | `_check_output` | picks and free text: grounded firms, verbatim emails, tier ceilings, no recommending context-only firms |
| inclusion gate | `gold/gate.py` | ADR-0029: an LLM deciding release is the control ADR-0023 exists to avoid |
| auto-release band | `gold/release_band.py` | ADR-0034: releases on measured client-mix corroboration, not judgement |
| answer verification | `rag/checkanswer.py` | ADR-0023: deterministic, model-independent, cannot be talked out of a failure |

**The whole pipeline is deterministic except extraction.** Discovery, gating, promotion, staleness
detection, and reconciliation are plain code. A model appears in exactly two places: reading a web
page into structured fields, and composing prose. Both are places where being wrong is *visible and
recoverable*; neither decides what ships.

Two step-governance controls exist because runs failed without them: a **loop-breaker** (run 10
repeated an identical `fit_rank` call five times and never submitted) and a **forced final submit**
(the last step may only call `submit_answer`).

---

## 3 · Authority boundary

**May decide alone:** which tools to call and how to compose an answer; which candidates to gate,
exclude, or route to enrichment; whether a home page changed materially; whether evidence has moved
enough to flag a record's trust state; whether a gate affirm clears the measured release band.

**Must escalate to a human:** whether a firm that the gate affirmed but the band held back is a
family office; whether an RIA runs an *evidenced* family-office practice (ADR-0028 category 3);
whether a decision-maker's authority is proven; any release of contact data. Human adjudication
**always outranks the gate** where both exist — unchanged since ADR-0029.

**Must refuse or abstain:** claiming a confident fit where `fit_rank` measured insufficient evidence
(code-enforced tier ceiling); naming a firm no tool returned; stating an email not on the record;
recommending a quarantined or non-released firm (ADR-0039); presenting a non-standalone family
office as a family office (blocking check, ADR-0037 era); answering out-of-scope queries (ADR-0026
cosine floor). On a second gate failure the agent **refuses and ships what is known** rather than a
repaired-but-still-unsupported answer.

The principle, because family-office intelligence punishes it asymmetrically: **a confident wrong
answer is worse than a missing one.** A wasted introduction costs a fund manager a relationship; a
blank costs them nothing but a search.

---

## 4 · State, replay, idempotency

Every run opens a row in `ops.runs` and closes it with status, tokens, cost and duration. Every
call — model, retrieval, external API, decision — lands in `ops.run_events`. Observations and trust
events are append-only and carry the run that produced them, so any record's history is
reconstructible run by run (`record_history`). Agent sessions additionally store their full message
trace in `ops.agent_messages`, tool results included.

**What prevents duplicated or corrupted work when a run is interrupted:**

- **Work claiming** — `FOR UPDATE SKIP LOCKED` on the candidate queue: an interrupted run's claims
  are simply re-claimable, never duplicated.
- **A concurrency group** on the workflow: a slow cycle can never overlap the next one.
- **Idempotent upserts** — gold rebuild is a full recompute from silver + bronze, so a partial run
  followed by a full one converges rather than double-counting.
- **Append-only evidence** — bronze captures, gate decisions and trust events are never mutated, so
  a re-run adds a new row rather than overwriting a prior judgement. The record shows what was
  decided on thin evidence *and* what changed when better evidence arrived.
- **A reaper** — a process killed mid-cycle used to leave `status='running'` forever with cost
  columns at zero while real spend sat in `run_events`, silently undercounting any total read from
  `ops.runs`. The next run now closes such runs out as `abandoned` and rolls up their recorded usage.

**Honest limits:** there is no snapshot/rollback of `gold.records` — a bad build is corrected by
the next build, not reverted. Replay re-executes rather than re-plays: an agent session can be
inspected exactly but not deterministically re-run, because the model is not pinned to a seed.

---

## 5 · Cost and latency

`[regen]` — figures below regenerate from `ops.runs` / `ops.run_events` before submission.

| | measured |
|---|---|
| one operating cycle | ~28–35 min, **~$0.012–0.018** |
| refresh 1 record, unchanged | ~$0.000 (HTTP fetch + hash compare, no model call) |
| refresh 1 record, changed | ~$0.0009 (re-fetch + re-extract + diff) |
| refresh all 500, one cycle at the measured ~11.4% change rate | **~$0.05** |
| refresh all 500, forced full re-extract | ~$0.47 |
| one agent goal session | $0.0014–0.0064, 3–5 steps |
| whole window to date | `[regen]` |

Broken out: **model calls** dominate cost entirely (extraction, embedding, agent turns);
**retrieval calls** are Postgres queries with no per-call fee; **external API calls** (ADV, IAPD,
13F, websites) are free and dominate *wall-clock*, not cost.

**Cacheable / downgradable / deferrable:** re-extraction is already skipped when the page hash is
unchanged, which is the single biggest saving; embeddings are incremental; the materiality
classifier could drop to a cheaper model or a pure diff for cosmetic-only changes; the registry
re-check could rotate a sample rather than sweep every record once the set is large.

### At 5,000 records, what breaks first

**Connection establishment in the ops ledger — and we know because it already broke, at 59
records.** Every ledger write opened its own connection (~1s of TLS to the Supabase pooler). Adding
the registry detector roughly doubled writes per sweep, and the pooler started closing connections
mid-run: `server closed the connection unexpectedly`. One sweep over 59 firms opened several hundred
connections; at 500 it would open several thousand, and at 5,000 the handshake time alone exceeds
the cycle budget. **Fixed** (ADR-0036) by moving the ledger onto the pooled, autocommitting
connection source; the sweep now runs 59 firms including 59 registry fetches in ~143s.

**What breaks next, in order, with the reasoning:**

1. **Website fetch wall-clock, ~500–800 records.** A cycle makes one home-page fetch per held
   record plus the discovery tranche. At ~1.4s mean and 8 workers that is ~15 min at 500 and
   ~2.5 hours at 5,000 — past the 6-hour cadence once retries and per-host politeness are counted.
   Fix is sharding by cadence (not every record every cycle), which is a policy change, not an
   architecture one.
2. **`build_gold` full recompute, ~1,000–2,000 records.** It rebuilds every row every cycle
   (60s at 50, ~1.2s/record). Linear that is ~10 min at 500 and ~100 min at 5,000; if superlinear
   it binds sooner. Incremental rebuild is the fix and is not built.
3. **The per-cycle re-extraction budget** — already found and fixed once. A flat cap of 10 against a
   measured 11.4% change rate does not merely delay, it fails to *converge*: skipped records keep
   their old hash and re-count as changed, so the backlog grows without bound. It now scales with
   the set (30%, floor 25).

---

## 6 · What broke while building

`[regen]` — final list assembled from the ledger before submission. Selected, all in git history and
the run ledger:

- **Evidence laundering (run 9).** `fit_rank` promoted generic firms to "strong" healthcare fit on
  token matches. Fixed with a generic-token stoplist and a stated-sector gate. **Recurred on day 3**
  in a different guise — `"lower-middle-market"` → `["lower","middle"]` — on the verbatim Goal 2
  mandate. Same class of bug, second fix.
- **Agent looped (run 10).** Five identical `fit_rank` calls, never submitted. Code-level
  loop-breaker plus forced final submit.
- **The staleness detector recorded model noise as world change.** 26 of 42 `website_change` events
  were LLM free-text variance on unchanged pages. Fixed with normalised comparison plus a
  requirement that a delta reproduce across two cycles; then refined again when reproduction alone
  could not separate variance from oscillation.
- **A detector that could never fire.** The ADV filing-date check compared our held value against
  our own previous observation of it — 772 observations, zero events. Rebuilt to ask IAPD (ADR-0036).
- **The third detector did not exist at all.** Vendor re-verification was claimed in the operating
  plan and never built; the credential has been dead since day 1. The cycle now records the failure
  every run rather than the claim being quietly dropped.
- **Release control ran after publication.** Scheduled run 20 correctly failed — 37 minutes after
  shipping an inconsistent export live. Split into a pre-publication gate plus the full post-export
  check (ADR-0040).
- **A category unreachable in code.** ADR-0028 defined three counted categories; the build could
  only reach two, so the first `embedded_fo_practice` record sat unresolved despite clearing both
  human gates. Then, once reachable, it shipped **unlabelled** on four serving surfaces.
- **Auto-release, attempted and refused twice.** ADR-0029 rejected it at 59% gate precision;
  ADR-0033 tried to fix precision with published-self-evidence and, measured, did not (54.8%) —
  because every false affirm is a wealth manager publishing "family office" about itself. Only the
  client-mix band cleared the bar.
- **A record shipped with no ADV facts at all.** A state-channel firm had empty freshness, AUM,
  phone and address because `_adv_facts` queried only the SEC feed. Guard added so it cannot recur.

**Cases tried beyond the three goals:** `[regen]` — the goal-shaped probes in `ops.query_log`.

---

## 7 · Commercial tier logic

**The tier this belongs in.** The dataset alone is a list, and lists are commodity. What is not
commodity is **a list that tells you which of its rows it no longer believes, and why** — which
requires a system that has been running, not a system that ran once.

**Who pays.** A fund manager raising capital, or a placement agent. Their unit of cost is a wasted
introduction: a partner's time, and a relationship spent on someone who left the firm or never
allocated to the strategy. That is worth materially more than the subscription.

**The gap between manual retrieval and the agentic output**, which is what the brief asks to be
justified: manual retrieval over the extended index returns *the current state of matching records*.
It cannot return "these two changed since Tuesday, here is what changed, and here is why we trust
them less" — because that is not a property of any record, it is a property of the *history* of
records. Goal 3 is built to expose exactly that gap, and the manual-retrieval artifact submitted
beside it is expected to be visibly unable to answer.

**Where we would not charge.** For the raw record count, at its current size. The set is far below
the 500 bar (`[regen]`), and a buyer paying per-record would be right to feel short-changed. What is
sellable today is the *evidence discipline* — per-cell basis, honest blanks, trust state with
reasons, and a system that says "I can't support that" instead of guessing. That is a product for a
buyer who has been burned by a confidently wrong list, which is most of them.
