# ADR-0038: The agent's raw session trace, and the one tool that sees across cycles

- **Date:** 2026-07-29
- **Status:** Accepted (extends ADR-0031)

## Context

Two gaps, both found by reading the code against the brief rather than against its own docstrings.

**The trace was not kept.** `pipeline/agent/loop.py`'s module docstring said *"the full message
trace preserved — the raw, unedited log the brief demands is a database export, not a narrative."*
It was not preserved: `messages` was a local variable that died when `run_goal` returned.
`ops.run_events` recorded that a tool was *called*, with its arguments and a record *count* — but
never what came back, never the model's intermediate reasoning, and never the repair turn. The brief
asks for *"the action sequence, every retrieval and tool call, intermediate decisions, any retries,
rejected paths, uncertainty checks, escalations, or refusals"* and says plainly that *"a written
summary of a run is not a run log."* A trace without tool results cannot show a rejected path,
because the rejection is a reaction to a result.

The repair call was also entirely unledgered — a real model call whose tokens, cost and latency were
missing, so `ops.runs.usd_est` **understated every repaired session**, and the one artefact the
brief explicitly asks to see (a retry) was invisible.

**Goal 3 was unanswerable.** Our own paid-tier goal is framed around what changed across cycles, and
**no tool read `ops.*`**. Every tool described the current state.

## Decision

**`ops.agent_messages`** stores every message of a session in order, verbatim — including tool
results and the repair turn under its own `phase` — written before the run closes and also on the
exception path, because a crashed session is the one whose trace is most worth having. The repair
call gets its own ledger event carrying the failures that triggered it.

**`record_history`** is the only tool that reads the operating ledger. With a firm name it returns
that firm's run-by-run history; with **no arguments** it lists released records whose evidence has
moved. Evidence and timestamps only, never contact data, so it cannot become a side channel around
release policy.

## What building it exposed

The no-argument mode was not in the original design and was added because the first version failed
in production. Asked *"which family offices should I no longer trust?"*, the agent answered from
`quarantine_summary` — naming 27 **never-released** candidates as *"family offices you should no
longer trust."* Two distinct errors: it conflated release state with trust state, and it had no way
to *discover* which records were flagged, because `record_history` could only confirm a firm you
already suspected.

So the fix was half prompt, half capability. The system prompt now separates the two states
explicitly; `record_history` gained the discovery mode that was genuinely missing. Re-run, the agent
returns the actually-flagged records with their evidence. **The prompt alone would not have fixed
it** — the information was not reachable by any call the model could make, which is the difference
between a model that reasons badly and a system that cannot answer.

## Options considered

- **A dedicated messages table (chosen):** queryable, exportable, and joins to the run ledger.
- **Write traces to files as artifacts:** rejected — the run history already lives in Postgres, and
  splitting the evidence across two stores makes the export a merge problem.
- **Store only assistant turns and tool names:** rejected — that is the summary the brief refuses.
- **Give the agent read access to `ops.*` generally:** rejected — a tool with a defined contract can
  guarantee no contact data leaks through it; a general query surface cannot.

## Assumptions and risks

Assumes traces stay a manageable size; a session is bounded at 10 steps with tool payloads capped at
12KB, so a session is tens of kilobytes. Risk: the trace contains whatever the tools returned, so
release policy has to hold at the tool boundary rather than at the trace boundary — which is why
`record_history` and `quarantine_summary` are metadata-only by construction rather than by filtering
afterwards.

## What would change this

If traces grow past what an export can reasonably carry, they get truncated with an explicit marker
rather than silently sampled. If `record_history` is ever needed for bulk analysis rather than a
handful of firms per session, it gets pagination instead of returning the whole flagged set.
