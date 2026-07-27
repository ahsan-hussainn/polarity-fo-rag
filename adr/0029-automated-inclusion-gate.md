# ADR-0029: Automated inclusion gate — deterministic triage, human release, measured precision

- **Date:** 2026-07-27
- **Status:** Accepted

## Context

ADR-0028 defines what counts toward the 500; something must decide it at scale. The original
records were qualified by per-firm human ratification — observed: that took a multi-day
workstream for 50 firms; it cannot cover 661+ candidates inside the window. The brief requires
automation of the repeatable work while keeping judgment visible in policies and release
decisions, and the Bridge operating standard allows sampled (not exhaustive) human review for the
mass — at a rate the evidence justifies. Observed constraint from ADR-0023's reasoning: a release
control must not be LLM-dependent.

## Decision

A deterministic, versioned rule gate (`pipeline/gold/gate.py`, `gold.entity_gate`): every
candidate gets a scored evidence list (name signal, site self-description, site-named practice,
ADV free-text, client-mix structure, domain; contradictions for institutional/retail scale), a
decision — affirm / needs_evidence / exclude — and, on affirm, an ADR-0028 category. Embedded
practice requires BOTH independent sources (site-named practice AND ADV free-text). **Human
adjudication outranks the gate wherever both exist.** Identity is resolved via namespaced keys
(`crd:` — shared by SEC and state registrants — `cik:`, `ein:`) with `gold.identity_links`;
discovery advances through `ops.candidate_queue` with run-claimed, resumable stage transitions.

**Release policy, dictated by measurement:** calibrated on the 59 human-labeled entities, gate-v2
measures 20/24 recall on affirmed FOs and 9/9 on curation exclusions, but only ~59% strict
affirm-precision (marketing-named wealth managers still affirm falsely). Therefore a gate-affirm
does NOT auto-release: affirms enter a human review queue with the evidence list pre-assembled
(the gate collapses ~661 candidates to ~150 review items — that is what makes 500 reviewable
in-window); needs_evidence routes to enrichment; excludes ship unreviewed except a sample to
estimate false-exclusion loss (measured at 3/24 on the calibration set).

## Options considered

- **Deterministic scored rules + human review of affirms (chosen).**
- **LLM-judge gate:** rejected — an LLM deciding release is the exact control ADR-0023 was built
  to avoid; prompt-only judgment is explicitly below the brief's floor.
- **Auto-release gate affirms with sampled review:** rejected by the measurement — at ~59%
  precision, sampling would knowingly ship ~4 non-FOs in every 10 releases; that is Stage 1's
  named failure with extra steps.
- **Extend per-firm human ratification to all candidates:** rejected — does not fit the window,
  and automating none of the repeatable work fails the mandate from the other side.

## Why this over the others

The gate is honest about what regex-and-structure evidence can and cannot establish, because we
measured it before trusting it. v1 was pre-registered; calibration exposed one missing evidence
class (affirmed FOs self-describing as family offices without the suffix words v1 looked for —
Wellspring 12 phrase hits, scored zero) and v2 added exactly that rule and froze. Every decision
row carries its full evidence list, so a reviewer confirms or overturns in seconds, and every
override lands in `gold.entity_adjudications` where it permanently outranks the gate.

## Assumptions and risks

Assumes the calibration set (59 SEC-registered firms) represents the mass — state-feed and
13F-sourced candidates may distribute differently; the first reviewed tranches will measure that.
Assumes review throughput of affirms is feasible (~150 items with pre-assembled evidence).
False-exclusion risk is real and measured (3/24 evidence-poor sites); the mitigation is
enrichment-then-regate, not looser rules. Site-text rules can be gamed by marketing copy — which
is why affirm ≠ release.

## What would change this

If the first ~50 reviewed gate-affirms from the mass measure materially different precision than
the calibration set (in either direction), the review rate is recalibrated and recorded here. If
a v3 rule change is ever wanted mid-window, it requires a superseding ADR and a re-run of the
calibration report — the frozen version string in `gold.entity_gate.gate_version` makes any
silent drift visible in the data itself.
