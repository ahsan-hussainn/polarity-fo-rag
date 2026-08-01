# Architecture notes

**Figures stamped 2026-08-02** from `ops.runs` / `ops.run_events` / `ops.query_log`, the end-of-window
`data/ops_export/`, and a `reconcile` pass (26/26, `all_agree`) — never hand-carried. A figure here is
a measurement with a timestamp, not a constant.

**Length, stated rather than hoped past.** The brief caps these sections at two to three pages; this
runs to about four. It was cut from ~3,400 words by relocating the full defect narrative, the runs
that did not end clean, and the scale reasoning into `docs/findings/what-broke.md`, which ships in
the repo and is not page-capped. What remains is content the brief names directly in these sections —
the source-class table, the agentic/deterministic boundary, the two cost tables, the 5,000-record
bottleneck analysis, and the 500-shortfall arithmetic — so cutting further would trade the page rule
for unanswered questions. Each claim is stated once and points at the ADR, finding or run carrying
its evidence.

---

## 1 · Retrieval extension

**What was added: `fit_rank`** (`pipeline/rag/fit.py`, ADR-0030), served at `POST /fit` and
available to the agent as a tool.

Stage 1 retrieval answers *"which records match this query."* `fit_rank` answers *"rank the whole
qualifying dataset against this investor mandate, and tell me how much to trust each ranking"* —
a **defensible ordering with per-record confidence**, which embedding distance alone cannot give,
because it cannot distinguish a firm that states a healthcare mandate from one that sounds like it
might.

The design decision that matters: **the confidence tier is a function of evidence *presence*, not
score magnitude.** A record can rank high on similarity and still be labelled
`insufficient_evidence`. That is what lets the agent abstain instead of laundering a high score into
a confident claim. Only the mandate embedding is a model call; every component ships in the output
with pre-registered weights, so a user sees *why* a firm ranks where it does.

**Considered and rejected:** a learned re-ranker (no labelled relevance data, and unexplainable
ranking is unsellable to a buyer who must justify an approach list); an LLM-as-judge scorer
(ADR-0023 — a release-relevant judgement that can be talked out of a failure); up-front
sector-classification of every record (manufactures labels the source text does not support, which
is the same laundering moved elsewhere).

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
times, when it has enough, how to compose the answer (`pipeline/agent/loop.py`). Nothing in the code
dictates calling `fit_rank` before `structured_search`, or deepening a firm with `get_record`. That
is where a model earns its place: the decomposition differs per goal in ways a fixed pipeline would
have to enumerate in advance.

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
detection and reconciliation are plain code. A model appears in exactly two places — reading a web
page into structured fields, and composing prose — both places where being wrong is visible and
recoverable, and neither decides what ships. Two step-governance controls exist because runs failed
without them: a **loop-breaker** and a **forced final submit** (run 10, §6).

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
office as one (blocking check); answering out-of-scope queries (ADR-0026 cosine floor). On a second
gate failure the agent **refuses and ships what is known** rather than a repaired-but-unsupported
answer.

The principle, because this domain punishes it asymmetrically: **a confident wrong answer is worse
than a missing one.** A wasted introduction costs a fund manager a relationship; a blank costs a
search.

---

## 4 · State, replay, idempotency

Every run opens a row in `ops.runs` and closes it with status, tokens, cost and duration; every call
— model, retrieval, external API, decision — lands in `ops.run_events`. Observations and trust
events are append-only and carry the run that produced them, so any record's history is
reconstructible run by run (`record_history`). Agent sessions also store their full message trace,
tool results included, in `ops.agent_messages`.

