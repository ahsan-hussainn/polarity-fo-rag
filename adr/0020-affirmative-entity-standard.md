# ADR-0020: Affirmative entity standard and identity resolution

- **Date:** 2026-07-19
- **Status:** Accepted

## Context

Bridge Mandate correction #2. Stage 1's entity logic was **negative**: discovered in SEC ADV +
family-office-like text + not on the ADR-0015 exclusion list ⇒ shipped as a "family office."
**Observed** (WS0 audit): two shipped records share `tfopartners.com` (affiliate pair counted
twice); METHODOLOGY itself discloses wealth managers kept in the file (1919, Chilton, F.L.Putnam).
**Structural fact:** true single-family offices are typically *exempt* from SEC registration (the
family-office exclusion), so a registered-adviser-only base is likely mostly MFOs and
RIAs-with-FO-practices — the label must follow the evidence, and reclassification is the expected
honest outcome, not a failure.

## Decision

Every record must **affirmatively prove** its category before release. Categories:
`single_family_office` · `multi_family_office` · `ria_with_fo_practice` · `wealth_manager` ·
`not_fo` · `unresolved`. Proof requires **≥2 independent evidence classes** (ADV Item 5 client-type
composition; the firm's own self-description, captured as source URL + quoted span + observed date;
third-party corroboration) — a page merely *mentioning* family-office services is not evidence of
*being* one. The category, status, and evidence are stored on the record and enforced: only affirmed
FO categories (`single_family_office`, `multi_family_office`) count toward "family office" claims
and the 500; `ria_with_fo_practice` and `wealth_manager` ship visibly labeled; `unresolved` is
**quarantined** — not released, not counted, not retrievable. Identity resolution runs first:
records sharing domain, address, or ADV Schedule A owners collapse to one entity unless evidenced
as separate offices. The stable identifier (CRD) is added to the exported artifact.

## Options considered

- **Option A (chosen):** affirmative per-category evidence rules + labeled non-FO categories.
- **Option B:** FO-only product (exclude reclassified firms like ADR-0015 did). Rejected: guts the
  base given the all-registered composition, and destroys honestly-labeled inventory PolarityIQ's
  own product segments by entity class.
- **Option C:** show unresolved entities with an "unresolved" badge. Rejected: weaker
  release-authority story; at 50 records we can afford to actually resolve them.
- **Option D:** single-evidence qualification (self-description alone). Rejected: a marketing page
  is one interested party's claim; the Stage 1 failure was exactly trusting one source class.

## Why this over the others

The mandate's test is that the label follows the evidence, per record, visibly. Two independent
evidence classes is the cheapest standard that survives a hostile sample check; labeled categories
convert an embarrassing reclassification into sellable precision.

## Assumptions and risks

Assumes ADV Item 5 client types + site language can separate MFO from wealth-manager in most cases —
uncertain for hybrid firms; borderline calls will be recorded with the evidence and the judgment,
not silently binned. Risk: the affirmed-FO count of the original 50 lands well under 50; accepted —
that number is the honest base and is reported plainly.

## What would change this

The official Stage 2 brief defining its own ontology (theirs wins); an evidence class proving
unreliable during adjudication of the 50 (e.g. ADV client-type buckets too coarse), which would
force a revised rule set *before* the 450 are adjudicated; discovery of non-registered FOs in
Stage 2 requiring category evidence rules that don't depend on ADV at all.
