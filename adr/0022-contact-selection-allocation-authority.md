# ADR-0022: Contact selection — allocation authority first, conditioned on entity category

- **Date:** 2026-07-19
- **Status:** Accepted

## Context

Stage 1 chose primary/secondary contacts by a title-prestige ladder
(`gold/build.py::principal_rank`: founder 100 > … > CIO 80 > … ), with ties broken by extraction
order and the email graded only after selection. **Observed:** the ladder encodes seniority, not
investment authority; the buyer's question — who evaluates external managers? — is answered by a
CIO/head-of-investments at MFOs/RIAs, a role the ladder ranks *below* founder/CEO/president. The
Bridge Mandate names title-inferred authority as a Stage 1 weakness. **Assumed (to verify during
WS3):** ADV Part 2A brochures and site bios provide stated-authority evidence for a usable share of
the 50.

## Decision

Primary = the **best-evidenced entry point for an allocator conversation**, conditioned on the
ADR-0020 entity category: SFO → family principal/owner (they allocate), CIO second; MFO /
`ria_with_fo_practice` → stated investment authority first (CIO, head of investments, named
investment-committee member), owner second. Candidate ordering within a role: `stated` authority
evidence (bio language, ADV Part 2A committee naming, Schedule A officer status) beats
`title_inferred`; reachability (email grade / safe channel) is a tie-breaker between equally
evidenced candidates, never the driver. Every contact ships a `selection_basis` stating exactly why
this person is the contact. Applies to the original 50 in WS3 and to all Stage 2 records.

## Options considered

- **Option A (chosen):** allocation-authority first, category-conditioned, evidence-ranked,
  reason shipped.
- **Option B:** keep owner/seniority-first, add labels only. Rejected: labels the weakness without
  fixing it — the product would still route pitches to the most-gated inbox at MFOs.
- **Option C:** two typed slots ("Investment contact" + "Principal/owner contact"). Rejected for
  now: most honest shape, but breaks FO-MAX schema parity and touches CSV/UI/prompt/routing at
  once; revisit for Stage 2 if the brief frees the schema.
- **Option D:** rank by email deliverability first. Rejected: promotes wrong-role people because
  their mailbox works — reachability without authority is a fast bounce-out.

## Why this over the others

The record's value claim is "act on this today"; acting means reaching the person who can say yes
to a fund conversation. Authority-by-evidence, conditioned on what kind of entity this is, is that
person more often than the biggest title is — and shipping the selection reason converts an opaque
judgment into an auditable claim, consistent with the mandate's release-authority theme.

## Assumptions and risks

Assumes stated-authority evidence exists for a meaningful share of firms; where it does not, the
fallback is `title_inferred` with the label saying so (ADR-0021) — honest, not silent. Risk: the
category-conditioned rule is itself a judgment; a real SFO CIO may outrank the family head for
pitch response. Mitigation: `selection_basis` makes every choice inspectable, and the secondary
slot carries the other role.

## What would change this

WS3 adjudication finding stated-authority evidence for <~30% of the 50 (the rule would mostly
fall back to titles — then Option B's simplicity wins and this ADR gets superseded); the Stage 2
brief prescribing a contact schema; operating-window response data (if collectible) showing the
owner-first ordering outperforms at MFOs.
