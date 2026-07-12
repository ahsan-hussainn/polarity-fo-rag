# ADR-0011: Gold record shape — FO-MAX-mirroring, primary contact by seniority

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

Observed: silver is normalized (firms + people, one row each) — a workbench, not a product. The
deliverable a capital allocator consumes is the FO-MAX shape: **one row per family office**, with the
firm's facts and a **primary** (and secondary) **contact**, each carrying the email chain (address →
validation code → explanation → quality grade) plus a per-record completion score.

Observed (measured, docs/findings/validation-layer.md): the reference product's weakness is contact
*targeting* — FO-MAX's Walton primary contact is an "Accounting Manager," and our own extractor
over-includes principals (precision 0.49–0.78). So the gold layer must make a *choice* of who the
primary contact is, and that choice is exactly where the dataset earns or loses its "decision-grade"
claim.

Decision forced: what grain is gold, and how is the primary contact chosen?

## Decision

Gold is **one row per firm** (`gold.records`, keyed on CRD), mirroring the FO-MAX columns. The primary
contact is the firm's **most senior principal** by an explicit seniority rank
(`pipeline/gold/build.py::principal_rank`: Founder/Owner/Managing Partner > CEO/President/Chairman > CIO
> Principal > Portfolio Manager > MD > Partner), the secondary is the next. Each contact carries its
silver email grade chain unchanged. A `data_completion_score` (share of key cells populated) and
`principal_count` / `people_count` (the over-inclusion denominator) travel with every row.

## Options considered

- **Firm-grain, primary-by-seniority (chosen).** Mirrors FO-MAX for direct comparability, and the
  seniority pick is a concrete, inspectable answer to "who do I contact" — 36/42 firms with a team page
  now lead with a Founder/CEO/Chairman/CIO/Principal, vs FO-MAX's Accounting Manager.
- **Person-grain (one gold row per principal).** Richer, but not the product shape, and it dodges the
  targeting decision instead of making it. Kept as an easy view over silver if needed; not the gold form.
- **Primary = first-listed / highest email grade.** Rejected: first-listed is arbitrary, and ranking by
  email grade would put a well-verified junior above an unverifiable founder — optimizing the wrong axis.

## Why this over the others

The whole point of the dataset is *who to contact*; making that choice explicitly, by a documented
seniority rule, is the value. Firm-grain makes us directly comparable to FO-MAX on the same row shape,
and the seniority rank turns the measured over-inclusion into a concrete improvement — the gold row
surfaces the founder, not the bookkeeper. Completion score + people/principal counts keep the honesty
visible: a firm we could only partly enrich shows a low score rather than a confident-looking blank.

## Assumptions and risks

- Assumption: title text is a good enough seniority signal to pick the primary. Risk: a mis-titled or
  firm-name-as-person extraction (e.g. "Element Pointe / Founders") becomes the primary; low frequency,
  visible in the row, and fixable upstream in extraction rather than by re-architecting gold.
- Risk: `principal_rank` is a heuristic, not ground truth. It is measured indirectly — the is_principal
  FP/FN set (ADR-0007 Stage 6) bounds how often the pool it ranks over is wrong in the first place.
- The completion score is a coverage signal, not an accuracy signal; it says how full a row is, not how
  correct — accuracy stays the job of the validation layer.

## What would change this

If a consumer needs every decision-maker rather than a single primary, add a person-grain export
alongside (silver already supports it). If extraction quality on names/titles improves enough that
seniority ties are common, the rank gains tie-breakers (e.g. AUM authority signals). Neither changes the
gold grain.
