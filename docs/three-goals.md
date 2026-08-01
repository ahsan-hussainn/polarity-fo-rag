# The three goals

Goal 2 is used verbatim as the brief requires. Goals 1 and 3 are framed here, before running them,
so the goal is a commitment rather than something reverse-engineered from a good-looking output.

For each goal the submission carries four artifacts: the exact goal string, the output a user would
get from the extended retrieval **manually** (`POST /fit` — the same ranking the agent calls as a
tool, served directly), the agent's structured output, and the raw run log — `ops.agent_messages`
for the full message trace including tool results and any repair turn, plus `ops.runs` /
`ops.run_events` for per-call timing, tokens and cost, exported unedited by `pipeline.cli
ops-export`.

**Counts in this document are stamped, not current.** The set changes every operating cycle; live
figures come from `reconcile` and `/stats`.

---

## Goal 1 · Multi-step commercial search

> **We are raising a $150M lower-middle-market industrials buyout fund out of Chicago and need LPs.
> Build me an approach list from your dataset: which family offices should we contact first, who
> specifically do we contact at each, how reachable are they, and where is your information too old
> or too thin for us to rely on it?**

**Why a single retrieval call cannot answer it.** It decomposes into at least four sub-questions
that hit different indexes and different tables: mandate fit (semantic + `fit_rank`), geography and
entity category (structured filters), decision-maker identity and reachability (per-record contact
evidence and email grades), and freshness/trust (the operating ledger). No single query returns
those together, and the ranking depends on combining them — a firm with perfect sector fit and a
quarantined contact ranks differently from one with moderate fit and a graded, reachable principal.

**Why a real user pays for it.** This is the actual first task of a fund raising capital: not
"search family offices" but "tell me who to call on Monday, and how confident you are." The output
is an ordered approach list with a reason and a confidence per line.

**What we expect to be hard.** Chicago-plus-industrials is a narrow slice of a small qualifying set
(32 at the time of writing, 2026-07-29), so we expect thin results and want the agent to say so
rather than widen the criteria silently to fill a list. Silently relaxing a stated constraint is the
failure mode to watch for.

---

## Goal 2 · Uncertain-data case (verbatim, as required)

> Identify the family offices in the dataset that are the best fit for a lower-middle-market
> healthcare services fund seeking limited partners, and tell me how confident you are in each.

Quoted verbatim, character-exact against the brief (no added emphasis — the blockquote holds the
exact string the agent was given); verified against runs 9–12, which already exercised it four
times. The run-9 → run-10 → run-12 progression (evidence laundering → identical-call loop → honest
weak-picks-plus-abstentions) is in the ledger and is the substance of architecture note §6.

Uncertain records stay in the set for this run, per the brief's explicit instruction not to clean
them away: the unresolved and quarantined records remain visible with their status intact (18 and 9
respectively at the time of writing, 2026-07-29 — regenerate from `reconcile` for the submitted
figure).

---

## Goal 3 · Paid-tier case (ours)

> **Which records in your coverage have changed in a way that would change how I approach them
> since I last looked, what specifically changed, and which ones should I now stop trusting?**

**Why this is the paid-tier case.** Every competitor can sell a list. A list is a photograph; this
question can only be answered by a system that has been *running*. Answering it requires
cross-cycle evidence — what the system observed on an earlier cycle, what it observed later, and
the judgment it formed about the difference. That is `ops.observations` and `ops.trust_events`, and
it does not exist in a dataset export at any price.

**This goal was unanswerable until day 3, which is worth stating rather than hiding.** The framing
above was written on day 2, and at that point no tool could read `ops.*` at all — every tool
returned the current state, so the agent's only honest answer would have been "I cannot see
history." `record_history` (ADR-0038) closed that gap: with no arguments it lists released records
whose evidence has moved; with a firm name it returns that firm's run-by-run history. The first
version still failed, and instructively — asked what to stop trusting, the agent answered from
`quarantine_summary`, naming never-released *candidates* as family offices to distrust. It conflated
"never released" with "released and now doubtful," and it had no way to *discover* the flagged set.
Both are fixed (ADR-0038, ADR-0039); the failing session is in the ledger.

It is also the question that maps to real money: a fund manager's cost of acting on a stale record
is a wasted introduction, and their cost of *not knowing* a decision-maker left is worse.

**The manual-retrieval gap will be unusually wide here**, which is exactly what the brief asks Goal
3 to demonstrate. Manual retrieval over the extended index returns the *current* state of a record.
It cannot return "this changed since Tuesday and here is why we trust it less," because that is not
a property of any record — it is a property of the history of records. We expect the manual output
to be visibly unable to answer, and that contrast is the deliverable.

**What we expect to be hard.** The honest answer is small. The trust ledger holds `website_dark`,
`decision_maker_gone` and `adv_filing` events alongside a large number of correctly-classified
cosmetic changes that a user should *not* be told about, and only a couple of records are flagged
at any moment once superseded events are discounted (ADR-0037: a later refresh clears an earlier
flag, so a re-verified firm stops carrying a scar). Reporting cosmetic churn as change would be
noise sold as signal, so the interesting behaviour is what the agent leaves out. If it reports every
hash flip it has failed this goal, even though it would look more impressive.

The same applies to the size of the answer: two flagged records is a *correct* answer to this
question today, and padding it would be the failure. Regenerate the figures at run time from
`record_history` rather than quoting these.
