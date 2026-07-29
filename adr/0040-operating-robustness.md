# ADR-0040: Four robustness fixes the operating plan had already promised

- **Date:** 2026-07-29
- **Status:** Accepted

## Context

`docs/OPERATING_PLAN.md` claims: *"bounded worker pool (~8) with per-host politeness + exponential
backoff"* and *"DB work-claiming so an interrupted run resumes instead of duplicating."* The
work-claiming half was real (`FOR UPDATE SKIP LOCKED`). The rest was not in the code. The brief is
unambiguous that this is worth nothing: *"Every claim below earns credit only where it corresponds
to something in your code, your logs, or your data... A claim that floats above the artifacts counts
for nothing here."*

Separately, the brief scores *"how it handles concurrency, rate limits, partial failures across
hundreds of records"* directly, and three real defects sat under that heading.

## Decision

**1. Per-host politeness and real backoff.** The worker pool is per-*firm*, so two firms on the same
host (or the same CDN) were fetched with no spacing at all, and a `429` was treated as a terminal
error — turning a server saying "slow down" into permanently missing evidence. `_fetch_raw` now
spaces requests per host (a lock map keyed by hostname, so unrelated hosts never block each other
and the pool stays as concurrent as before) and retries `429/5xx` with exponential backoff,
honouring `Retry-After` when the server sends one.

**2. Failed candidates are retried, not dead-lettered.** `status='failed'` was permanent: one
transient OpenAI 500 or network blip removed a candidate from the climb forever, silently, with no
sweeper and no alert. Candidates are now retried up to 3 attempts, with the attempt count on the
row, and retries are ordered *last* so a poison record cannot starve fresh work.

**3. The resolve queue rotates.** `_stranded` ordered by `entity_key` and took the first N, so with
140 stranded candidates and a limit of 40, positions 41–140 were **unreachable by construction**
while the same unresolvable head was re-attempted every cycle. The measured symptom: domains proven
per run decayed 13 → 5 → 4 → 1 → 1. Ordering is now by attempt count, so the queue cycles through.
Deliberately a counter rather than a give-up flag — a firm with no website today may publish one
next week, and the resolver is cheap. This changes the order work is attempted in, not whether it is
ever attempted again.

**4. The release control runs before publication, not after.** `reconcile` ran after the CSVs and
the retrieval index were written, so it could *report* an inconsistent surface but never *prevent*
one. On scheduled run 20 it correctly failed the run — 37 minutes after shipping the inconsistent
export to the live surface, which is the wrong half of the job. `reconcile.run(db_only=True)` now
runs before export and raises before anything is written; the full check still runs afterwards,
because surface-vs-CSV agreement cannot be tested until the CSVs exist.

Splitting it exposed a subtlety worth recording: two suppression checks read the product CSV, so in
a pre-publication position they would have validated the **previous** export — a check that looks
like a check but tests the wrong artifact. Both now have database-side equivalents that run in the
gate, with the CSV versions kept afterwards to confirm what actually shipped.

## What this cost, and one landmine it created

The pre-publication gate makes any release invariant a hard stop for the whole cycle. That is the
point, and it has teeth: a 13F-sourced record (ADR-0035) has no ADV capture by construction, so it
would have shipped with a null `data_asof`, which the freshness invariant would have refused — a
green cycle turned red over a record the system was never going to have an ADV row for. `_adv_facts`
now reads the 13F submission header too (it carries a filing date, address and phone), with the ADV
feeds still preferred wherever a firm appears in both. Found by reasoning about the new gate against
the new channel before either had met the other in production, which is the only cheap time to find
it.

## Options considered

- **Fix the code to match the claims (chosen).**
- **Delete the claims from the operating plan:** the honest fallback, and correct if the fixes had
  not fit the window. They did, and the brief scores the behaviour rather than the prose, so fixing
  is strictly better than retracting.
- **A global fetch rate limit instead of per-host:** rejected — it would throttle 59 unrelated hosts
  to protect one, converting a politeness problem into a throughput problem.

## Assumptions and risks

Assumes a 1s per-host interval is polite enough for the sites we fetch; it is a floor, not a
guarantee, and a host that objects will still surface as `429` — which now backs off instead of
failing. Assumes 3 attempts distinguishes transient from persistent; a candidate failing 3 times is
not retried again and is visible by its attempt count rather than silently gone. The pre-publication
gate makes the cycle fail *more* often by design, and that is the intended trade: a failed run with
an intact surface beats a green run with a broken one.

## What would change this

If the per-host interval measurably slows cycles as the set grows past a few hundred records, it
becomes adaptive (spacing only hosts that have recently returned 429/5xx) rather than uniform. If
retried candidates prove to succeed almost never, the attempt cap drops to 2 and the budget goes to
fresh discovery instead.
