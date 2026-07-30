# Goal artifacts

Four artifacts per goal, as the brief requires: the exact goal string, the output a user would get
from the extended retrieval **manually**, the agent's structured output, and the **raw, unedited**
run log. Goal framings are committed in `docs/three-goals.md` ahead of the runs, so a goal is a
commitment rather than something reverse-engineered from a good-looking answer.

Figures here are stamped with the run that produced them. Live counts come from `reconcile` and
`GET /stats`.

---

## Goal 1 · Multi-step commercial search — run 2026-07-30, day 4

**Exact goal string** (as committed in `docs/three-goals.md`):

> We are raising a $150M lower-middle-market industrials buyout fund out of Chicago and need LPs.
> Build me an approach list from your dataset: which family offices should we contact first, who
> specifically do we contact at each, how reachable are they, and where is your information too old
> or too thin for us to rely on it?

Dataset state at run time: **40 qualifying** (34 SFO+MFO + 6 evidenced practices), 15 unresolved,
9 quarantined — from `GET /stats`, 2026-07-30 12:05 PKT.

| Artifact | File |
|---|---|
| Manual retrieval (both attempts, exact requests + latency) | `goal1-manual-fit.json` |
| Agent structured output | `goal1-agent-output.json` (**run 47**) |
| Raw run log — `ops.runs` + `ops.agent_messages` + `ops.run_events` | `goal1-run-log.jsonl` (43 rows) |
| **Superseded attempt 1, kept deliberately** | `goal1-agent-run45-FAILED.json` + `goal1-run45-FAILED-run-log.jsonl` |
| **Superseded attempt 2, kept deliberately** | `goal1-agent-run46-PARTIAL.json` + `goal1-run46-PARTIAL-run-log.jsonl` |

### What the manual path returns

Captured against the deployed service. Two attempts, because the difference between them *is* the
finding.

**Attempt 1 — mandate only, what a user types first.** 40 considered, 10 ranked, scores 0.34–0.42,
**every row tiered `insufficient_evidence`**, all 10 with a named contact. Top hits Denver, Naples,
Atlanta — **zero Illinois records**. The mandate says "out of Chicago" and the ranking cannot honour
it, because geography was not expressible.

**Attempt 2 — the same mandate with `state: "IL"`**, a filter added to `POST /fit` on 2026-07-30 as
part of this goal's fix. 40 considered → **1**, returning `BMO FAMILY OFFICE, LLC` (Chicago, IL),
still `insufficient_evidence` on mandate fit. The record the first attempt could never reach.

Even with the filter, the manual path cannot answer the freshness half of the question. That gap is
the point of comparison for this goal.

### What the agent adds, and what it costs

Run 47: 10 model calls, 9 tool calls (`fit_rank` ×2, `structured_search` ×2, `get_record` ×2,
`semantic_search` ×1, `record_history` ×1, `quarantine_summary` ×1), **$0.00636**. Verification
passed with no repair turn.

One pick — BMO Family Office, Chicago — at `weak` confidence with a caveat, a verdict stating the
industrials evidence is insufficient because the record's stated sectors do not include industrials,
and an honest outreach line: no decision-maker is established, so general channels only. It reached
for `structured_search` here, which run 45 never called, and consulted the operating ledger via
`record_history` — which the manual path structurally cannot do.

### Run 45 failed the release check's intent, and is kept as evidence

The first attempt shipped **three picks at `confidence: strong` with no caveats** — Xception, Fifth
Avenue, Eagle Bay — over records `fit_rank` had measured `insufficient_evidence`, each citing only
an AUM band as evidence. Xception's stated sectors contain no industrials. Verification reported
`passed: true`.

Root cause was a **release control that had silently stopped applying**. `_check_output` has exactly
the right guard (`loop.py`: a pick claiming strong/moderate over a measured `insufficient_evidence`
tier is a failure), but `grounding[crd] = r` overwrote unconditionally. `fit_rank` returns records
carrying `fit_confidence`; `get_record` does not, because the tier is computed per mandate and there
is no such column, and `_slim()` omits absent keys. So nine `get_record` calls erased the measured
tier for the same CRDs, the guard read `None`, and both confidence checks skipped. A control that
still reports "passed" while no longer applying is worse than an absent one.

