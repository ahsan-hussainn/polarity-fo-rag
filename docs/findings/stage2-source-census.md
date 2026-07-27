# Stage 2 source census — can affirmed family offices reach 500?

_2026-07-27, day 1 of the operating window. Two parallel census probes sized every candidate source
class BEFORE committing to a discovery strategy or an inclusion standard (thresholds before
measurement). Every count below regenerates from the committed artifacts
(`data/census/census-adv-era.json`, `data/census/census-13f-990.json`); rates marked **est.** are
estimates with their basis stated, not measurements._

## The funnel (measured counts, estimated affirm rates)

| Source class | Candidates (measured) | Est. affirm rate | Est. affirmed yield |
|---|---|---|---|
| SEC ADV baseline classifiers (current 439) | 439 | 30–45% (41% measured on the 59 enriched) | ~150 |
| ADV+ERA widened: family-word/domain net-new | 92 | 50–75% by tier | ~46 |
| ADV+ERA widened: structural-only net-new (few clients + high RAUM) | 129 | 10–20% (hedge-fund dominated) | ~17 |
| ERA marginal (beyond above) | 4 | — | ~3 |
| **SEC-registered ceiling (ADV+ERA, every tier)** | **661 distinct** | — | **~180–250** |
| State-registered adviser feed (family-signal names/domains) | 116 | 45–60% est. | ~55 |
| 13F filers not in ADV (SFO channel) | 2,184 net-new pool; 13–15 high-confidence + ~120–220 possible in 1,688 neutral names | effort-bounded | ~40–90 |
| IRS 990-PF >$100M family foundations (leads, not entities) | ~584–700 nationally (derived from 29,676 name-matched; 2.4% of 250-org sample >$100M) | 10–25% convert to a verifiable FO entity | ~60–175 |

**Combined realistic range: ~335–570 affirmed genuine family offices**, with 500 sitting in the
aggressive upper half — reachable only if every channel performs near its upper bound AND
per-record verification effort scales inside the window.

## Load-bearing findings

1. **SEC registration alone cannot reach 500.** The absolute candidate ceiling across every ADV+ERA
   tier is 661 firms; at realistic affirm rates that is ~180–250 affirmed. This settles Bridge
   correction #4 as mandatory, with numbers.
2. **The classifier had a measured hole:** the strong pattern matched "family office" but not
   "family offices" — 11 near-certain FOs (Colony Family Offices, WE Family Offices, …) silently
   dropped. Fixed in `pipeline/config.py` same day.
3. **"Family"-named 13F filers are mostly already ADV-registered** (24/28 Tier-1). The genuinely
   net-new exempt SFOs mostly do NOT carry "family" in their names (Soros Fund Management, MSD
   Capital) — the 13F channel is real but research-per-candidate, not regex-per-candidate. And 13F
   only sees SFOs with >$100M in US-listed securities: Bezos Expeditions and Walton Enterprises are
   confirmed absent from the entire 13F universe. That is this channel's blind spot, stated.
4. **A foundation is not a family office.** 990-PF is a lead source: the Bezos Family Foundation
   appears in the sample while Bezos Expeditions files nothing anywhere — foundation = lead,
   office = target. Conversion needs affirmative FO-entity evidence per ADR-0020, so the channel's
   volume is bounded by verification effort, not by the 29,676 name matches.
5. **A fourth channel exists that the plan missed:** the SEC state-registered adviser feed (same
   XML format, 21,763 firms, advisers typically <$100M AUM) carries 116 family-signal candidates —
   small genuine MFOs the SEC-registered feed structurally excludes. Cheap to ingest (same parser).

## What this feeds

The automated minimum-inclusion standard (day-2 ADR): the counting ontology decision now has its
evidence base, and per-source expected yields let each cycle's discovery tranche be sized and its
actual yield measured against these estimates — deviation is signal, either about the estimate or
about the classifier.
