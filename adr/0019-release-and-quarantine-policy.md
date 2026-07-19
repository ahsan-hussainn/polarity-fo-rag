# ADR-0019: Release and quarantine policy for vendor-rejected contact data

- **Date:** 2026-07-19
- **Status:** Accepted

## Context

Bridge Mandate correction #1. **Observed** (WS0 audit, `docs/findings/bridge-audit-reconciliation.md`):
the shipped file carries 28 vendor-rejected email addresses (grade D, `INVALID_API`; 16 primary,
12 secondary) in operational fields, surfaced to the UI as tagged alternatives and rendered into the
answer prompt; 4 F-grade slots (`INVALID_NO_MX`) ship blank cells but keep their grade metadata.
The Stage 1 system *graded* honestly and *released* unsafely — "a check that does not control what
ships is measurement without authority." Policy fixed 2026-07-19, **before** re-measurement, per the
mandate's thresholds-before-measurement rule.

## Decision

Vendor-rejected values (codes `INVALID_API`, `INVALID_NO_MX`) move to an audit table
(`gold.contact_audit`) and their operational columns become NULL — enforced in the gold build, so a
rejected value structurally cannot reach the CSV, the prompt, the API, or the UI. Every record gets
a `release_state` (`qualifying` / `quarantined` / `unresolved`) plus reasons. **Qualifying** requires:
entity affirmed (ADR-0020), identity resolved, no rejected values operational, person block honest
(ADR-0021). Records with no proven contact route still qualify, honestly labeled, but rank at the
**bottom of the release queue** (last-resort fill toward the 500). C-grades (`UNKNOWN_API`) stay,
labeled "unconfirmed — vendor could not verify," never a recommended channel.

## Options considered

- **Option A (chosen):** quarantine table + record release state, enforced at the build layer.
- **Option B:** suppress rejected values at display time only. Rejected: the data stays operational
  underneath — the exact Stage 1 failure; suppression must hold on *every* surface including exports.
- **Option C:** delete rejected values outright. Rejected: the mandate explicitly permits an audit
  history, and the evidence (which patterns failed, when) is needed for future re-verification.
- **Option D:** quarantine C-grades too. Rejected: the vendor did not reject them; conflating
  "unknown" with "known bad" is itself imprecise labeling.

## Why this over the others

Authority must be structural, not behavioral: one choke point (the build) that cannot write rejected
values beats N renderers each remembering to hide them. The trust-ranked queue resolves the
actionability-vs-honesty tension: honest-blank records ship (candor) but never displace records a
client can act on (sellability).

## Assumptions and risks

Assumes a vendor rejection is sufficient evidence of unsafety for release (the mandate states this);
the vendor can still be wrong in both directions — accepted, with re-verification as the remedy, not
retention. Completion scores of affected records will drop because dead contact fields no longer
count as populated — an honest decrease, disclosed.

## What would change this

A second independent verifier contradicting the first on the same address (forces an arbitration
policy rather than single-vendor authority); the official Stage 2 brief defining release
requirements that differ from these; re-verification converting a D to deliverable (the value
returns from audit to operational with a fresh, dated verdict).
