# ADR-0010: Email verification via an API (MillionVerifier), behind the verifier seam

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

Observed (verified this session): SMTP RCPT verification from our single host **cannot confirm
mailboxes** on the providers that matter here. Microsoft 365 — roughly half of FO domains — 5xx-rejects
every external RCPT probe, including addresses that certainly exist (`info@`, `contact@` on
`flputnam.com` and `jfgfamilyoffice.com` all return `550`). So the SMTP-only path yields a distribution
of B (catch-all) / C (unconfirmable) / F (no MX) and **never an A** — no confirmed emails. Detail in
`docs/findings/validation-layer.md` and the ADR-0005 "Measured update 2".

Observed (from the reference product): the FO-MAX sample carries, per contact, a `Primary E-Mail
Validation Code` + `Code Explanation` + `Email Quality Assessment` (primary and secondary). That
code+explanation+grade shape is the signature of a **third-party verification API**, not host SMTP. The
incumbent confirms emails with a paid service running warmed IP pools and provider-specific logic.

Constraint context: ADR-0005 already anticipated this — step 3 of its design is "a free-tier
verification API as a fallback/second opinion where SMTP is ambiguous or port 25 is unavailable." This
ADR executes that fallback and makes it the primary confirmation path, since SMTP-from-host is now
measured to be blind on the dominant providers.

## Decision

Add an **API email verifier behind a provider-agnostic seam** (`pipeline/verify/api.py`:
`Verifier` protocol + `get_verifier()`), mirroring the extraction seam (ADR-0008). Default provider:
**MillionVerifier** (generous free tier, simple single-email endpoint). The verifier's verdict maps to
the same honest grade scale, and — unlike host SMTP — the API can return **authoritative valid (A)** and
**authoritative invalid (D)**, so those grades become reachable. Catch-all and unknown are still never
graded valid.

## Options considered

- **MillionVerifier behind the seam (chosen):** ~10k free credits (one-time), plenty to verify several
  candidate patterns for each of ~150 principals; single-email REST endpoint; returns
  ok/catch_all/unknown/disposable/invalid.
- **ZeroBounce:** richest output (status + sub_status ≈ FO-MAX's code + explanation), but ~100/month
  free — too tight to probe multiple patterns per person. Kept as a first-class swap target.
- **NeverBounce / Reoon / Hunter:** all viable behind the same seam; NeverBounce (~1k free) and Reoon
  (ADR-0005's original pick) are drop-in alternates; Hunter also *finds* sourced emails (A+ path) but
  its free tier is too small for this volume.
- **Keep SMTP-only:** rejected — measured to never confirm on M365 (half the domains); it can gate dead
  domains (F) but cannot deliver the decision-grade A the dataset needs.

## Why this over the others

The choice of vendor is deliberately low-stakes because it sits behind the seam — the grade taxonomy and
the pipeline do not change if we swap MillionVerifier for ZeroBounce. Given that, the tie-breaker is free
throughput: MillionVerifier's credit budget lets us verify *multiple inferred patterns per person* and
so actually *find* the deliverable mailbox, not just check one guess. SMTP-from-host stays in the tree as
the zero-dependency default (`--verifier` unset) and offline `mock` keeps the pipeline testable without a
key or spend.

## Assumptions and risks

- Assumption: MillionVerifier's free credits cover the run (≤ ~150 principals × a few patterns ≪ 10k).
  If exhausted, the seam falls back to SMTP/mock without code change.
- Risk: API accuracy is itself unverified against our own ground truth. We treat its `ok` as A but the
  same ground-truth discipline (ADR-0007 Stage 6) should sample-check confirmed emails before overclaiming.
- Risk: catch-all domains remain unconfirmable *by anyone* (including the API) — those stay B, honestly.
- Data/privacy: we send inferred B2B work addresses to a third-party verifier; low-concern, same public
  footprint as the SMTP probe, and no message body is ever sent.

## Interim state (2026-07-12)

The MillionVerifier account provisioned this session returned `Insufficient credits` (0 available) on
the first live call — the client works, the account budget does not. Rather than block, we **shipped the
domain-level grader** (`--verifier domain`): one catch-all probe per domain, then grade F (dead domain) /
B (catch-all) / C (live, unverified) with no per-address probing. Result over 251 principals: B 18, C 215,
F 18, A 0 (see `docs/findings/validation-layer.md`). The API path stays built + tested behind the seam;
turning the 215 C's into A/D is a credit top-up (MillionVerifier) or a one-class swap to another verifier
(ZeroBounce ~100/mo, NeverBounce ~1k, Bouncer, Hunter) — no pipeline change. Vendor choice is deferred
until an account with confirmed credits exists.

**Update (same day):** a funded MillionVerifier key (499 credits) became available and the API pass ran
over the C-grade principals (`validate-emails --verifier millionverifier --only-grade C`). Result:
**88 A (verified), 27 B, 9 C, 109 D (authoritative invalid), 18 F** over the 251 principals; ~438 credits
spent. The API confirms M365 mailboxes host SMTP cannot, so A is genuinely reached. `--only-grade` makes
the pass resumable (upgraded rows drop out of the C filter) and credit-thrifty (dead/catch-all domains
skipped). This validates the seam end-to-end; the remaining C's and a sourced-email A+ crawl are optional
follow-ups, not blockers.

## What would change this

Free-tier exhaustion or an accuracy shortfall against the ground-truth set would trigger a swap (to
ZeroBounce for richer codes, or Hunter for sourced-email A+), which is a one-class change behind
`get_verifier()`. If a future run host had a warm, unblocked IP for SMTP, the SMTP path could return as
primary — but that is not this host.
