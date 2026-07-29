# Bringing the Stage 1 records under the Stage 2 standard (day 3, 2026-07-29)

The brief, on what counts toward the 500:

> The 500 includes your original Stage 1 records, **brought under the same Stage 2 standard before
> submission.**

`docs/findings/stage2-brief-reconciliation.md` flagged this as Drift 2 on day 2: the seed records
had been *scored* by the Stage 2 gate as calibration, but scoring for calibration is not the same as
bringing them under the standard, and — measured today — the scores were never even persisted.

## What was actually wrong

Every qualifying record was checked against `gold.entity_gate`. **24 of them had no gate decision at
all.** `gate.retro()` had only ever been run without `--write`, so the calibration numbers quoted in
ADR-0029 existed in a terminal, not in the data.

Worse, running it with `--write` would have made things *less* consistent: `retro()` passed bare
CRDs to `run_gate`, so it would have written `entity_key='120053'` while every other gate decision
uses the namespaced `crd:120053` (ADR-0029's identity scheme). That is two key formats for the same
entity, and it quietly breaks any join over the table. Fixed before writing anything.

## What is true now

All **32 qualifying records — the seed 24 included — carry a persisted gate-v3 decision.** 331
distinct CRD entities now have one. One dataset, one standard, and the disagreements are in the data
rather than in a report.

The gate does **not** change their release state. Human adjudication outranks the gate (ADR-0029,
unchanged), so a record a human affirmed stays affirmed. What the retro produces is a measured,
recorded second opinion — which is the point: a reviewer can see where the automated standard and
the human standard diverge, per record.

## The disagreements, stated plainly

Of the 67 human-labeled entities, gate-v3 says:

| human label | n | gate affirms | gate needs_evidence | gate excludes |
|---|---|---|---|---|
| affirmed family office | 25 | 21 | 1 | 3 |
| wealth manager | 14 | 10 | 2 | 2 |
| quarantined / other | 9 | 6 | 1 | 2 |

**Recall on human-affirmed family offices: 21/25 (84%).** The gate misses 4 real family offices —
under-inclusion, the safe direction, and they are in the product anyway because the human decision
governs.

**The gate affirms 10 of 14 firms a human called a wealth manager.** That is the precision problem
ADR-0034 measured independently (54.8% counted-precision) and is exactly why gate affirms do not
auto-release: they must also clear the client-mix band. The retro is the same finding from the other
direction, on the same labeled set.

## Open, and it needs Ahsan rather than code

ADR-0028 says the 7 `ria_with_fo_practice` records "may re-enter qualifying **only by clearing the
category-3 evidence bar through adjudication**." Gate-v3's view of them, for whoever does that
adjudication:

| CRD | firm | gate decision | category | score |
|---|---|---|---|---|
| 307521 | Alpha Capital Family Office, LLC | affirm | multi_family_office | 105 |
| 142856 | Pioneer Family Office, LLC | affirm | multi_family_office | 95 |
| 329496 | Innovative Family Office LLC | affirm | multi_family_office | 85 |
| 324899 | Sapient Capital LLC | affirm | embedded_fo_practice | 45 |
| 220519 | Summit Trail Advisors, LLC | needs_evidence | — | 30 |
| 286243 | Crestwood Advisors | exclude | — | 20 |
| 133370 | 1919 Investment Counsel, LLC | exclude | — | 5 |

They remain `unresolved` and are **not** auto-promoted, deliberately: the human adjudication that
put them there outranks the gate, and ADR-0028 requires adjudication for re-entry. Three of the four
gate affirms score at or above the concordance bar, so a re-adjudication is plausible upside of up
to +4 qualifying records — but it is a judgment call about whether each firm runs an *evidenced*
family-office practice, and evidence assembly is the machine's job while that call is not.

The bottom three are worth noting for the opposite reason: the gate and the human agree these are
not family offices, which is the standard working.
