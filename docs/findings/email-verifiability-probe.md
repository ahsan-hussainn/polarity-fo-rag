# Findings: email-verifiability across FO domains (run 2026-07-12)

Measured, from `pipeline.verify.smtp` over the 143 unique domains of the strong ADV candidates. This was
run to test ADR-0005's *assumption* that FO domains skew heavily catch-all. That assumption did not survive
contact with real data.

## Measured result

| | |
|---|---|
| Domains assessed | 143 |
| Reachable MX | 137 (96%) |
| No MX record | 6 |
| **Catch-all (unverifiable)** | **26 (18%)** |
| **Non-catch-all (mailbox-verifiable)** | **104 (73%)** |
| Unknown (throttle/greylist/timeout) | 7 (5%) |

Provider mix: Microsoft 365 70, other 26, Proofpoint 16, Mimecast 13, Google 12, Barracuda 5, Amazon SES 1.

Catch-all rate **by provider** (this is the real story):

| Provider | n | catch-all |
|---|---|---|
| microsoft365 | 70 | **0%** |
| mimecast | 13 | 0% |
| other | 26 | 27% |
| proofpoint | 16 | 44% |
| google | 12 | 58% |
| barracuda | 5 | 100% |

## What changed vs our prior belief

ADR-0005 assumed (from general research) that M365/Workspace FO domains would be heavily catch-all, giving a
pessimistic ~50-65% confirmable ceiling. **Measured: ~73% of FO domains are mailbox-verifiable, and M365 (the
single largest provider here) is 0% catch-all.** The catch-all problem is concentrated in Google Workspace,
Proofpoint, and Barracuda, not M365. This is a belief update driven by evidence, recorded as an addendum to
ADR-0005.

## Caveats (why this is a ceiling, not a guarantee)

1. **Verifiable domain != confirmed principal.** This measures whether a domain rejects a *known-fake* address
   (so a `250` on a real one would be meaningful). It does not mean we will *find* each principal's address.
   Actual confirm rate depends on the inference step (Stage 4/5) too.
2. **Some `5xx` may be policy blocks, not recipient rejections.** We classify any `5xx` to the fake address as
   "non-catch-all." M365 throttling is usually `4xx` (would land in "unknown"), so this risk is small, but a
   `5xx` connection/policy block could be misread as "verifiable." Residual, flagged.
3. **M365 0% catch-all is suspiciously clean.** It implies these tenants run directory-based edge blocking. It
   is a positive signal but we have not yet confirmed it against a *known-valid* M365 address.
4. **Small per-provider samples** (Google n=12, Barracuda n=5): those provider rates are directional, not precise.
5. Single probe per domain did not trigger throttling; at scale, "unknown" could rise.

## The next validation this points to

The honest way to trust these numbers is a **ground-truth set**: known-valid + known-invalid + known-catch-all
addresses run through the verifier to measure its real false-positive / false-negative rates (ADR-0007 Stage 6).
That converts "73% of domains reject a fake" into "the verifier is X% accurate on addresses whose truth we know."
