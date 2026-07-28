# Day-2 checkpoint: the three predictions

Committed **before** the checkpoint email is sent, per the brief's requirement and because a
prediction recorded after the fact is not a prediction. Git history is the timestamp.

The brief: *"There is no penalty for a prediction that turns out wrong — a specific prediction that
misses tells us more than a vague one that cannot."* These are therefore specific and falsifiable,
with the number and the mechanism named. Every figure is read off `ops.runs` / `ops.run_events` as
of run 17, 2026-07-28.

---

## 1. What we expect to break first

**Website fetching at volume — bot-shielding and per-host blocking — with the first visible symptom
being candidates that hold a valid domain but return no readable text.**

Already visible in the ledger before the set has grown at all:

- 5 held firms moved from HTTP 200 to **HTTP 202** between runs 4 and 5 (CRD 106079, 106223,
  142856 among them). 202 with no body is a bot-shield signature, not an outage.
- 9 `fetch_candidate_site` errors across scheduled runs.
- Run 15: of 40 candidates gated, **19 fetched nothing**, and 17 of those carried a social-media URL
  in the ADV website field rather than a firm domain.

The mechanism: cycles run from GitHub-hosted runners on shared, well-known egress IP ranges. Today
a cycle makes ~50 home-page fetches plus ~40 candidate site fetches. At 500 held records the same
cycle makes ~500 + tranche, from the same IPs, on a 6-hour cadence. Anti-bot services rate by IP
reputation and request volume, so the failure arrives as a rising share of 202/403/empty-body
responses rather than as an outage — which is the dangerous shape, because the cycle keeps
reporting success while its evidence quietly thins.

Second-most-likely, named because the first may not fire: **`build_gold` wall-clock.** It measured
60s at 50 records (~1.2s/record). If that is linear it is ~10 min at 500 and ~100 min at 5,000; if
it is superlinear it binds much sooner. We are measuring it as the set grows rather than
extrapolating from one point.

*Explicitly not predicted:* the per-cycle re-extraction budget. It **was** the first bottleneck —
a flat cap of 10 against a measured ~11.4% change rate binds at ~88 records, and run 15 hit 9
against 10 with 50 records held. It was found and fixed on day 2 (budget now scales with the set,
classification runs concurrently, oldest-unchecked first). Naming it here as already-broken-and-
fixed rather than as a prediction.

## 2. Expected cost to refresh one record, and all 500

Measured, not modelled. `gpt-4o-mini` extraction, `text-embedding-3-small` indexing.

| | cost | basis |
|---|---|---|
| Refresh 1 record, **unchanged** | **~$0.000** | HTTP fetch + hash compare only; no model call. Mean fetch 1.36s over 500 observations |
| Refresh 1 record, **changed** (re-fetch + re-extract + diff) | **~$0.0009** | mean of 46 `materiality_extract` calls: $0.000929 |
| Refresh **all 500**, one cycle, at the measured change rate | **~$0.05** | 500 × 11.4% changed × $0.0009 |
| Refresh **all 500**, forced full re-extract | **~$0.47** | 500 × $0.0009 |
| One full cycle today (50 held + 40-candidate tranche) | **$0.002 – $0.018** | `ops.runs.usd_est`, runs 3–15 |

Whole window to date: **$0.086** across 105 model calls. Retrieval and external API calls carry no
per-call fee; Supabase and Render are free tier.

The prediction: **the marginal cost of holding 500 records current is roughly $0.05 per cycle,
about $0.20/day at a 6-hour cadence**, and cost is not what constrains this system — wall-clock and
source cooperation are.

## 3. Goal 2 — expected confidence, and where we expect it to abstain

Goal 2 verbatim: *"Identify the family offices in the dataset that are the best fit for a
lower-middle-market healthcare services fund seeking limited partners, and tell me how confident you
are in each."*

**Expected: low-to-moderate confidence, a small number of weak-to-moderate picks, and explicit
abstention on the majority of nominally-matching records.**

Grounded in run 12, which ran this goal verbatim: it returned **weak picks plus 6 abstentions**,
passed the independent verification floor, cost $0.0034 over 4 steps. Run 9 attempted to launder
generic-token evidence into a confident answer and the scorer was fixed to stop it; run 10 looped on
identical calls and a code-level loop-breaker was added. That progression is in the ledger.

We expect it to abstain specifically where:

- the record carries **no stated sector or mandate evidence** — the scorer's stoplist plus
  stated-sector gate refuses to treat generic descriptive tokens ("investments", "private capital")
  as healthcare-mandate evidence;
- the entity category is **unresolved** — currently 18 of 50 records — since a fit claim about a
  firm we cannot classify is a claim stronger than its evidence;
- contact evidence is **quarantined** (8 records), so no actionable introduction path exists.

We expect **no record to be returned at high confidence**, because no held record currently carries
an explicit healthcare-allocation statement. If the run does emit a high-confidence pick, that is
the interesting failure and we would rather it be visible than smoothed away.