Fixed by merging rather than clobbering: keys in the newer view win, keys only the older view had
survive. A re-rank under a new mandate still updates the tier; a thin lookup can no longer disarm
the gate. Verified by replaying the exact sequence — **old path 0 failures, new path 1 failure**
with the correct message.

**What run 46 does not prove.** Its nine picks are all `weak` with caveats, and `limitations` now
states the fit rests on insufficient evidence — but `repaired: false`, so the model produced
compliant output on its own. `grounding` feeds the gate, not the model, so the fix did not cause the
better labels; run-to-run variation did. The fix's guarantee is narrower and worth stating exactly:
a strong-over-insufficient claim can no longer pass **silently**.

### Run 46 dropped the stated constraint too — fixed in two halves

Run 46 fixed the confidence problem and kept the geographic one: no mention of Chicago, Illinois or
BMO anywhere, `limitations` empty. `docs/three-goals.md` pre-registered exactly this ("silently
relaxing a stated constraint is the failure mode to watch for"), and the uncomfortable part was that
it was **not** a capability gap — `structured_search` already accepted a `state` filter and the logs
show the agent simply never called it.

Two things were wrong, so two things changed.

**Capability.** `fit_rank` now accepts `state`/`city` as exact filters, applied before ranking and
deliberately *not* folded into the weighted score — a firm does not become a better mandate fit by
being nearby. Plumbed through the tool and `POST /fit`. An empty geographic result now states that
the constraint held and the answer is genuinely empty, rather than looking like a failed search.

**Enforcement**, because the brief is explicit that prompt instructions do not count as enforced
control. `_check_output` extracts geographic constraints from the goal and requires each to be
honoured or disclosed. The constraint vocabulary is read from the corpus itself — distinct city and
state of qualifying records — so it cannot drift from the data. Conservative by construction: full
state names mapped to codes, city names ≥5 characters, word-boundary matching only, and **never**
bare two-letter codes, because `IN`, `OH`, `MA` and `CA` are ordinary words. `ADA` is skipped for the
same reason; a missed constraint is a disclosure gap, a false one blocks a correct answer.

The rule enforces **disclosure, not judgment.** It does not require that a record in the stated place
be recommended — the honest answer may well be "we hold one and it is a poor fit." What it forbids is
silence. Verified three ways: the run-45/46 shape fails, disclosing-without-matching passes, and
returning a matching record passes. Goals 2 and 3 extract no location, so no false positives.

### Still open: the AUM band is derived from the fund's size

Run 47 called `fit_rank` with `min_aum_usd: 150000000` and `structured_search` with
`min_aum_usd: 150000000, max_aum_usd: 10000000000`. The $150M is **the fund's size, not a constraint
on family-office AUM**, and the `min_aum_usd` tool description says so explicitly: *"Never derive
this from a fund's market segment... A $5B family office writing an LP cheque into a
lower-middle-market fund is a fit, not a mismatch."* The `max_aum_usd` value is invented outright.

It changed nothing here — Illinois holds exactly one qualifying record at any AUM — but it made the
prose wrong: `coverage_note` and `limitations` both attribute the narrow result to "the AUM
criteria" when the actual cause is geography. A customer-facing string crediting the wrong filter is
a small honesty defect, not a cosmetic one.

Reported rather than fixed, and the reason is the same one this note keeps returning to: the
guardrail is currently a **tool description**, which is a prompt instruction, and the brief says
those do not count as enforced control. Doing it properly means a deterministic rule — a size band
is only legitimate when the goal constrains the family office, not the fund — and that needs
measuring against goals that legitimately do constrain FO size before it goes in front of a release
path. Left as a known defect with the run log as evidence.
