# ADR-0012: FO-MAX parity enrichment — held-data fields + search-assisted LinkedIn

- **Date:** 2026-07-13
- **Status:** Accepted

## Context

Observed (measured, docs/findings + the sample workbook): scoring both datasets with our own rubric,
our primary contacts are real principals 88% of the time vs FO-MAX's 42% — we lead decisively on
*targeting quality*, and we populate the email chain they redact. But FO-MAX carries enrichment
*breadth* we lacked: Corporate LinkedIn (71% filled), Street Address (86%), URL Quality (92%), and a
person-level Contact Location (96%). Three of these are recoverable without a new source; one is not.

Observed: Street Address is already in our ADV bronze (`street1`/`street2`, 55/59 firms), and URL
Quality is derivable from our own website-fetch signals (page count, HTTP status, TLS). Corporate
LinkedIn is nowhere in the regulatory or on-site data — it needs an external lookup, which crosses the
"public regulatory + the firm's own site" line ADR-0004 drew.

Decision forced: do we add these parity fields, and if so, how do we source the one that requires
going outside our existing data — without importing the two problems ADR-0004 and ADR-0005 warned
against (opaque paid data, or confident guesses)?

## Decision

Add the four parity fields to `gold.records`. Fill **Street Address** and **URL Quality**
deterministically from data we already hold (gold-build time), and derive **Contact Location** from the
firm's city/state as an honest proxy. Fill **Corporate LinkedIn** via a **search-assisted enrichment**
stage: a web search per firm, disambiguated against the firm's domain / founder / city, recording an
**honest `null` rather than a guess** when nothing clearly matches. Because that search is agent-driven
(not a deterministic transform), commit the *results* as an auditable artifact
(`data/enrichment/corporate_linkedin.json`) and re-apply them idempotently via `load-linkedin` — the
search is a separate step from the load. Deliberately do **not** source contact *personal* LinkedIn or
phone numbers.

## Options considered

- **Held-data fields + search-assisted LinkedIn with honest blanks (chosen).** Closes the visible gaps
  (LinkedIn 54/59 = 92%, above FO-MAX's 71%) while keeping the honesty and provenance discipline.
- **Skip enrichment, stay purely regulatory + on-site.** Rejected: leaves a visible breadth gap on
  fields FO-MAX fills, for no good reason when three of four are cheap and honest to close.
- **Buy a data provider (as FO-MAX evidently does).** Rejected: cost, and it hides the method — the same
  reason ADR-0005 rejected a pure paid-API email verifier. We want to own and show the derivation.
- **Scrape/source personal LinkedIn + phone too.** Rejected on ethics/ToS grounds: these are exactly the
  cells FO-MAX *redacts* as paid value, and harvesting individuals' personal contact data is a different
  privacy posture than inferring a B2B work email. Left blank on purpose, not by omission.

## Why this over the others

It closes the gap that mattered for comparability without compromising the two things that make the
dataset defensible: honesty (blanks over guesses, and no personal-contact harvesting) and provenance
(every LinkedIn URL is in a committed file with what it was matched on). It also keeps the pipeline's
character intact — the deterministic fields stay deterministic; only LinkedIn is search-assisted, and
that non-determinism is quarantined behind a committed-results artifact so the *load* is reproducible
even though the *search* is not.

## Assumptions and risks

- Risk: search enrichment can mis-match a similarly named company. Mitigated by disambiguating on
  domain/founder/city and by preferring `null` — but not eliminated; the URLs are not individually
  verified against ground truth (5 of 59 were left blank, which shows restraint was exercised).
- Assumption: firm city/state is a reasonable stand-in for a founder's contact location. Usually true
  (principals sit at HQ) but not guaranteed; it is labelled as firm-derived, not asserted as person-level.
- This qualifies ADR-0004: sourcing is now "public regulatory + the firm's own site + a bounded,
  provenance-tracked search-assisted lookup for LinkedIn," not regulatory-only.

## What would change this

If LinkedIn accuracy needs to be guaranteed, verify each match (or use LinkedIn's official company API)
before shipping. If a funded, transparent data provider becomes acceptable, it swaps in behind the same
`enrich` stage. If the brief ever calls for personal contact data, that reopens the ethics decision
above — it would not be taken lightly.
