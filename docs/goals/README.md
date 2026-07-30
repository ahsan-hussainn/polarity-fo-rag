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
| Manual retrieval (`POST /fit`, incl. exact request + latency) | `goal1-manual-fit.json` |
| Agent structured output | `goal1-agent-output.json` (run 46) |
| Raw run log — `ops.runs` + `ops.agent_messages` + `ops.run_events` | `goal1-run-log.jsonl` (58 rows) |
| **Superseded first attempt, kept deliberately** | `goal1-agent-run45-FAILED.json`, `goal1-run45-FAILED-run-log.jsonl` |

### What the manual path returns

`POST /fit` with the mandate and `sector_terms: ["industrials","manufacturing"]`, k=10: 40 records
considered, 10 ranked, fit scores 0.34–0.42, **every one tiered `insufficient_evidence`**, all 10
carrying a named contact. Latency 15.1s.

**Zero Illinois records in the manual top 10.** `/fit` has no geography parameter — it ranks mandate
fit and cannot honour "out of Chicago" at all. The manual path also cannot answer the freshness half
of the question. That gap is the point of comparison for this goal.

### What the agent adds, and what it costs

Run 46: 10 model calls, 17 tool calls (`fit_rank` ×1, `get_record` ×9, `record_history` ×6,
`quarantine_summary` ×1), **$0.01633**, ~65s of model time, slowest single call 39.5s.
Verification passed with no repair turn. It composes an ordered approach list with a named contact,
a reachability basis and a per-pick caveat, and it consults the operating ledger via
`record_history`, which is what the manual path structurally cannot do.

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

### Open limitation, disclosed rather than fixed

**The agent drops the stated geography constraint and misses the one record that matches it.**
`BMO FAMILY OFFICE, LLC` (Chicago, IL) is in the qualifying set. Neither run mentions it; the
strings "Chicago", "Illinois" and "BMO" appear nowhere in either output, and neither run declared
the gap in `limitations`.

This is **not** a capability gap, which is the uncomfortable part. `structured_search` accepts a
`state` filter and would have returned BMO. The run logs show it was **never called** in either
attempt — the agent planned `fit_rank` + `get_record` + `record_history` and never reached for the
one tool that answers the geography half. So this is an agent-planning failure with an available
tool, not a missing filter.

Left open on purpose. Enforcing "honour a stated hard constraint or disclose that you could not"
means either a prompt instruction — which the brief explicitly does not count as enforced control —
or a new deterministic gate rule inferring constraints from the goal text. Building an unmeasured
release rule on day 4 to make one goal look better is the wrong trade; `docs/three-goals.md`
pre-registered this exact failure mode as the thing to watch for, and it happened, so it is reported
as found.
