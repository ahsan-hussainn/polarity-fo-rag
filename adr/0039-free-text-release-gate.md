# ADR-0039: The release gate covers the free text, not just the picks

- **Date:** 2026-07-29
- **Status:** Accepted (extends ADR-0023's verification floor to the agent's prose)

## Context

The agent's deterministic release gate (`_check_output`) iterated `ans.picks` and nothing else. The
`verdict` — the first thing a user reads — plus `coverage_note`, `abstained`, `next_steps` and
`limitations` were **entirely ungated**.

That matters because `quarantine_summary` deliberately hands the model the names and reasons for
every firm the system holds but does not release. The only thing standing between that and a
quarantined firm being recommended in prose was a line in the system prompt, and the brief is
explicit:

> Prompt instructions alone do not count as enforced control. Before a composed answer reaches the
> user, the system must enforce, in its control flow, what it may claim, what it must refuse, and
> what data it may rely on.

This was not hypothetical. A session asked *"which family offices should I no longer trust?"*
answered in its verdict by naming 27 never-released candidates as family offices to distrust — in
the field nothing checked, while the `picks` list stayed clean and the gate passed.

## Decision

Two enforced checks over the concatenated free text:

1. **A context-only firm may be reported on, never recommended.** "We hold 9 quarantined firms" is
   honest coverage and must stay possible — the brief asks for uncertain records to remain visible.
   What must not happen is a push to *act*. The two are separated by a deliberately narrow
   recommendation-verb match in a window around the firm's name, so naming a firm is free and
   recommending it fails the gate.
2. **Every email in free text must belong to a retrieved record**, the same rule the picks already
   obeyed.

Firms surfaced by non-pickable tools are tracked by name for exactly this purpose and never enter
the grounding set — the set an answer may draw *evidence* from stays distinct from the set the model
has merely *seen*.

## A bug in the check itself, found while testing it

The email pattern's trailing `[\w.]+` swallows sentence-ending punctuation, so a perfectly valid
*"reach them at a@firm.com."* would have failed its own grounding check and forced a pointless
repair. Stripped. Worth recording because it is the characteristic failure mode of a safety check:
the cost of a false positive is invisible in testing (the answer just gets repaired) and real in
production (a correct answer withheld).

## Options considered

- **Verb-window matching (chosen)** — narrow, and errs toward allowing honest coverage.
- **Forbid naming a non-released firm in free text at all:** rejected — it would make honest
  coverage reporting impossible, and the brief explicitly wants uncertain records visible rather
  than hidden.
- **An LLM judge over the free text:** rejected for the reason ADR-0023 exists — a release control
  that can be talked out of a failure is not a control.
- **Structured-only output, no free text:** rejected — the verdict is what makes the answer readable
  to a non-technical buyer, which is itself a scored requirement.

## Assumptions and risks

Assumes the verb list catches the ways a recommendation is actually phrased; it will miss creative
phrasings, and it is a floor rather than a proof. Assumes firm names are distinctive enough to match
on — names shorter than 6 characters are skipped to avoid false positives on common words, which
means a very short firm name is not covered by this check and is covered only by the pick-level
gate. Both limits are stated rather than papered over.

## What would change this

If a real answer is ever blocked for reporting honestly, the window narrows or the verb list loses
the offending term — measured against actual sessions, not imagined ones. If the miss rate proves
high, the check moves from verb matching to requiring that any context-only firm named in free text
also appear in `abstained` with its reason, which is a stronger and more structural rule.
