# Stage 1 findings: ADV discovery (run 2026-07-12)

Real output from `python -m pipeline.cli discover-adv` against the live SEC firm feed
(`IA_FIRM_SEC_Feed_07_11_2026`). Numbers are observed, not estimated.

## The funnel

| Metric | Value |
|---|---|
| Firms scanned | 23,519 |
| Scan time | ~30 s |
| Candidates (total) | 439 |
| — strong (name or free-text "family office") | 238 |
| — medium (family capital/wealth/partners naming) | 51 |
| — client_mix (weak HNW-heavy heuristic) | 150 |

Within the **238 strong**:
- 71 matched on the **firm name** containing "family office" (highest precision).
- 167 matched on **free-text** "family office" in the filing's Other fields (lower precision, see caveats).
- 211/238 (89%) have a **website** (needed for enrichment: thesis, team, email pattern).
- 223/238 (94%) report **AUM** (median $681M; max $225B likely an outlier/large MFO to validate).
- 215/238 (90%) are US-based.
- **207 are "enrichment-ready"** (website AND AUM present).

## What this settles

ADR-0007 assumed "a few-hundred candidate pool is enough to yield 50 after attrition." **Confirmed with
real data**: 207 enrichment-ready strong candidates, before we even add the 990-PF foundation track. We have
~4x headroom against the target of 50, which means we can afford to be selective and prioritize the highest-
precision 71 name-matches plus the best free-text matches. The client_mix weak tier is likely unnecessary.

The 71 name-match samples are unambiguously real family offices (Custos, Longwall, Arrowroot, PointOne,
Seneschal, Founders, Aurelius, Eagle Bay Family Office, etc.), which is a good precision signal for that tier.

## Honest caveats (what could be wrong)

1. **Free-text matches (167) are lower precision.** A firm that lists "family office services" among many
   offerings is not necessarily a family office. These require Silver-stage validation (confirm the entity
   genuinely *is* a family office, not a generic RIA that mentions the term). We keep the name-match tier as
   the high-confidence core.
2. **"Candidate" != "confirmed family office."** Discovery optimizes for recall + a precision-tiered signal.
   Precision is Silver's job (website/filing evidence), not Stage 1's.
3. **The $225B max AUM is suspicious** and may be a false positive or a very large MFO. Flag for validation.
4. **13 strong candidates are missing city** (MainAddr parsing gaps in the feed, e.g. Custos). Minor; will be
   backfilled or marked as honest blanks during enrichment.

## Coverage note (carried from ADR-0004)

This is the SEC-registered universe. Genuine single-family offices that qualify for the registration exemption
are absent here; the 990-PF track (family foundations) partly offsets that. Stated plainly, not implied away.
