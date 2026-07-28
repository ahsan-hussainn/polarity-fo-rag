# The three goals

Goal 2 is used verbatim as the brief requires. Goals 1 and 3 are framed here, before running them,
so the goal is a commitment rather than something reverse-engineered from a good-looking output.

For each goal the submission carries four artifacts: the exact goal string, the output a user would
get from the extended retrieval **manually**, the agent's structured output, and the raw run log
(`ops.runs` + `ops.run_events` for the session, exported unedited).

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

**What we expect to be hard.** Chicago-plus-industrials is a narrow slice of a 24-qualifying-record
set, so we expect thin results and want the agent to say so rather than widen the criteria silently
to fill a list. Silently relaxing a stated constraint is the failure mode to watch for.

---

## Goal 2 · Uncertain-data case (verbatim, as required)

> **Identify the family offices in the dataset that are the best fit for a lower-middle-market
> healthcare services fund seeking limited partners, and tell me how confident you are in each.**

Character-exact against the brief; verified against runs 9–12, which already exercised it four
times. The run-9 → run-10 → run-12 progression (evidence laundering → identical-call loop → honest
weak-picks-plus-abstentions) is in the ledger and is the substance of architecture note §6.

Uncertain records stay in the set for this run, per the brief's explicit instruction not to clean
them away: 18 unresolved and 8 quarantined records remain visible with their status intact.

---

## Goal 3 · Paid-tier case (ours)

> **Which records in your coverage have changed in a way that would change how I approach them
> since I last looked, what specifically changed, and which ones should I now stop trusting?**

**Why this is the paid-tier case.** Every competitor can sell a list. A list is a photograph; this
question can only be answered by a system that has been *running*. Answering it requires
cross-cycle evidence — what the system observed on an earlier cycle, what it observed later, and
the judgment it formed about the difference. That is `ops.observations` and `ops.trust_events`, and
it does not exist in a dataset export at any price.

It is also the question that maps to real money: a fund manager's cost of acting on a stale record
is a wasted introduction, and their cost of *not knowing* a decision-maker left is worse.

**The manual-retrieval gap will be unusually wide here**, which is exactly what the brief asks Goal
3 to demonstrate. Manual retrieval over the extended index returns the *current* state of a record.
It cannot return "this changed since Tuesday and here is why we trust it less," because that is not
a property of any record — it is a property of the history of records. We expect the manual output
to be visibly unable to answer, and that contrast is the deliverable.

**What we expect to be hard.** The honest answer today is small: the trust ledger holds
`website_dark` on 5 firms, `decision_maker_gone` on 2, and a large number of correctly-classified
cosmetic changes that a user should *not* be told about. Reporting cosmetic churn as change would
be noise sold as signal, so the interesting behaviour is what the agent leaves out. If it reports
every hash flip it has failed this goal, even though it would look more impressive.
