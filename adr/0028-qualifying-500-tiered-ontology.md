# ADR-0028: Qualifying-record ontology for the 500 — tiered, labeled, never blended

- **Date:** 2026-07-27
- **Status:** Accepted (amends ADR-0024's product scope and the 2026-07-19 policy that only
  SFO/MFO count; decided by Ahsan on day 1, BEFORE mass discovery ran)

## Context

Observed (census, `data/census/*.json`, `docs/findings/stage2-source-census.md`): counting only
affirmed SFO+MFO, the realistic all-channel ceiling is ~335–570 affirmed records — 500 sits in the
aggressive upper half of what four channels yield only if everything performs at its top estimate.
The Stage 2 brief simultaneously sets 500 as "the bar, not a target to approach" and instructs
"define your own minimum inclusion standard and apply it"; its Goal 2 explicitly anticipates
records "ambiguous on whether they are a single-family office, a multi-family office, or a
registered adviser that is neither" living in the dataset with visible status. Assumed (estimate,
basis stated in the census): embedded-practice candidates add ~100–150 evidenced records on top of
the FO-only ceiling.

## Decision

A record counts toward the 500 only as a **unique resolved entity** carrying **affirmative evidence
for exactly one of three counted categories**, each visible on the record and on every surface:

1. `single_family_office` — serves one family; ADR-0020 evidence standard unchanged.
2. `multi_family_office` — serves multiple families as its business; ADR-0020 unchanged.
3. `embedded_fo_practice` (new) — a registered adviser or trust company with a **distinct,
   evidenced family-office practice**: a named FO division/service line with dedicated FO services
   substantiated by the firm's own materials AND a second source (ADV items, brochure, dedicated
   team/page). A tagline is not a practice.

Counts are always reported per-category — no surface ever says "500 family offices"; the honest
sentence is "N family offices (SFO+MFO) + M evidenced family-office practices." Wealth managers and
marketing-only labels remain excluded and non-counting. Stage 1's 7 `ria_with_fo_practice` firms
may re-enter qualifying only by clearing the category-3 evidence bar through adjudication; the 11
`wealth_manager` firms stay out.

## Options considered

- **Tiered ontology (chosen):** see above.
- **Hold FO-only and accept a documented shortfall:** rejected — the census makes a miss on the
  stage's central bar the *likely* outcome, not a tail risk; candor about a predictable shortfall
  is weaker than a pre-registered, evidenced standard the brief explicitly invites.
- **Count anything family-branded:** rejected without ceremony — that is Stage 1's named failure
  (marketing labels shipped as categories) and the exact claim-inflation the Bridge Mandate calls
  disqualifying.

## Why this over the others

The mandate punishes *blending and inflation*, not labeled ontologies: every named Stage 1 failure
was a claim stronger than its evidence. Category 3 keeps the claim exactly as strong as the
evidence ("this RIA runs an evidenced FO practice") and a paying fund manager hunting FO LPs
plausibly wants those records — family capital allocates through them. Deciding this on day 1,
before any mass discovery ran, with the census as the stated trigger, is threshold-setting under
the thresholds-before-measurement rule; deciding it on day 4 with a count in hand would have been
bar-moving, which is why the fork was forced today.

## Assumptions and risks

Assumes the category-3 evidence bar holds ~50%+ precision under sampled human review — if most
candidates clear it on thin evidence, the category inflates silently. Assumes reviewers read a
labeled ontology as honesty, not padding; the mitigation is that no surface ever aggregates the
three categories into one number. Risk: the Stage 1 reclassification language ("kept but NOT
counted") could be quoted against category 3 — the answer on the record is that those 7 firms were
excluded for lacking evidence, not for their entity type, and re-entry requires the evidence.

## What would change this

If sampled review of the first 50 category-3 records shows <50% would survive adversarial
adjudication, the category freezes (no new entries) and the release queue drops to SFO/MFO until
the evidence bar is rewritten. If the FO-only channels outperform the census and reach 500 on
their own, the headline count switches to FO-only with category 3 reported as a separate labeled
tranche — the stronger claim becomes available and we make it.
