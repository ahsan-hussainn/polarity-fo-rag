# Inclusion-gate calibration — measured before trusted

_2026-07-27, day 1 of the operating window. The ADR-0029 gate was calibrated against the 59
human-labeled entities (50 ratified adjudications + 9 curation-gate exclusions) BEFORE any mass
discovery ran. Full machine-readable report: `data/curation/gate_calibration_v2.json`. The gate
never overrides these labels — human adjudication outranks it — so every number here is
measurement, not a release change._

## Results by version

| Metric | gate-v1 (pre-registered) | gate-v2 (frozen) |
|---|---|---|
| Recall on 24 human-affirmed FOs | 16/24 (67%) | **20/24 (83%)** |
| Curation exclusions correctly excluded | 9/9 | **9/9** |
| Strict affirm-precision vs Stage 1 labels | ~57% | ~59% |

## What v1→v2 changed, and why that was legitimate

One rule was added: `site_fo_selfdesc` (+20 when the firm's own site says "family office" ≥2
times). Calibration exposed it as a missing *evidence class*, not a tuning knob: Wellspring's
site states the phrase 12 times and PointOne's 20, and v1 scored both zero because it only
matched suffixed forms ("family office services/practice"). v2 was then **frozen**; further rule
changes require an ADR. This is declared as calibration on a labeled set — the mass records are
the held-out test, and the first reviewed tranches will measure whether calibration transfers.

## The four remaining misses (all evidence-poor, none rule-shaped)

Pine Ridge (site fetch yielded 226 chars), Timonier and Landmark (minimal sites, no ADV
free-text), one near-threshold. These route to needs_evidence/enrichment — the correct behavior:
the fix is richer evidence, not looser rules.

## The measured failure mode that sets release policy

Marketing-named wealth managers still affirm (7 of 11 in the calibration set at v2) — a firm
named "X Family Office" with FO-heavy marketing copy is indistinguishable from a real MFO at this
evidence depth. This is the same trap Stage 1's discovery fell into, now with a number attached.
Consequence (ADR-0029): **gate-affirm is triage, not release** — every affirm goes to human
review with its evidence list pre-assembled. The gate's value is collapsing ~661 candidates to
~150 reviewable items, not replacing the reviewer.
