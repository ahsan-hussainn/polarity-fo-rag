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

**Build time (unpadded): 42.7 h** across eleven sittings — 30.5 h through day 3, plus the day-3 night
audit (3.0), day 4 (4.0), day 5 (4.0), a 40-minute phone sitting, and the wrap. Every start and end
was supplied by hand; none were reconstructed from commit timestamps, even where that would have
raised the number. Two disagreements between supplied times and the commit record are recorded rather
than reconciled in `docs/SESSION_LOG.md` — **both point downward**, so 42.7 h is likelier an
under-count than a padded one.

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

The customer-facing states were walked on the deployed system on 2026-08-02, after the final push:
success, absence ("there are no family offices based in Alaska", stated before alternatives are
offered), uncertainty (emails labelled inline as inferred on a catch-all domain, unconfirmable),
out-of-scope refusal with no sources, the withheld-answer state ("answer withheld — could not be
fully grounded in the dataset"), and service-unreachable. Two rough edges found and judged
non-blocking, both off the normal customer path: an unknown URL returns a raw `{"detail":"Not Found"}`,
and the query page renders a raw exception message into its error line.

— Ahsan Hussain, 2026-08-02
