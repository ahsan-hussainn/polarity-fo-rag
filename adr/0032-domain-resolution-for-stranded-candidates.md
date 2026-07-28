# ADR-0032: Domain resolution — proving a firm's website when the registry didn't carry one

- **Date:** 2026-07-28 (Stage 2 operating window, day 2)
- **Status:** Accepted

## Context

Observed, measured on the live queue: of 341 queued candidates, **108 carry a social-media URL in
the ADV website field** (LinkedIn company pages, x.com, facebook.com) and **66 carry no URL at
all**. Only 167 (49%) carry a real firm domain.

This is the binding constraint on the entire climb, and it is measurable in the gate's own output.
Across the first 70 gate decisions the site rules fired 19 times (`site_fo_selfdesc` 13,
`site_fo_practice` 6) while `adv_freetext_fo` fired 40. In run 15, **15 of 40 candidates scored
exactly 15** — their own ADV filing states they do family-office work — and were excluded solely
because no page could be read. Those records sit +25 (a named site practice) away from an
`embedded_fo_practice` affirm.

The measured affirm rate splits accordingly: **56% where site text was obtained, 5% where it was
not.**

The brief names this failure directly:

> A source may be good enough to surface a candidate record without being strong enough to
> establish its identity, classification, decision-makers, mandate, contacts, or current relevance.
> … scaling one convenient registry does not demonstrate market discovery if its blind spots pass
> into your records unchanged.

The ADV website field is self-reported and unvalidated by the SEC. Treating it as the firm's domain
passes exactly that blind spot into the records.

## Decision

Derive candidate domains from the firm's registered name, and accept one **only on proof that the
page belongs to that firm**. Resolution runs as a cycle phase before discovery, so a recovered
candidate is re-queued and re-gated with the evidence it was missing.

The proof standard is deliberately asymmetric, because the two error types are not symmetric:

1. **Full-name domains** (the stem is the firm's entire registered name, e.g.
   `bravefamilyadvisors.com`) are accepted when the page carries at least one **distinctive** name
   token — distinctive meaning not in a generic-finance stoplist (`capital`, `wealth`, `advisors`,
   `family`, `office`, `partners`, …), which carries no identifying information.
2. **Partial-stem domains** (`troobcapital.com`, `reddoor.net`) are accepted **only with
   independent corroboration**: the firm's ADV phone number (matched on its last 10 digits, so
   formatting cannot defeat it) or its ADV city appearing on the page.
3. Everything else stays unresolved. A resolution never overwrites a real website already held.

The prior gate decision is left in place; `gold.entity_gate` is append-only, so the record shows
what was decided on thin evidence and what changed when evidence arrived.

## Options considered

- **Trust the ADV website field** (status quo): rejected by measurement — it strands 51% of the
  queue and the failures are silent, appearing as "fetch errors" rather than as bad source data.
- **Loose verification (any two name tokens on the page):** tested, and rejected on its results. A
  probe at that bar resolved 9 of 12 candidates but produced wrong-entity matches twice — BLOSSOM
  WEALTH MANAGEMENT → `blossom.com` on `{blossom, management}`, RED DOOR WEALTH MANAGEMENT →
  `reddoor.net` on `{red, door}`. This dataset already carries one defect of exactly that shape
  (`arrowrootadvisors.com`, an M&A bank whose pages were extracted as a family office's), which is
  why the loose bar was disqualified rather than tuned.
- **Search-engine lookup:** rejected for this window. It would raise recall, but it introduces a
  scraped dependency with its own blocking behaviour and no per-result evidence trail, and the
  strict-derivation path is deterministic, free, and auditable.
- **LLM-guessed domains:** rejected outright. The failure mode is a confident, plausible, wrong
  domain, and no model call is allowed in a release-affecting decision path (same objection as
  ADR-0023 and ADR-0029).

## Why this over the others

A missing domain costs one candidate. A **wrong** domain costs a false record — with someone else's
thesis, someone else's team, and someone else's contact details — which then propagates into gold,
the retrieval index, and the agent's answers, carrying the same confidence as a true one. Precision
is therefore worth far more than recall here, and the measured rates reflect the trade: **28% of
stranded candidates resolve under the strict bar, versus 75% under the loose one**, and the 28%
inspected sample contained no wrong matches while the 75% contained at least two.

Firms whose names consist entirely of generic tokens (`FAMILY WEALTH ADVISORS`,
`FAMILY CAPITAL MANAGEMENT`) can never resolve under this rule. That is intended: for such a name
no derived domain is safe, and an honest gap beats a guess.

## Assumptions and risks

Assumes a firm's real domain is usually derivable from its registered name — true for owner-named
advisers, weaker for rebranded ones. Assumes an ADV phone or city on the page is strong
corroboration; a shared office building or a syndicated directory page could in principle defeat
it, which is why corroboration supplements token evidence rather than replacing it.

Risk: recall is low enough that the recovered volume (~49 candidates) does not change the 500
outcome by itself. Accepted — it is a real gain on records we already hold, and the same mechanism
serves any future channel, since 13F and 990-PF leads face the identical identity problem.

## What would change this

If sampled review of resolved domains shows any wrong-entity match, the full-name-alone path is
withdrawn and every resolution requires phone or city corroboration. If recall proves the binding
constraint after precision is established, a search-derived channel becomes worth its dependency
cost — but as a *separate*, labelled resolution method, never blended with derived-and-proven.
