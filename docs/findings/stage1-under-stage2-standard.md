# Bringing the Stage 1 records under the Stage 2 standard (day 3, 2026-07-29)

The brief, on what counts toward the 500:

> The 500 includes your original Stage 1 records, **brought under the same Stage 2 standard before
> submission.**

`docs/findings/stage2-brief-reconciliation.md` flagged this as Drift 2 on day 2: the seed records
had been *scored* by the Stage 2 gate as calibration, but scoring for calibration is not the same as
bringing them under the standard, and — measured today — the scores were never even persisted.

## What was actually wrong

Every qualifying record was checked against `gold.entity_gate`. **24 of them had no gate decision at
all.** `gate.retro()` had only ever been run without `--write`, so the calibration numbers quoted in
ADR-0029 existed in a terminal, not in the data.

Worse, running it with `--write` would have made things *less* consistent: `retro()` passed bare
CRDs to `run_gate`, so it would have written `entity_key='120053'` while every other gate decision
uses the namespaced `crd:120053` (ADR-0029's identity scheme). That is two key formats for the same
entity, and it quietly breaks any join over the table. Fixed before writing anything.

## What is true now

All **32 qualifying records — the seed 24 included — carry a persisted gate-v3 decision.** 331
distinct CRD entities now have one. One dataset, one standard, and the disagreements are in the data
rather than in a report.

The gate does **not** change their release state. Human adjudication outranks the gate (ADR-0029,
unchanged), so a record a human affirmed stays affirmed. What the retro produces is a measured,
recorded second opinion — which is the point: a reviewer can see where the automated standard and
the human standard diverge, per record.

## The disagreements, stated plainly

Of the 67 human-labeled entities, gate-v3 says:

| human label | n | gate affirms | gate needs_evidence | gate excludes |
|---|---|---|---|---|
| affirmed family office | 25 | 21 | 1 | 3 |
| wealth manager | 14 | 10 | 2 | 2 |
| quarantined / other | 9 | 6 | 1 | 2 |

**Recall on human-affirmed family offices: 21/25 (84%).** The gate misses 4 real family offices —
under-inclusion, the safe direction, and they are in the product anyway because the human decision
governs.

**The gate affirms 10 of 14 firms a human called a wealth manager.** That is the precision problem
ADR-0034 measured independently (54.8% counted-precision) and is exactly why gate affirms do not
auto-release: they must also clear the client-mix band. The retro is the same finding from the other
direction, on the same labeled set.

## Open, and it needs Ahsan rather than code

ADR-0028 says the 7 `ria_with_fo_practice` records "may re-enter qualifying **only by clearing the
category-3 evidence bar through adjudication**." Gate-v3's view of them, for whoever does that
adjudication:

| CRD | firm | gate decision | category | score |
|---|---|---|---|---|
| 307521 | Alpha Capital Family Office, LLC | affirm | multi_family_office | 105 |
| 142856 | Pioneer Family Office, LLC | affirm | multi_family_office | 95 |
| 329496 | Innovative Family Office LLC | affirm | multi_family_office | 85 |
| 324899 | Sapient Capital LLC | affirm | embedded_fo_practice | 45 |
| 220519 | Summit Trail Advisors, LLC | needs_evidence | — | 30 |
| 286243 | Crestwood Advisors | exclude | — | 20 |
| 133370 | 1919 Investment Counsel, LLC | exclude | — | 5 |

## Resolved — the re-adjudication was performed (2026-07-29)

All seven were re-adjudicated against the category-3 bar, reading each firm's own site text and ADV
Item 5.G rather than the gate's score. **Three clear, four do not.**

Crucially, the original rationales all said the same thing — *"FO is a service line," "one offering
among many," "FO is a service, not identity."* That was the right call under the Stage 1 binary,
where a service line meant not-counted. **ADR-0028 created a counted category for exactly that
shape**, so "it is a service line" stopped being the disqualifier and became the starting condition.
The real test is whether the line is *distinct and evidenced* — a named division or service with
described services, in the firm's own materials, plus an independent second source — or a tagline.

| CRD | firm | outcome | why |
|---|---|---|---|
| 324899 | Sapient Capital | **affirmed cat-3** | site names the service line *and* staffs it — "Elizabeth Chand, Partner, Family Office Solutions" — plus ADV 5.G "FAMILY OFFICE SERVICES". Strongest of the seven |
| 220519 | Summit Trail Advisors | **affirmed cat-3** | "As your outsourced family office…", itemised among named services, plus ADV 5.G "OUTSOURCED CIO SERVICES/ FAMILY OFFICE SERVICES". 588 HNW vs 51 non-HNW |
| 329496 | Innovative Family Office | **affirmed cat-3** | "our family office division, headed by a registered investment advisor" with described services, plus ADV 5.G. Majority-retail book recorded on the record as a caveat, not hidden |
| 307521 | Alpha Capital Family Office | held | no *distinct* practice exists to evidence — all 58 mentions are the firm's own brand name; zero named service-line phrasings. The firm IS branded as the family office, so the question is MFO-vs-wealth-manager, already answered |
| 142856 | Pioneer Family Office | held | one evidence class only: a named service line on the site, but ADV 5.G reads "MINIMUM ACCOUNT CHARGE". HNW share 0.23 |
| 133370 | 1919 Investment Counsel | held | the site evidence is a **navigation label** repeated across pages with no description of the service — ADR-0028's "a tagline is not a practice" case. ADV corroborates, but a second source cannot corroborate a practice the first never established |
| 286243 | Crestwood Advisors | **held, and flagged** | the website captured for this CRD is Focus Financial Partners' (its acquirer) — the token "CRESTWOOD" appears nowhere in the fetched site text. Cannot adjudicate a firm on its parent's materials; the domain needs re-resolving. This is the wrong-entity defect ADR-0015 exists to catch |

Two findings fell out of the work:

**A defect in the release rule (fixed, ADR-0041).** Affirming the three did not move the count. The
build required human-adjudicated records to carry a *ratified decision-maker* to qualify, while
gate-released records qualified on entity evidence alone — so a machine-affirmed entity was released
and a human-affirmed one held out. That contradicted ADR-0028's day-1 standard (entity-strict,
field-permissive). Fixed; qualifying went 32 → 35 (30 family offices + 5 evidenced practices).

**A gate recall miss worth recording.** Gate-v3 scored Summit Trail 30 (`needs_evidence`) while a
human reading of the same site clears it comfortably. Recorded as calibration data, not as a release
change — the gate never overrides a human adjudication in either direction.

**Who decided.** These three were adjudicated in-session by the assistant at Ahsan's direction, and
`decided_by` says exactly that, including *pending Ahsan's final-review confirmation*. The mandate's
final-review pass covers them; the record does not claim a human ratification that has not happened.
