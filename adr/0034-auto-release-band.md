# ADR-0034: The auto-release band — releasing gate affirms the client mix corroborates

- **Date:** 2026-07-29
- **Status:** Accepted (supersedes ADR-0029's release policy; ADR-0029's gate design, precedence
  rule, and measurement discipline are unchanged)

> **Correction (2026-07-30, day 3 night).** Two claims below were wrong, found by auditing the
> funnel against the live database. Neither changes a threshold; both change what this ADR is
> entitled to say.
>
> **1. Route 2 was described as an alternative to registry evidence. It is not.** The text below
> said score ≥100 "requires the firm's name, its site's named FO practice, and its repeated
> self-description to all agree." Those three rules are `name_fo_strong` (40) +
> `site_fo_practice` (25) + `site_fo_selfdesc` (20) = **85**, which is below the bar. Reaching 100
> requires a fourth signal, and the only ones available are `adv_freetext_fo` (+15) or
> `structural_fo_shape` (+20) — **both registry-derived**. So the route offered as the fallback for
> firms with no usable client mix in fact requires registry corroboration of its own. Three
> candidates sit held at exactly 85 with exactly the described combination: Colony Family Offices
> (`cik:1633573`), OneAscent Family Office (`cik:2055812`), Noblehouse Family Office
> (`crd:338855`).
>
> **The threshold is not the error — the description is.** Measured over the calibration affirms:
> `score ≥100` is **12/12** counted-correct, `score ≥85` is **18/19** (it admits one human-labeled
> wealth manager at 95). Lowering the bar to match the prose would cost precision, and choosing 85
> *after* seeing which records it would admit is the bar-moving this project forbids. So 100 stands
> and the sentence is corrected instead.
>
> **2. The band's coverage across source channels was never measured, and it is uneven.** Route 1
> needs ADV client-mix fields. Measured presence of `hnw_raum` on queued candidates:
> **13F 0/20 · state_adv 27/119 · sec_adv 54/222.** The 13F channel therefore cannot use route 1 at
> all — ADV-exempt is the entire point of that channel (ADR-0035) — and with route 2 needing a
> registry signal, **no 13F candidate can auto-release**: max gate score observed across all 20 is
> **85**, and none reach 100. This is disclosed as a measured blind spot rather than patched, since
> a new release route built this late would be unmeasurable before submission. It is the honest
> reading of the band: it releases well on SEC-registered firms whose registry data is complete,
> and is structurally closed to the channel built to reach single-family offices. The dataset
> holding **zero** `single_family_office` records is the shape that predicts.

## Context

ADR-0029 built the inclusion gate and then refused to let it release anything: affirms entered a
human review queue. That refusal was correct and was **dictated by measurement** — gate-v2 scored
~59% strict affirm-precision, and releasing at that rate ships four non-family-offices in every ten
records, which is Stage 1's named failure at scale.

Two things have changed since.

**First, the cost of the refusal is now visible.** Qualification requires a human ratification per
record. Scheduled cycles have therefore contributed **zero** counted records across the entire
operating window: 23 gate affirms sit outside the product, and the qualifying set has only moved
when a human sat down with it. The brief is explicit that this is not the shape it wants —
*"Manual row-by-row construction does not satisfy the mandate"* — and the day-2 reconciliation
already recorded the intent to fix it (`docs/findings/stage2-brief-reconciliation.md`).

**Second, ADR-0033's fix was measured and did not work.** Gate-v3 added a published-self-evidence
requirement aimed exactly at the false-affirm failure mode. Measured today over the 67 human-labeled
entities: **54.8% counted-precision, 60.0% strict-FO precision** — essentially unchanged from v2.
The reason is visible in the misses and is worth stating plainly, because it kills a whole family of
proposed fixes: **every false affirm is a wealth manager that publishes "family office" all over its
own site** — Tarbox, Stokes, Long, Seneschal, Family Office Research. Self-published evidence cannot
separate a family office from a firm that markets itself as one, because both publish the same
words. No amount of reading the firm's own site harder will fix this.

## Decision

Introduce an **auto-release band** (`pipeline/gold/release_band.py`, `BAND_VERSION`, frozen before
it released anything). A gate affirm auto-releases only when at least one holds:

1. **Client-mix consistency** — the registry's own numbers corroborate the entity claim: ≥90% of
   regulatory AUM from high-net-worth clients **and** ≤15 non-HNW clients; or
2. **Concordant published evidence** — gate score ≥100. *(Corrected 2026-07-30: this was originally
   described as name + site practice + self-description agreeing, which scores 85. Reaching 100
   requires those published signals **plus** a registry corroborator — `adv_freetext_fo` or
   `structural_fo_shape`. Route 2 is therefore a published-evidence route that still needs the
   registry to agree, not an escape hatch from it. The threshold is unchanged and measures 12/12;
   see the correction note at the top.)*

