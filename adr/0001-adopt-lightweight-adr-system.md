# ADR-0001: Adopt a lightweight, self-built ADR system

- **Date:** 2026-07-11
- **Status:** Accepted

## Context

Observed (fact): The assessment scores *visible reasoning* above output volume. The briefing docs
repeatedly require showing what was observed vs assumed, believed vs verified, and what would change a
conclusion. They also read the git history and run an Ownership Check interview that asks the candidate to
"walk through specific decisions and explain tradeoffs."

Assumed (unverified but reasonable): a structured, timestamped decision trail committed alongside the build
will read as genuine thinking and make the ownership interview straightforward.

The idea for an ADR system came from Amin Naggar's public `claude-customizations` repo, which ships an
`aminnaggar_adrs` skill (auto-syncs an ADR summary into CLAUDE.md) plus tickets, a uv anti-pattern hook,
Bats tests, and Just automation.

## Decision

Use ADRs as the reasoning trail. Build a minimal version ourselves: an `adr/` folder, a short template, a
`/adr` scaffold command, and a hand-maintained index in CLAUDE.md. Do not install Amin's skill or the rest
of his tooling.

## Options considered

- **Minimal self-built ADRs (chosen):** just enough structure to capture decisions fast.
- **Install `aminnaggar_adrs` skill + his repo tooling:** rejected. The hooks/tickets/bats/just stack is his
  personal workflow and serves none of this assessment; wiring it up burns clock for zero scoring value.
- **No ADRs, rely on commit messages + a final writeup:** rejected. Commit messages are too thin to carry
  tradeoff reasoning, and an end-of-project writeup is reconstruction, which is exactly what they penalize.

## Why this over the others

The value is the *idea* (decisions with tradeoffs, recorded when made), not the machinery. A self-built
minimal system gives us the scoring benefit with near-zero setup cost and nothing to maintain. Keeping it
lightweight also protects against the real risk: ADR ceremony competing with the dataset, which is the
pass/fail product.

## Assumptions and risks

- Risk: ADRs become polish/procrastination instead of building. Mitigation: one screen max, written inline
  with the work, never a separate "phase."
- Assumption: reviewers value a genuine trail over a polished narrative. Consistent with every briefing doc.

## What would change this

If maintaining ADRs starts costing more time than it saves, or begins reading as manufactured, we cut back
to decision-heavy commit messages plus a short decisions log.
