# Build summary — supporting detail

`BUILD_SESSION_SUMMARY_STAGE2.md` is capped by the brief at under half a page. This file holds the
evidence behind its claims so the summary can stay short without the numbers becoming unsupported
prose. Nothing here is new; it is the working detail for claims stated there.

---

## 1 · How long the operating window took

Measured from the run ledger, not from memory — regenerate from `data/ops_export/runs.jsonl`:

- **Scheduled cycles only:** first fired `2026-07-27T15:19:07Z`, last finished `2026-08-01T16:09:48Z`
  — **5 days, 0 hours, 51 minutes**, across **33 scheduled runs** (32 completed, 1 failed).
- **Every run, including local tests and manual dispatches:** `2026-07-27T09:03:12Z` →
  `2026-08-01T19:05:11Z` — **5 days, 10 hours, 2 minutes**, 74 runs.

Cross-checked against the scheduler's own history: GitHub Actions reports 33 scheduled runs from
`2026-07-27T15:18:47Z` to `2026-08-01T15:45:21Z`, with 1 failure. The platform history and our
internal ledger agree on both count and span.

The 48-hour separation condition was met many times over; the binding constraint on the window was
never run separation but the five-day submission ceiling. The scheduler kept firing through the end
of the window, so the last scheduled cycle lands *after* the point at which deliverables were frozen
— the export is the state at freeze.

## 2 · Build time: why days 4–5 are not estimated

`docs/SESSION_LOG.md`'s standing rule is that every start and end time is supplied by hand and none
inferred. Applying that rule only when it flatters the total would make the log worthless, so the
unlogged sittings are left blank rather than reconstructed.

For calibration only, the commit spans — a **lower bound on a sitting, not the sitting**:

| sitting | first → last commit | span |
|---|---|---|
| day 4 (07-30) | 12:02 → 15:43 | 3 h 41 m |
| day 5 (07-31) | 11:31 → 18:29 | 6 h 58 m — see note |
| day 5, phone dispatch (08-01) | 01:10 → 01:50 | 40 m |
| wrap (08-02) | 00:12 → — | open |

**The day-5 span is the one not to trust.** There is a 6 h 45 m gap with no commits between 11:44 and
18:29, so 6 h 58 m is almost certainly two sittings with a long break in it, not seven hours of work.
Reporting it as seven would be exactly the padding the brief asks against.

## 3 · The least-trusted number, in full

The band's headline accuracy is **16/16** — measured on the *calibration set its own thresholds were
chosen against*. ADR-0034 states that sampled human review of released records is the only
measurement that can falsify the band, because it is the only one taken out of sample. That review
sheet (`band-review`) was built on day 5 and surfaced a defect before a human read a row: **both
records released via the CONCORDANCE route carry a client mix that contradicts the entity claim.**

| record | HNW share | non-HNW clients | band requires |
|---|---|---|---|
| ANGELES FAMILY OFFICE | 79% | 0 | ≥ 90% |
| ONEASCENT FAMILY OFFICES | 43% | 43 | ≤ 15 |

Both would fail route 1 outright.

**Cause — a real code/ADR divergence.** ADR-0034 describes route 2 as a *fallback* for firms that
file no usable client mix: "or — where a firm files no usable client mix — requires concordant
published evidence". But `evaluate()` fires route 2 as an unconditional OR whenever the score clears
100, regardless of whether the mix is present and failing. So a firm whose registry data actively
contradicts the family-office claim is released on the strength of its own website — the precise
failure ADR-0034 exists to prevent, since its own context section establishes that self-published
evidence cannot separate a family office from a wealth manager marketing itself as one.

**Not patched at the deadline.** It changes release behaviour, drops the qualifying count, and
`BAND_VERSION` is frozen with "changes require a superseding ADR". Both records remain in the shipped
`data/gold/family_office_dataset.csv`. Disclosed with the evidence rather than quietly fixed or
quietly shipped.

**Consequence:** treat **40** as an upper bound containing at least 2 known-soft rows, not a clean
count. The 29 human-ratified records are unaffected — this is a statement about the 11
machine-released ones.

**What would check it:** run `band-review` to human verdict across all 11 released records, not the 2
the sheet surfaced, and report out-of-sample precision with the sample size stated.

**Runner-up (per-cell):** the `VERIFIED_API` email grades — vendor-reported deliverability on
inferred-pattern addresses, never proven to be the named person's mailbox, obtained pre-window, and
never re-verified during the window because the MillionVerifier credential returned HTTP 403 on every
run. Checked by restoring the credential, re-running the verifier, and a small real-send bounce test
on the shipped grade-A rows.

## 4 · What was not reviewed

- **The 11 band-released records, individually.** Only the 2 the review sheet flagged were read. The
  other 9 have had no human look at them — the substance of §3.
- **The raw operating ledger row by row.** `data/ops_export/` is 74 runs, 4,827 run_events and 11,009
  observations, shipped uncurated and deliberately unfiltered. Schema, manifest totals, and the runs
  under investigation were reviewed; 11,009 observations were not read.
- **Every cell of all 40 records.** The three full validation chains were reviewed end to end, along
  with rows touched by adjudication; the rest was sampled.
