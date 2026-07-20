# ADR-0023: Independent answer-verification floor + surface consistency

- **Date:** 2026-07-20
- **Status:** Accepted

## Context

Bridge Mandate correction #5. **Observed:** Stage 1 grounding was prompt-only — the model was *asked*
to stay inside the retrieved evidence and *trusted* to have done so; no independent control checked
the composed answer before release, and `docs/rag-note.md` already flagged this as the top gap. The
mandate: "the final release decision cannot depend only on the same model saying that its answer is
safe," and "every customer surface must agree." Two concrete failures were possible: an answer could
state an email or firm not in the retrieved set, and a reclassified non-FO (ADR-0020) could surface
in a "family office" answer unlabeled.

## Decision

A **deterministic, model-independent** check (`pipeline/rag/checkanswer.py`) runs on every composed
answer before release and gates it: (1) every email in the answer must belong to a retrieved record;
(2) no quarantined/vendor-rejected address (`gold.contact_audit`) may appear on any surface; (3) a
stated count must match the dataset total; (4) a reclassified non-FO named in the answer must be
labelled as not a family office. On failure the answer layer repairs once (regenerate with the exact
failures + the allowed-email list), and if it still fails, **refuses** rather than shipping it — the
verdict is logged and returned in the API response (`verification`). Surface consistency: retrieval
carries `entity_category`, affirmed FOs always lead (non-FOs are kept but never lead an answer), the
coverage panel counts family offices and "related firms" separately (fixing the Stage-1 count bug),
and cards badge non-FOs. `pipeline/rag/eval.py` measures the deployed `answer()` path over an
adversarial suite and reports the numbers, weak ones included.

## Options considered

- **Option A (chosen):** deterministic post-generation check + repair-or-refuse + surface consistency.
- **Option B:** a second LLM as judge/verifier. Rejected as the primary control: still model-dependent
  (the mandate's objection), non-deterministic, and adds latency/cost; a deterministic check cannot be
  talked out of a failure. (An LLM judge could *augment* later for semantic faithfulness.)
- **Option C:** keep prompt-only grounding, tighten the prompt. Rejected: explicitly named
  below-the-floor; a prompt is not a control.
- **Option D:** block-only (no repair). Rejected: a single stricter re-generation recovers most
  failures without giving up, and refusal remains the backstop.

## Why this over the others

The whole point of the correction is that a control must *change what ships*, deterministically and
visibly. A programmatic check over the retrieved evidence is the only option that is independent of
the generator, reproducible in the eval, and cheap enough to run on every request.

## Assumptions and risks

The check is deterministic but not exhaustive: it verifies emails, suppression, counts, and category
honesty — **not** free-form semantic faithfulness (a sentence can be misleading while every token is
grounded). Firm-name grounding is asserted indirectly (via emails + the category check), not by
parsing every firm mention. Streaming now composes-and-checks before the first text token, trading
ADR-0017's first-token latency for release-gated text (coverage cards still render at retrieval time).
**Known gap, reported not hidden:** an out-of-scope query that shares a token with a firm (e.g.
"weather in Zurich" → Marcuard) is answered about that firm; the answer is grounded but off-intent —
the eval flags this case (`rag-eval`, expectation 7/8).

## What would change this

Adding an LLM faithfulness judge as a second gate (if the deterministic check proves insufficient on
real traffic); a measured groundedness number on live queries (not just the fixed suite) that falls
below a set threshold; a scope/relevance gate to close the out-of-scope case if it recurs in use.