Everything else stays in the human review queue exactly as ADR-0029 specified. **Human adjudication
still outranks the gate wherever both exist** — unchanged.

A band-released record:

- carries `release_basis = 'gate_released'` and a `release_basis_detail` stating the evidence that
  cleared it, **on the record and in the CSV**, so a buyer can tell it from a human-ratified one;
- counts on **entity evidence alone**, which is ADR-0028's pre-registered standard (entity-strict,
  field-permissive), and
- **ships no decision-maker.** `person_status = 'not_established'`, contact fields empty. The band
  establishes *what the firm is*; nothing in it establishes *who allocates*. Shipping an
  extracted-but-unratified name as the proven decision-maker is precisely the
  claim-stronger-than-evidence failure the Bridge Mandate corrected, and volume pressure is not a
  reason to reopen it.

Measured band precision over the calibration set: **16/16 counted (100%), 14/16 strict-FO (87.5%)**.
`release_band.measure()` recomputes both from the artifact on demand; no surface hand-carries them.

## Why the client mix, and why this is not curve-fitting

The rule's **shape** is principled, not fitted: a family office's regulatory book is essentially all
high-net-worth *by definition of what a family office is*. The false affirms fail it structurally —
Chilton at 39% HNW share with 1,172 non-HNW clients, TFO Wealth at 895, Superior at 431, Stokes at
341 — while every true affirm sits at 0.90–1.00 with a small tail. This is the same evidence a human
adjudicator used to call those firms wealth managers; the band just reads it in code.

**The thresholds, however, were chosen with the calibration set in view, and that is a real
governance weakness.** The Bridge Mandate says: *"Do not set the threshold after seeing the score."*
Three mitigations, all of them actual rather than rhetorical:

- the thresholds are round numbers taken from the principle (≥90% HNW, a de-minimis non-HNW tail),
  not the values that maximised the metric — a sweep found marginally better numbers and they were
  **not** used;
- `BAND_VERSION` is frozen before the band released a single record, so any later change is visible
  in the data itself; and
- **sampled human review of released records is mandatory**, and it is the only measurement that
  can actually falsify the band, because it measures out of sample.

The honest statement of what is known: the band is 16/16 on the set its thresholds were chosen
against, which is evidence but not proof, and the out-of-sample number does not exist yet.

## Options considered

- **Band-limited auto-release (chosen).**
- **Keep ADR-0029 unchanged (human ratification for all):** rejected — the count cannot move
  unattended, which fails the mandate's central requirement from the other side. Its own measurement
  is what justified revisiting it.
- **Blanket auto-release of gate affirms:** rejected by measurement, twice — at 54.8% precision it
  ships ~45% non-family-offices. This is what the day-2 reconciliation contemplated before the
  measurement existed; the measurement overrules it.
- **Raise the gate's affirm threshold instead:** rejected — it moves the same trade-off into a place
  where it is *less* visible. A record excluded by a higher bar is silently gone; a record held out
  of the band is still in the review queue with its reason recorded.
- **Ship gate-released records with their extracted contacts:** rejected — that is the exact
  Bridge Mandate violation, and it would trade the one thing that is genuinely proven here (the
  entity) for the thing that is not (the person).

## Assumptions and risks

Assumes the client-mix fields are populated and honest in the registry; firms filing no usable mix
fall back to the concordance route or stay in review (measured: 1 of 15 pending affirms).
*(Corrected 2026-07-30: both halves of that sentence were too optimistic. The fallback does not
function as described — route 2 needs a registry signal of its own, per the correction note above —
and the incidence was far understated: of 37 affirms the band has now evaluated, **28 are held and 9
of those for "no usable client mix on file"**, including every 13F candidate. The measured
per-channel coverage of `hnw_raum` is 13F 0/20, state_adv 27/119, sec_adv 54/222.)* Assumes
the calibration set represents the mass — state-channel and 990-PF candidates may distribute
differently, and the sampled review exists to catch that. **Known and disclosed:** the band's
*category* label is weaker than its *release* decision (14/16) — two released records the gate calls
multi-family-office are human-labeled RIA-with-an-FO-practice, i.e. they belong in the counted set
but under category 3. Since ADR-0028 forbids blending the categories into one number, a category
error is a real error, and it ships on the record as a stated caveat rather than being smoothed
away.

## What would change this

If sampled review of the first released tranche measures counted-precision below ~85%
out-of-sample, the band freezes and released records revert to the review queue — the release basis
column makes exactly that reversal possible, per record, without touching human-ratified rows. If
category errors exceed the 14/16 measured here, the band stops assigning categories and releases
everything as "counted, category pending" rather than guessing between MFO and category 3.
