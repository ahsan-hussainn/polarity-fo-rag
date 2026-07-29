# ADR-0035: 13F as the second source class — reaching the family offices ADV cannot see

- **Date:** 2026-07-29
- **Status:** Accepted (extends ADR-0004's sourcing strategy)

## Context

Both discovery channels shipped so far — the SEC adviser feed and the state adviser feed — are
**one registry wearing two hats**. The Stage 2 brief is explicit that this is not enough:

> No minimum source count is prescribed, but scaling one convenient registry does not demonstrate
> market discovery if its blind spots pass into your records unchanged.

Bridge Mandate correction #4 asks for the same thing, and `docs/BRIDGE_MANDATE_DISCLOSURE.md`
deferred it to this window. It is therefore owed twice.

The blind spot is not incidental, it is **definitional**: a single-family office managing one
family's own money meets the conditions for exemption from adviser registration. The purest family
offices are precisely the ones Form ADV can never see. Our own data says so — **zero single-family
offices across 341 ADV-sourced candidates**, and Stage 1 recorded the same finding.

Section 13(f) has no such exemption: any institutional manager holding over $100M in 13(f)
securities files a 13F-HR regardless of who it serves.

## Decision

Add a 13F discovery channel (`pipeline/bronze/thirteenf.py`, `discover-13f`) reading EDGAR's
quarterly form index, keyed `cik:` rather than `crd:` — these firms have no adviser registration,
and identity must not be forced into a namespace they do not belong to. Candidates are tiered on
the **name signal only**, because a 13F filing carries nothing else to judge on.

Measured on 2026 QTR2: 8,801 distinct 13F filers → 59 name matches → **20 net-new after dedupe
against everything already held**, including **Duquesne Family Office** (Stanley Druckenmiller's),
which appears in no ADV feed we hold. That is the blind spot, demonstrated rather than asserted.

**What this source can and cannot establish**, per ADR-0004's requirement that each source be used
for what it actually supports:

- **CAN:** that a legal entity exists, its exact registered name, its CIK and EIN, its business
  address and phone, and that it manages institutional-scale securities. Enough to *surface* a
  candidate and to *corroborate* a domain.
- **CANNOT:** what the firm is. No client mix, no self-description, no AUM breakdown, **no
  website**. Every 13F candidate enters stranded and must earn its domain through the ADR-0032
  resolver before the gate can read anything the firm says about itself.

**Release consequence, and it is the conservative one:** a 13F candidate has no ADV client mix, so
ADR-0034's client-mix release route is unavailable to it *by construction*. It can only auto-release
through the concordant-published-evidence route. We know less about these firms, so more of them
stay in human review. That is the correct direction for the uncertainty to push.

## What measurement changed during the build

The first implementation seeded name and CIK only. Measured immediately: the domain resolver proved
**0 of 6** candidates, because ADR-0032's proof standard requires an independent corroborator for
any partial-stem domain, and a name supplies none. The options were to weaken the proof standard or
to find a corroborator. **The proof standard is the thing that must not move** — it exists because
two domains (blossom.com, reddoor.net) once passed a looser bar. So the channel now fetches the
filing's submission header, which carries the filer's street address and phone: the same
corroborator class the ADV path already uses. Proof rate went to **1 of 8**.

That number is low and is not being dressed up. It reflects something true about this population:
**the property that exempts these firms from registration — managing one family's private money —
is the same property that keeps them off the public web.** A source that reaches otherwise-invisible
entities will also find many of them unenrichable, and the honest reporting of that is part of what
this channel is for.

## Options considered

- **13F (chosen)** — attacks the documented blind spot directly, and the exemption logic guarantees
  it reaches a different population rather than a re-cut of the same one.
- **990-PF via ProPublica** — investigated and **rejected for this window on measurement**. A search
  for "family office" returns 33 organisations, nearly all charities and associations with the
  phrase in their name (Vincentian Family Office, Family Office University Network), not family
  offices. Reaching real family capital through 990-PF means starting from large private
  foundations and resolving to the family's office — a two-hop identity problem with no reliable
  join, and inventing a "foundation" category to absorb them would be exactly the category
  inflation ADR-0028 forbids. Recorded here so the rejection is on the record with its reason,
  not silently dropped.
- **More ADV tiers (the `client_mix` tier)** — rejected: 1,374 candidates exist there and the gate
  refuses to affirm on structural shape alone at a measured 10–20% precision. More volume from the
  same registry is exactly what the brief says does not count as market discovery.

## Assumptions and risks

Assumes name-signal tiering is adequate for 13F, where no other evidence exists at surface time —
it will miss family offices with a family surname and no "family office" in the registered name
(Cascade Investment, Willoughby Capital), which is a real and stated recall limit. Assumes EDGAR
tolerates a paced, identified client; requests are sequential with a delay and a declared
User-Agent, because a rate-limit block here would be a self-inflicted failure rather than the
external one the window condition asks for. One quarter is indexed at a time; a filer that stopped
filing before that quarter is not seen.

## What would change this

If the resolver's proof rate on this channel stays near 1-in-8 after the queue drains, the honest
conclusion is that 13F is a **lead** source rather than an enrichment source, and the architecture
notes should say so plainly rather than counting it as a second full channel. If a later quarter's
index shows materially different yield, the channel is re-measured rather than assumed stable.
