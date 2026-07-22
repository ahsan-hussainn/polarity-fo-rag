# ADR-0025: Decision-grade record enrichment — reachability, confidence, freshness, signals

- **Date:** 2026-07-22
- **Status:** Accepted

## Context

A record that is merely *complete* (cells filled) is not *decision-grade* (a buyer can act on it). The
existing `data_completion_score` measures completeness only, and treated a proven firm-published email
the same as a filled-but-weak one. **Observed** (WS6 review): a fund manager deciding *whom to
contact, why them, why now, how much to trust it* needs signals the completeness score does not carry.
Bridge Mandate correction #6 also requires time-sensitive signals (recent investments/hires/news),
dated and sourced, whose staleness visibly affects trust. This ADR records the enrichment layer added
to the 24 qualifying family offices.

## Decision

Four record-level KPIs, all with their basis on the artifact:

- **Reachability** (tier + 0–100): how directly you can reach the *proven* decision-maker. The email
  is the only direct-to-person channel; phone/LinkedIn are firm-level cold routes. High = usable email
  (PUB firm-published or A vendor-deliverable); Medium = plausible email (B) or phone+LinkedIn; Low =
  a single cold route. (Renamed from "actionability" — the metric measures reach, not the holistic
  act; migration 0015.)
- **Confidence** (0–100): how well-*proven* the record is — affirmed entity (≥2 evidence classes) +
  person proof (stated > title-inferred) + email proof (published proves ownership; inferred does
  not). Distinct from reachability: a record can be high-confidence, low-reachability.
- **Freshness**: `data_asof` (the SEC ADV filing date) + a `Stale?` flag past the annual-filing
  window — correction #6's "record when evidence was observed; staleness affects trust."
- **Time-sensitive signals** (`gold.record_signals`, migration 0014): dated, sourced recent events
  (investment / hire / leadership-change / news / growth), researched per firm and ratified; the RAG
  weaves the most recent in as the "why now." 27 signals over 17 of 24 FOs; 7 honest blanks, no
  invented events.

Weights are heuristic and documented in `build.py`; the KPIs summarise the underlying proof columns,
which a buyer can still read directly. "Actionability" as a holistic idea = reachability + confidence
+ a recent signal, read across columns rather than fudged into one number.

## Options considered

- **Option A (chosen):** separate honest KPIs (reachability / confidence / freshness) + dated signals.
- **Option B:** one blended "actionability 0–100". Rejected: the inputs are categorical and distinct
  (reach vs proof vs recency); one number would hide which axis is weak and imply false precision.
- **Option C:** defer all of correction #6 to the Stage 2 window. Rejected: we are perfecting 24
  records now; the signal *fields + initial dated population* are the same work either way, and they
  make the record decision-grade. (The *operating refresh loop* is still window work — see risks.)
- **Option D:** infer/guess signal dates to fill blanks. Rejected: a signal without a real date +
  source is not a signal; honest blanks (7 firms) are correct.

## Why this over the others

The mandate scores on actionability and on evidence made visible. Three honest axes a buyer can sort
and inspect beat one opaque composite, and dated/sourced signals answer the "why now" that turns a
contact list into intelligence.

## Assumptions and risks

The KPI weights are judgment, not measured — defensible and tunable, but not validated against
outcomes. **Correction #6 is only half-built here:** the signal fields carry an *initial* population;
the mandate's "the system notices changes and adjusts over time" is the Stage 2 operating agent, not
this pre-window snapshot — disclosed as such. Signals age; without the refresh loop they will go
stale, which is exactly why the loop is the next build.

## What would change this

The Stage 2 agent taking over signal refresh (this becomes its seed); measured outcome data letting
the KPI weights be tuned rather than asserted; the official brief prescribing its own record schema or
KPI definitions.
