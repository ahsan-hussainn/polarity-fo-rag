# ADR-0030: fit_rank — mandate-fit ranked retrieval with evidence-based confidence

- **Date:** 2026-07-28
- **Status:** Accepted

## Context

Stage 2 requires one retrieval capability a paying user does not have today. Stage 1 retrieval
answers "which records match this query" (lookup / exact filters / hybrid top-k); the paying
question a fund manager actually asks is "rank the WHOLE dataset for MY mandate and tell me how
much to trust each fit" — Goal 2 is literally this question. Observed constraint: per-record
confidence claims must be defensible, and most records carry thin mandate evidence by design.

## Decision

`pipeline/rag/fit.py`: deterministic weighted ranking over every qualifying record. Components,
pre-registered (semantic affinity .35, stated-sector evidence .25, record confidence .15,
reachability .15, signal recency .10), all shipped in the output per record with evidence strings
and caveats. The per-record `fit_confidence` tier is a function of EVIDENCE PRESENCE, not score
magnitude: 'strong' requires a stated-sector match plus ≥90 record confidence; prose mentions cap
at 'moderate'; no mandate-specific evidence → 'weak' (similarity only, caveated); no stated
sectors or thesis at all → 'insufficient_evidence'. Generic tokens ("services", "capital", …)
never count as evidence. The only model call is the mandate embedding. Exposed as an agent tool
and (with the agent UI) to users.

## Options considered

- **Deterministic component scoring (chosen).**
- **LLM-judged fit per record:** rejected — unmeasurable confidence claims, per-goal cost scaling
  with dataset size, and a release-relevant judgment inside a model (the ADR-0023 objection).
- **Plain hybrid top-k as the "extension":** rejected — not new, and top-k rank position is not a
  defensible confidence statement.

## Why this over the others

The first Goal-2 session proved the design necessary in the worst way: the initial scorer let the
generic token "services" match every wealth-management blurb and upgraded generic firms to
"strong fit" for a healthcare mandate — manufactured evidence, the exact laundering the brief
warns about. The fix was structural (generic-token stoplist; 'strong' gated on stated sectors),
and it is why tier assignment lives in deterministic code where a defect is findable and fixable,
not inside a prompt.

## Assumptions and risks

Keyword sector-matching is approximate and says so on every surface. Semantic affinity from one
embedding can rank plausible-but-unevidenced records highly — mitigated by the tier system, which
refuses to dress similarity as evidence. Weights are pre-registered, not learned; at 500 records
the ranking cost stays one embedding + one SQL scan.

## What would change this

If reviewed goal outputs show the tier rules misgrading records in either direction (strong tiers
on hollow evidence, or systematic under-confidence on genuinely evidenced fits), the rules change
via a superseding ADR with the measured cases attached. If sector vocabulary proves too sparse at
500 records, a canonical sector taxonomy (mapped at extraction time, not query time) is the next
step, keeping the gate deterministic.
