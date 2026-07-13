# ADR-0015: Gold curation gate — entity validity is a validated cell, not an assumption

- **Date:** 2026-07-13
- **Status:** Accepted

## Context

A pre-submission review of the gold CSV against the brief surfaced the highest-severity finding of the
build: **the file contained records that are not family offices.** Oak Hill Advisors (~$112B
institutional credit manager), Clearlake Capital (institutional PE), Hamilton Lane, Aksia, Cliffwater,
Mariner, Parvus, and Naya Capital all entered via ADV *free-text* matching — firms that merely mention
"family office" in a filing. A second failure rode in with them: for some firms the ADV `WebAddr` points
at a **different company** (SpiderRock → blackrock.com after its acquisition), so every website-derived
cell described the wrong entity.

Two of our own artifacts had already flagged this and we failed to act on them:
`stage2-website-fetch.md` explicitly named Hamilton Lane as an asset-manager false positive, and
`gt-crosscheck` flagged Oak Hill's 15/15 "principals" at a firm reporting 435 employees. The signal was
observed, recorded — and not wired into the gold build. That is exactly the "measured but not acted on"
failure the How-We-Work loop exists to prevent.

## Decision

Add an explicit **curation gate** between silver and gold (`pipeline/gold/build.py::EXCLUDED`):
a firm ships only if the entity-validity judgment passes. Nine firms are excluded, each with a written
reason, persisted to **`gold.excluded_firms`** (migration 0007) so the judgment is auditable data, not
a silent deletion. The gate is code, so re-running the pipeline cannot resurrect an excluded record.
Result: exactly **50 records**, all defensible as family offices / multi-family offices / wealth
managers whose family-office practice is the entity ADV registers.

## Options considered

- **Exclude with recorded reasons (chosen).** Smaller, honest file; judgment auditable; count lands on
  the brief's 50 exactly.
- **Keep them with a classification column.** More candid-looking, but the brief asks for "50 real
  family office records" — a flagged hedge fund is still not one, and it dilutes every aggregate claim.
- **Re-enrich replacements from the candidate pool.** Correct long-term (207 enrichment-ready
  candidates remain), but not honest within the remaining window; noted as the first improvement.

## Assumptions and risks

- Judgment calls remain at the boundary (e.g. 1919 Investment Counsel, Chilton Trust, F.L.Putnam are
  wealth managers with family-office practices; TFO's two registrants share a parent and a domain).
  These are disclosed in the methodology's limitations rather than hidden.
- The gate is a manual allow/deny list informed by measured signals (crosscheck, AUM, employee count),
  not a trained classifier. At 59 firms that is proportionate; at 500 it would not be.

## What would change this

A measured firm-type classifier (SFO / MFO / RIA-with-FO-practice / not-FO) with its own labelled gold
set and FP/FN rates — the same harness `pipeline/eval.py` already applies to `is_principal` — would
replace the hand list. ADV Schedule D 7.A (family-office client types) is the natural feature source.