**What prevents duplicated or corrupted work when a run is interrupted:** `FOR UPDATE SKIP LOCKED`
work claiming (an interrupted run's claims are re-claimable, never duplicated); a workflow
concurrency group (a slow cycle cannot overlap the next); idempotent upserts (gold rebuild is a full
recompute, so a partial run followed by a full one converges rather than double-counting);
append-only evidence (bronze captures, gate decisions and trust events are never mutated, so the
record shows what was decided on thin evidence *and* what changed when better arrived); and a reaper
that closes out runs whose process died (§6).

**Honest limits:** there is no snapshot/rollback of `gold.records` — a bad build is corrected by the
next build, not reverted. Replay re-executes rather than re-plays: an agent session can be inspected
exactly but not deterministically re-run, because the model is not pinned to a seed.

---

## 5 · Cost and latency

Measured over the **32 completed scheduled cycles** run between 2026-07-27 15:19Z and 2026-08-01
16:09Z (33 fired; one failed). Regenerated from `data/ops_export/runs.jsonl` at end of window.

| | measured |
|---|---|
| one scheduled operating cycle | 15.1–34.5 min (mean **22.3**), $0.0020–$0.0180 (mean **$0.0085**) |
| refresh 1 record, unchanged | ~$0.000 (HTTP fetch + hash compare, no model call) |
| refresh 1 record, changed | ~$0.0009 (re-fetch + re-extract + diff) |
| refresh all 500, one cycle at the measured ~11.4% change rate | **~$0.05** |
| refresh all 500, forced full re-extract | ~$0.47 |
| one agent goal session | $0.0007–$0.0163 over 22 sessions, **$0.1149** total |
| **whole window, every run** | **74 runs, 2,282,143 tokens in / 154,700 out, $0.4344** (2026-07-27 09:03Z → 2026-08-01 19:05Z) |

Per goal, for the submitted runs:

| goal | run | latency | cost | tokens in/out | tool calls |
|---|---|---|---|---|---|
| 1 · mandate fit | 47 | 43.9s | $0.00636 | 40,180 / 551 | 20 |
| 2 · weak-evidence | 48 | 11.4s | $0.00117 | 6,451 / 329 | 3 |
| 3 · paid-tier | 56 | 27.0s | $0.00637 | 40,081 / 599 | 13 |

**Goal 2 is the cheapest and fastest run in the set, and that is the point of it** — the agent
stopped after three calls rather than working harder against evidence that could not support a
confident answer. A system that spent *more* on Goal 2 would be laundering weak evidence.

**A claim we had to withdraw at end of window.** An earlier draft of this section said a $0.000
cycle "is the common case" — a cycle finding no changed pages makes no model call, so it costs
nothing. The mechanism is real, but the end-of-window ledger does not support the frequency claim.
Of 48 cycles, 8 cost exactly $0.000, and **every one of those 8 is a local test or manual dispatch**
(`local-test-*`, `local-smoke`, `local-regate-v3`, `workflow_dispatch`). **No scheduled cycle ever
cost $0.000** — the cheapest was $0.0020. At this dataset size some page always changes, so the
free-cycle case never fired in unattended operation. The affordability claim survives on the
measured mean of **$0.0085 per scheduled cycle**, not on free cycles.

Broken out: **model calls** dominate cost entirely; **retrieval calls** are Postgres queries with no
per-call fee; **external API calls** (ADV, IAPD, 13F, websites) are free and dominate *wall-clock*,
not cost. **Cacheable / downgradable / deferrable:** re-extraction is already skipped on an unchanged
page hash (the biggest saving); embeddings are incremental; the materiality classifier could drop to
a cheaper model for cosmetic changes; the registry re-check could rotate a sample once the set is
large.

### At 5,000 records, what breaks first

**Connection establishment in the ops ledger — and we know because it already broke, at 59
records.** Every ledger write opened its own connection (~1s of TLS to the Supabase pooler). The
registry detector roughly doubled writes per sweep and the pooler began closing connections mid-run
(`server closed the connection unexpectedly`, run 53). One sweep over 59 firms opened several
hundred connections; at 5,000 the handshake time alone exceeds the cycle budget. **Fixed**
(ADR-0036) onto a pooled autocommitting source: 59 firms plus 59 registry fetches now run in ~143s.

After it, in order: **website fetch wall-clock** (~500–800 records; ~1.4s mean × 8 workers is ~2.5h
at 5,000, past the cadence — fix is cadence sharding, a policy change); **`build_gold` full
recompute** (~1,000–2,000; ~1.2s/record, no incremental rebuild exists); **the re-extraction
budget** (already fixed once — a flat cap against an 11.4% change rate does not converge, because
skipped records keep their old hash and re-count as changed). Reasoning and measurements:
[what-broke.md](./findings/what-broke.md#scale-what-breaks-next-with-the-reasoning).

---

## 6 · What broke while building

Thirteen defects, each with a run, a commit or an ADR behind it. Full narrative and evidence:
**[docs/findings/what-broke.md](./findings/what-broke.md)**.

| what broke | how it was caught | what changed |
|---|---|---|
| release control ran **after** publication | run 20 failed 37 min after shipping an inconsistent export live | pre-publication gate + full post-export check (ADR-0040) |
| `website_dark` fired on HTTP **202**, a success code | 16 of 20 events were 2xx, 2 were our own 429s; a Goal-3 run told a user to distrust 7 records on it | reachability classified; recovery supersedes the flag |
| the ADV filing detector could never fire — it compared our held value to our own copy of it | 772 observations, **zero** events | rebuilt to ask IAPD (ADR-0036) |
| `fit_rank` laundered token matches into "strong fit" — twice, the second time on the Goal 2 mandate itself | run 9; re-found day 3 (`"lower-middle-market"` → `["lower","middle"]`) | generic-token stoplist + stated-sector gate |
| release rule was asymmetric — human-affirmed entities held while machine-affirmed ones shipped | affirming 3 firms did not move the count | ADR-0041; qualifying 32 → 35 |
| a published coverage figure was wrong, and the true one **weakened** our story | re-measured against the row `gate.assemble()` actually reads | withdrawn in its own commit, not quietly edited |
| auto-release refused twice before it was accepted | 59%, then 54.8% measured gate precision | only the client-mix band cleared the bar (ADR-0034) |

Six more — the agent loop, extraction variance read as world change, the staleness detector that was
never built, a counted category unreachable in code, the band's misdescribed route 2, and a record
that shipped with no ADV facts — are in [what-broke.md](./findings/what-broke.md#the-defects) with
the same evidence.

**Runs that did not end clean:** 3 of 62 — run 20 (above), run 53 (ledger connections, §5), and run
27, which died without closing its row and was reaped by the next run. That reaper exists because a
killed process otherwise leaves `status='running'` forever with cost columns at zero, silently
undercounting any total read from `ops.runs`.

**Cases tried beyond the three goals.** `ops.query_log` holds **22 queries** — 19 agent, 2 API, 1
UI. Three of the 19 are the submitted goal artifacts; the other 16 are probes and rejected attempts,
four of them committed under their own names (`run45-FAILED`, `run46-PARTIAL`, `run49-REFUSED`,
`run50-PREFIX`) rather than deleted. Outcomes across all 22: **19 answered, 2 refused on the
verification floor, 1 refused as out of scope.**

---

## 7 · Commercial tier logic

**The tier this belongs in.** The dataset alone is a list, and lists are commodity. What is not
commodity is **a list that tells you which of its rows it no longer believes, and why** — which
requires a system that has been running, not a system that ran once.

**Who pays.** A fund manager raising capital, or a placement agent. Their unit of cost is a wasted
introduction: a partner's time, and a relationship spent on someone who left the firm or never
allocated to the strategy. That is worth materially more than the subscription.

**The gap between manual retrieval and the agentic output.** Manual retrieval over the extended
index returns *the current state of matching records*. It cannot return "these two changed since
Tuesday, here is what changed, and here is why we trust them less" — that is not a property of any
record, it is a property of the *history* of records. Goal 3 exposes exactly that gap, and the
manual-retrieval artifact submitted beside it is visibly unable to answer.

**The shortfall, as measured yield rather than an excuse.** Regenerated 2026-08-02 from the live DB
(`ops.candidate_queue` joined to the latest `gold.entity_gate` decision per entity):

| stage | measured |
|---|---|
| candidates gated | **361** |
| gate affirms | **58** (16.1%) |
| of those, band-released into the product | **11** (19.0% of affirms) |
| end-to-end automated yield | **3.0%** of gated candidates |

The other 47 affirms: 44 held, 2 reached qualifying by human ratification, 1 quarantined. **The load-
bearing fact is that the gate over-affirms and the band is what catches it** — of the 44 held, 32 are
held because the client mix contradicts the entity claim, a 55% contradiction rate matching the
gate's independently measured 54.8% precision. So 460 more records at a 3.0% yield would need
~15,100 gated candidates; everything still unseeded totals roughly 3,558, which yields **~109 more**
and lands near **150**, not 500. What would have closed it is human ratification — how 29 of the
current 40 were qualified — which works and does not scale to 500 in five days, which is precisely
why ADR-0029 built the gate. Releasing the 32 contradicted affirms would reach the number by
shipping ~45% non-family-offices: Stage 1's named failure, and the one move the brief calls
disqualifying.

**Where we would not charge.** For the raw record count. The set stands at **40 qualifying records
against a 500 bar** (34 family offices + 6 evidenced practices, never summed; stamped 2026-08-02,
regenerate with `reconcile`), and a buyer paying per-record would be right to feel short-changed.
What is sellable today is the *evidence discipline* — per-cell basis, honest blanks, trust state
with reasons, and a system that says "I can't support that" instead of guessing: a product for a
buyer who has been burned by a confidently wrong list, which is most of them.
