# ADR-0033: Gate v3 — an affirm requires evidence the firm published about itself

- **Date:** 2026-07-28 (Stage 2 operating window, day 2)
- **Status:** Accepted
- **Supersedes:** the frozen `gate-v2` rule set in ADR-0029 (thresholds and scoring otherwise
  unchanged)

## Context

ADR-0029 froze `gate-v2` before mass discovery and reported ~59% affirm precision against the 59
human-labeled entities. Day 2 re-measured it more finely, and two things surfaced that the original
calibration could not have shown.

**1. Precision does not improve with score.** Measured across all calibration affirms:

| score band | n | correct | wrong | precision |
|---|---|---|---|---|
| ≥80 | 24 | 16 | 8 | 67% |
| 70–79 | 6 | 4 | 2 | 67% |
| 60–69 | 4 | 1 | 3 | 25% |
| **overall** | **34** | **21** | **13** | **62%** |

There is no high-confidence band. The top band still ships roughly one wrong record in three, which
settles a live question in the negative: **no threshold makes gate-only release safe**, so ADR-0029's
"an affirm is triage, and a human reviews it" stands unchanged. This ADR does not touch that.

**2. The calibration population does not resemble the production population.** Every one of the 34
calibration affirms carries website evidence, because the original 50 records all had working
websites. Half the live queue does not: 108 of 341 candidates carry a social-media URL in the ADV
website field and 66 carry none (ADR-0032). The gate is now judging a population its calibration
never contained, and the 62% figure carries no information about the no-site case.

That case has already appeared. Of 9 production affirms, **one rests on no site evidence at all**:
CRD 158302 (MACI FAMILY OFFICE ADVISORS), scored 60 on `name_fo_strong` (+40) plus
`structural_fo_shape` (+20). A firm named "family office" with an FO-shaped client mix and nothing
it has ever published about itself.

That combination contradicts two standards this project already holds. ADR-0020 requires **≥2
independent evidence classes** to affirm an entity, and a registered name is not an evidence class —
it is registry metadata, the same registry the client mix came from. ADR-0028 is blunter still: "a
tagline is not a practice," and a marketing label shipped as a category is Stage 1's named failure.
The gate was applying a weaker standard to 500 records than the standard applied by hand to 50.

## Decision

**An affirm requires at least one site-evidence rule to have fired** — `site_fo_practice`,
`site_fo_selfdesc`, `domain_fo`, or `silver_fo_desc`. Name and registry signals alone can reach
`needs_evidence`, never `affirm`.

Rationale in one line: an affirm must include something the firm says about itself, not only what a
registry says about it. Scoring, thresholds, contradictions, and the embedded-practice path are
unchanged. `GATE_VERSION` becomes `gate-v3`.

## Options considered

- **Raise `AFFIRM_MIN` 60 → 70** (the change originally proposed): **rejected on insufficient
  evidence.** It rests on the 60–69 band's 25% precision, and that band has **n = 4**. A
  four-record sample cannot carry a threshold change; the 95% interval on 1/4 spans roughly 1–70%,
  which is consistent with the band being fine. Deferred to real measurement, not adopted because
  the number looked bad.
- **Require registry AND site evidence (a literal ≥2-class rule):** tested and rejected on results.
  Precision rises 62% → 73%, but **13 of 21 true family offices are lost** — a 62% recall
  collapse. The large correct group is name + site with no registry signal (13 correct / 10 wrong);
  many genuine family offices simply do not describe themselves in ADV Item 5.G free text.
- **Do nothing and let human review catch it:** rejected. Review is the backstop, not the standard.
  Sending a reviewer a row whose only evidence is its own name spends the scarcest resource in the
  system on a decision the gate should not have escalated.

## Why this over the others

It is the only candidate with a **measured recall cost of zero**. All 34 calibration affirms already
carry site evidence, so precision and recall on the calibration set are unchanged — this rule
removes no true positive it has ever been shown. What it removes is a failure mode the calibration
set structurally could not contain, and which production has already produced.

It also aligns the automated standard with the human one. ADR-0020's two-independent-class bar was
argued for and ratified; the gate quietly applied something weaker. Closing that gap needs no new
justification, only consistency.

## Assumptions and risks

Assumes site evidence is obtainable for genuine family offices. ADR-0032's resolver exists precisely
because it often is not from the registry alone — and the two work together: the resolver recovers
the site, and this rule refuses to affirm until it does.

**Named risk: this trades recall for precision on the no-site population, and that trade is
unmeasured.** A real single-family office with a registered FO name, an FO-shaped client mix, and no
website is now `needs_evidence` rather than `affirm`. Such firms exist — a genuine SFO has no reason
to market itself. They are not lost, they are held for evidence, and the honest position is that we
cannot yet distinguish them from marketing labels using registry data alone. Recording that
explicitly rather than resolving it by preference.

Small-sample caveat applies to this ADR too: the production evidence is 1 of 9 affirms. The change
is justified by consistency with ADR-0020/0028, corroborated by that case — not established by it.

## What would change this

- If the reviewed sample shows `needs_evidence` rows blocked solely by this rule are affirmed by a
  human at a high rate, the rule is too strict and a name-plus-registry affirm returns with a
  category label that states its basis is registry-only.
- If the 60–69 band reaches **n ≥ 25** and precision stays under ~40%, `AFFIRM_MIN` rises to 70 in a
  superseding ADR — the change deferred above, then made on evidence.
- If precision on the post-resolver population diverges materially from 62%, the gate is
  re-calibrated against a sample drawn from the *current* population rather than the original 50,
  since this ADR's central finding is that the two differ.
