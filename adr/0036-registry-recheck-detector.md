# ADR-0036: Re-checking the regulator, and the connection bottleneck that exposed

- **Date:** 2026-07-29
- **Status:** Accepted (fixes the ADV detector promised in ADR-0027; extends ADR-0017's pooling)

## Context

`docs/OPERATING_PLAN.md` claims three independent staleness detectors. Measured against the ledger,
only one of them could ever fire.

The ADV filing-date detector read `gold.records.data_asof` — **our own held value** — wrote it to
`ops.observations`, and compared the next run's observation against the previous one. Nothing in the
cycle re-ingests Form ADV, so the held value cannot move, and the comparison was the held value
against itself. The result across 24 runs: **772 observations, zero trust events.**

This is worse than having no detector. A detector that cannot fire still reports coverage, still
appears in the operating plan as one of three, and the brief is explicit that a claim without a
corresponding artifact scores nothing. It also quietly weakened the honest claim we *could* make,
because the one real detector (website evidence) was doing all the work while three were advertised.

## Decision

**Compare against the regulator, not against ourselves.** Each cycle fetches every held CRD's
current record from IAPD (`pipeline/bronze/iapd.py`) — the source behind adviserinfo.sec.gov — and
compares three live facts against what we hold. All three are evidence-based, none is a clock:

| signal | trust event | why it matters |
|---|---|---|
| `advFilingDate` newer than held `data_asof` | `adv_filing` | ADV-derived cells (AUM, address, phone, client mix) may be superseded |
| `iaScope` no longer `ACTIVE` | `adv_registration_lapsed` | the firm is no longer a registered adviser: the *basis* of every ADV-derived cell is gone, not merely stale |
| registered name differs from held name | `adv_name_changed` | an identity event; the held record may describe a firm that no longer presents under that name |
| CRD no longer resolves at IAPD | `adv_registration_gone` | the regulatory basis can no longer be re-checked at all |

Registration scope is the signal a filing-date check would have missed entirely, and it is the
strongest of the four: a lapsed registration invalidates the evidence rather than ageing it.

**First run, measured: 59 of 59 CRDs checked, 0 errors, and 3 firms carry a filing newer than the
one their record was built from.** The detector fires on real evidence, on its first execution.

## The bottleneck this exposed, and the fix

Adding the detector roughly doubled ledger writes per observe sweep. The sweep then failed
outright: `server closed the connection unexpectedly` from the Supabase pooler, mid-run.

The cause was already known as a scalability risk and is now a live failure: **every ops ledger
write opened its own connection.** `runlog.event/observe/trust_event/start_run/finish_run` each
called `psycopg.connect()`, at roughly one second of TLS handshake apiece. One sweep over 59 firms
opens several hundred; at 500 records it would open several thousand, which is over an hour of
handshake per cycle before any work happens.

The ops ledger now uses the same pooled, autocommitting, idle-revalidating connection source the
serving path has used since ADR-0017 (`db.get_pool()`), making the pool the process-wide connection
source rather than a serving-only optimisation. Sweep time with the detector added: 143s for 59
firms including 59 registry fetches.

This is the honest answer to architecture-note §5's "what breaks first at 5,000 records" — it was
connection establishment in the ledger, it broke at 59 records once write volume rose, and it is
fixed rather than predicted.

## Also fixed here: dry runs contaminating the evidence chain

`_observe_phase` wrote observations and trust events regardless of the `write` flag, and
`latest_observation` takes the most recent earlier run of any trigger. A laptop dry-run could
therefore become a scheduled cycle's comparison baseline, and cross-run evidence would be measuring
a local test. Observation and trust-event writes are now suppressed on dry runs; reads still happen,
so a dry run still reports what it *would* have flagged.

## Options considered

- **Re-check the regulator per cycle (chosen).** One small JSON per held firm, bounded at 4 workers
  because this is one government API rather than N independent hosts.
- **Re-download the ADV bulk feed each cycle:** rejected — hundreds of megabytes per cycle to detect
  a handful of changes, and it would still miss registration lapses between feed publications.
- **Delete the detector and claim two:** genuinely considered, and it is the right move if the
  re-check had proved infeasible. It did not; the claim is now true instead of retired.

## Assumptions and risks

Assumes IAPD tolerates a paced, identified client at this volume; requests are bounded and carry a
declared User-Agent, and errors are ledgered per firm rather than failing the sweep. Assumes
`iaScope` is maintained promptly by the regulator — a lapse recorded late is detected late, which is
a floor on how fresh this signal can be and is stated rather than assumed away. The detector covers
CRD-keyed records only; 13F-sourced (`cik:`) candidates have no adviser registration by
construction (ADR-0035), so they are outside its reach and must rely on website evidence.

## What would change this

If IAPD rate-limits or blocks the sweep, the detector degrades to a rotating sample per cycle rather
than a full pass, and the ledger records the sampling rate — never a silent partial sweep reported
as a full one. If registration-scope changes prove to lag reality badly, the signal is demoted to
corroboration rather than a standalone trust event.
