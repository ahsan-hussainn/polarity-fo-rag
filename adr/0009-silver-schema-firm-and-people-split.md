# ADR-0009: Silver schema — firm + person split, believed vs verified cells

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

Observed (fact): Stage 3 extraction (ADR-0008) yields two grains of data from one firm's website —
firm-level facts (thesis, description, sectors, founded_year) and a team list where each person
carries a machine-set `is_principal` flag plus a reason. Bronze holds one append-only row per fetched
*page*; the silver layer is *defined* as normalized + entity-resolved (ADR-0006), so it must collapse
a firm's several pages into stable records before anything downstream can measure them.

Observed (fact): the FO-MAX reference schema chains its paid value at the **contact** level —
email → validation code → explanation → quality grade → per-record completion score. The validation
layer that is our differentiator measures false-positive / false-negative rates on exactly two cells,
and both are per-person: `is_principal` (principal targeting) and `email` (contact intelligence).

Observed (fact): ADR-0003 calls for per-cell `*_source` + `*_verification`. Read maximally that means
a source/verification pair on every column. This dataset is ~50 decision-grade records, and at the
firm grain every extracted field derives from the *same* fetched page-set (one lineage), so a
per-column `*_source` on firm facts would be redundant bookkeeping.

Decision forced: freeze the silver shape before loading records and building the validation layer on
top of it — the shape is expensive to change once gold + ground-truth depend on it.

## Decision

Two tables. `silver.firms` = one row per firm (keyed on SEC CRD, the entity resolution key).
`silver.people` = one row per named person, the grade-able contact unit. Believed facts sit in plain
columns; VERIFIED facts (`email_status`, `email_verification`, `quality_grade`) sit in their own
columns and are NULL until the validation layer fills them — a NULL is an honest "not yet verified,"
never a guess. Firm-level provenance is carried as `source_urls[]` + `bronze_ids[]` arrays (one shared
lineage), and the believed-vs-verified split is realized where it earns its keep: the contact email
chain on `silver.people`.

## Options considered

- **Normalized firm + person split (chosen).**
- **One denormalized firms table with `team` as a jsonb blob:** simpler to write, but the team member
  is the unit the ground-truth set grades and the SMTP-verify / grading stages join against. FP/FN is
  computed per person; a jsonb blob is not cleanly indexable, joinable, or updatable per row. Rejected.
- **Literal ADR-0003: `*_source` + `*_verification` on every column of every table:** faithful to the
  maximal reading, but redundant at the firm grain where all cells share one page-set lineage, and it
  bloats the schema for a 50-record dataset. Kept the pattern only where believed and verified actually
  diverge — the per-person email chain. Rejected as primary.

## Why this over the others

The split mirrors where FO-MAX puts its value (the contact record) and puts the grade-able unit —
the person — in its own indexable, joinable table, which is precisely what the validation layer and
the SMTP verifier attach to. The believed-vs-verified separation is legible in the column layout
itself: `email` / `email_pattern` are believed; `email_status` / `email_verification` /
`quality_grade` are verified and start NULL. That makes the "believed vs verified" reasoning trail a
property of the schema, not a convention someone has to remember.

## Assumptions and risks

- Assumption: one firm ≡ one CRD is a clean entity key. Risk: relying/sub-advisers can share or branch
  CRDs; low at this scale — revisit with a surrogate `firm_id` + resolution table if collisions appear.
- Risk: re-running extraction replaces `silver.people` wholesale (delete-then-insert), which would
  clobber validation columns once they are populated. Accepted now because re-extraction is a
  deliberate act and the validation layer is not built yet; when it lands, switch to a merge keyed on
  `(firm_crd, name)` or version the people rows.
- Risk: `people.source_url` is stamped as the firm's home page, not the exact page a name came from —
  the extractor does not return per-person provenance. Acceptable granularity gap; noted, not hidden.

## What would change this

Ground-truth work needing per-field provenance at the firm grain would add `*_source` columns to
`silver.firms`. Entity collisions on CRD would introduce a surrogate `firm_id` and a resolution table.
The validation layer being built would trigger the `(firm_crd, name)` merge to stop clobbering verified
cells on re-extraction. None of these change the firm/person split itself.
