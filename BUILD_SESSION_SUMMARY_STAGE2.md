# Build session summary — Stage 2

> Stage 1's summary is `BUILD_SESSION_SUMMARY.md`. Counts are stamped, not live — regenerate with
> `python -m pipeline.cli reconcile`. Per-sitting times: `docs/SESSION_LOG.md`. Evidence behind every
> number below, including the full band-defect write-up: **`docs/findings/build-summary-detail.md`**.
>
> **Length, stated rather than hoped past:** the brief caps this at under half a page. It runs about
> **1.2 pages**. I cut it from ~3 by moving evidence into the detail file; what is left is the six
> things the brief names in this deliverable, and cutting further would drop required content to meet
> a format rule. Flagged, not quietly accepted.

**Operating window:** **5 d 0 h 51 m** of scheduled operation — 33 scheduled runs,
2026-07-27T15:19Z → 2026-08-01T16:09Z (32 ok, 1 failed). The scheduler's own history and our ledger
agree on count and span.

**Build time (unpadded): ~[AHSAN: 30.5 + day 4/5/wrap] h.** 30.5 h is firm across six closed sittings
through day 3, each start and end supplied by hand. Days 4, 5 and the wrap are **not** estimated from
commit timestamps — the log's rule is that times are supplied, never inferred, and a rule applied
only when it flatters the total is not a rule. **[AHSAN — fill the four `[AHSAN]` cells in
`docs/SESSION_LOG.md`, then put the sum here.]**

**Main sessions.** Day 1 — plan, ops layer, run ledger, scheduler live; the tiered-ontology decision
(ADR-0028) taken *before* mass discovery, once the census showed FO-only 500 was aggressive. Day 2 —
domain resolution, gate v3 requiring published self-evidence, the agent + `fit_rank` at `POST /fit`,
first Stage 2 records, checkpoint email. Day 3 — auto-release band, 13F as a second source class,
registry re-check detector, record-level trust, release gates, robustness (ADR-0034–0040), full
adversarial review. Days 4–5 — funnel audit, the three goals, documentation, final review. Per-sitting
detail in `docs/SESSION_LOG.md`; the reasoning in 41 ADRs.

**AI vs me.** Claude Code generated most pipeline/agent code, the migrations, and the prompts. I owned
the architecture and every judgment call: the ontology that refuses to blend FO categories; a
deterministic gate with **human** release rather than blanket auto-release, kept refused at 54.8%
measured precision; the entity and decision-maker evidence standards; and the 500-shortfall framing —
3.9% measured yield stated honestly rather than releasing the 32 contradicted affirms to hit the
number. AI-proposed figures I corrected rather than shipped: a wrong ADV coverage figure, a
"~103 stranded never attempted" miscount, and the claim that a $0.000 cycle "is the common case",
which the end-of-window ledger falsified.

**The number I trust least: the qualifying count of 40** — specifically the 11 band-released records
in it. The band's 16/16 accuracy is measured on the calibration set its own thresholds were chosen
against. The out-of-sample review ADR-0034 requires was built on day 5 and immediately found that
**both records released via the CONCORDANCE route carry a client mix contradicting the entity claim**
(ANGELES 79% HNW / 0 non-HNW; ONEASCENT 43% / 43 — the band requires ≥90% and ≤15). Cause: route 2 is
documented as a fallback but implemented as an unconditional OR. Both are still in the shipped CSV,
not patched at the deadline because it changes release behaviour and `BAND_VERSION` is frozen pending
a superseding ADR. **Treat 40 as an upper bound with at least 2 known-soft rows**; the 29
human-ratified records are unaffected. **What would check it:** run `band-review` to human verdict
across all 11 and report out-of-sample precision with the sample size stated.

**Review attestation.** I personally reviewed every submitted file and every customer-facing state —
success, absence, uncertainty, partial data, failure — on the deployed system, not only in source.
**Not reviewed:** the other 9 band-released records individually; the 11,009-row operating ledger row
by row (schema, manifest totals and investigated runs only); every cell of all 40 records (three
validation chains end to end, adjudicated rows, remainder sampled).

> **[AHSAN — the attestation above is in your name and only you can make it true. Walk the live UI's
> failure and empty states since the last deploy before signing (~10 min; it is the one claim here a
> reviewer can trivially falsify), and cut anything you have not personally done.]**
