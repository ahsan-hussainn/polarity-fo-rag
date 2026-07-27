# ADR-0031: Goal agent — model plans, code releases

- **Date:** 2026-07-28
- **Status:** Accepted

## Context

Stage 2 requires an agent that uses retrieval as a tool to accomplish natural-language goals,
with enforced (not prompted) control over what it may claim. Observed while building: gpt-4o-mini
repeated an identical fit_rank call five consecutive steps and never submitted (run 10); the
first honest-looking session also laundered generic-token "evidence" into strong fits (run 9,
fixed in ADR-0030). Both failures shaped where the deterministic boundary sits.

## Decision

`pipeline/agent/`: a framework-free tool loop. **Agentic (model decides):** goal decomposition,
which tools to call with what arguments, when to stop, and the wording of the answer. **Fixed
(code decides):** the tool set (wrapping only released retrieval paths — no route to suppressed
data; quarantine_summary returns status + reason only and its firms are non-pickable); the
grounding set (every record a tool returned this session is the closed world); duplicate
tool-calls never re-execute (the loop-breaker run 10 forced); the final step may only submit; the
answer arrives only through `submit_answer` validated against a Pydantic schema; and a
deterministic release gate checks every pick is a grounded, pickable record, every stated email
belongs to that record verbatim, and claimed confidence never exceeds fit_rank's evidence-based
tier. Gate failure → one named-failure repair → refuse with what IS known (the ADR-0023 pattern).
Every session is an ops run: model calls and tool executions ledgered with tokens/USD/duration —
the raw run log is a database export, not a narrative. Served at `/agent` (buyer-readable states)
with tool schemas live at `/agent/tools`.

## Options considered

- **Framework-free loop over the OpenAI tools API (chosen).**
- **LangChain/LangGraph or similar:** rejected — the brief scores behavior, not framework choice;
  a framework buries exactly the control flow we are required to demonstrate we own.
- **Prompt-only honesty rules:** rejected explicitly by the brief ("prompt instructions alone do
  not count as enforced control") — the rules exist in the prompt too, but the gate is what makes
  them true.
- **A larger model to avoid loop pathologies:** rejected for now — the loop-breaker fixes the
  pathology deterministically at ~1/20th the cost; the model is an env-swappable seam
  (AGENT_MODEL) if goal quality demands escalation.

## Why this over the others

Runs 10–12 are the argument in miniature: prompt guidance failed to stop repeated calls (model
limitation), a code loop-breaker stopped them structurally; scorer honesty failed in a component
we could measure and fix in code within minutes. The Goal-2 verbatim run now produces weak picks
with stated caveats, six explicit abstentions, and a coverage note saying the dataset cannot
support confident recommendations — verified before release, at $0.0034 and 4 steps per session.

## Assumptions and risks

gpt-4o-mini's reasoning ceiling shows in prose (it still narrates AUM-band framing it was told to
drop); acceptable while the structure carries the honesty, revisitable via AGENT_MODEL. The gate
checks structure and grounding, not prose truthfulness inside fit_summary wording — narrative
drift within a grounded pick is the residual risk, bounded by evidence lists shipping alongside.
Sessions are synchronous (~20–60s); fine at demo load, queueable later if needed.

## What would change this

If reviewer-run goals (the 7-day post-submission window) surface a claim the gate should have
caught, the gate gains that check and the miss is documented, not smoothed. If goal complexity
outgrows 10 steps or 4o-mini's planning, escalate AGENT_MODEL and record the cost delta in the
ledger — the decision will be visible as a config change in ops.runs.
