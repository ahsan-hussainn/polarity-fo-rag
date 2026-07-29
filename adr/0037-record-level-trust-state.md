# ADR-0037: Evidence-based freshness on the record a buyer receives

- **Date:** 2026-07-29
- **Status:** Accepted

## Context

The system gathers real decay evidence every cycle — a home page that went dark, a registration
that lapsed, a newer ADV filing, a decision-maker who vanished from the roster — and wrote all of it
to `ops.trust_events`, where **a customer never sees it**.

The only freshness signal on the delivered record was `is_stale`, computed as "the ADV filing is
more than 15 months old." That is calendar arithmetic, and the brief rules it out explicitly:

> A clock-based expiry alone does not satisfy this condition.

Meanwhile deliverable 5 asks for "the 500 records **including whatever the system uses to track how
fresh or trustworthy each record is**." Answering that with a log the reader must correlate by hand
against a CSV is not answering it.

## Decision

Join the operating layer's evidence onto the record, in three columns that ship in the CSV and on
every serving surface:

- **`last_checked_at`** — when a cycle last *looked*. Distinct from `data_asof`, which is the age of
  the source document; this is the age of our last look at it. A buyer needs both and they are not
  the same fact.
- **`trust_state`** — `current` or `flagged`, derived from the **latest trust event per check type**:
  a later `noted`/`refreshed` supersedes an earlier `flagged`, so a firm that was flagged and then
  re-verified reads as current instead of carrying a scar forever.
- **`trust_reason`** — the evidence, in the detector's own words. A flag without a reason is a
  warning users learn to ignore, so `reconcile` fails the run if any flagged record lacks one.

`is_stale` survives but is renamed on the artifact to **"Source Doc Older Than 15mo"**, which is
what it actually measures. It was the only thing wearing the word "stale" while being the one
signal the brief says does not count.

**Only real operating cycles drive a customer-facing flag.** Trust events are filtered to runs that
actually wrote (`ops.runs.config->>'write' = 'true'`). This was not theoretical: a dry run of the
materiality classifier had put *"website_change: home-page text changed (dry-run: materiality not
classified)"* on a buyer-visible record. A dry run does not classify materiality, so its events are
incomplete by construction. ADR-0036 stopped dry runs writing at all; this filter covers the rows
written before that, **without deleting anything** — the submitted logs stay uncurated, they just do
not drive the product.

Measured after the filter: 2 of 32 qualifying records flagged, both from scheduled run 14, both
`website_dark` with the HTTP status change and the run and timestamp they were observed at.

## Options considered

- **Join the evidence onto the record (chosen).**
- **Leave trust in the ops tables and point the reader there:** rejected — the brief asks for it
  with the records, and a buyer reading a CSV will not join it by hand.
- **Collapse it into one composite freshness score:** rejected — a score hides which evidence moved,
  and "why should I distrust this row" is exactly the question the column exists to answer. The same
  reasoning that keeps entity category, person status and email grade as separate readable axes.
- **Let a flag be permanent once raised:** rejected — a record that was re-verified is not still
  suspect, and permanent flags decay into noise.

## Assumptions and risks

Assumes the supersede rule (latest event per check type) matches how a reader interprets a flag; a
firm flagged on one axis and refreshed on another correctly stays flagged. Risk: as the set grows,
the share of flagged records is itself a product-quality signal, and a rising number could read as
decay when it actually reflects better detection — `reconcile` therefore reports the split every
run, so the trend is visible rather than inferred. `trust_reason` carries detector prose written for
an operator; it is legible but not marketing copy, and that is deliberate.

## What would change this

If the flagged share climbs past roughly a fifth of the set, a single flag stops being informative
and the state needs severity tiers (advisory vs blocking) rather than a boolean. If a detector
proves noisy enough to flag records that re-verify immediately, that detector's events stop driving
`trust_state` and remain observation-only until its precision is measured — the same
measure-before-trusting rule the inclusion gate operates under.
