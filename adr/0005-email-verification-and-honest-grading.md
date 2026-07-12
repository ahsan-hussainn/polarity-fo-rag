# ADR-0005: Email verification with a pluggable verifier and honest two-axis grading

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

The highest-value cell is the principal's work email, and the client's schema pairs it with a validation
code, a code explanation, and a quality grade. Getting this right (honestly) is the decision-grade
differentiator. Feasibility findings (2026-07-12):

- **Fact (verified live from our build machine):** outbound **port 25 is OPEN** here. We connected to Google
  and Microsoft MX hosts on port 25 and received `220` SMTP banners. This contradicts the general assumption
  that port 25 is universally blocked, and it means real SMTP-level verification is possible from this host.
- **Fact (verified):** the two family-office domains in the client sample (`waltonfamilyfoundation.org`,
  `tlcapital.com`) both resolve to **Microsoft 365** mail. Research indicates M365/Workspace domains are
  disproportionately **catch-all** (accept every address), and ~30% of B2B domains are catch-all generally.
- **Inference:** realistic hard-confirm rate for inferred emails is ~50-65% for general B2B and **lower for
  family offices** (custom-domain M365 + thin public footprint of principals). Not a measured number.

## Decision

A **pluggable, layered verifier**, and grading that never overstates certainty:

1. **Syntax + MX gate** (`python-email-validator`, free) drops dead domains before any probe.
2. **SMTP RCPT probe** from a port-25-capable host (this build machine), issuing no `DATA`. Per domain, run a
   **catch-all probe** first (RCPT to a random non-existent address); if it returns `250`, the domain is
   catch-all and no address on it can be confirmed.
3. **Free-tier verification API** (Reoon, 600/mo) as a fallback/second opinion where SMTP is ambiguous or
   port 25 is unavailable on the run host.
4. **Grade on two axes** — inference confidence (was the email sourced vs pattern-guessed) x verification
   result — collapsed to a letter + a code + a plain-English explanation, mirroring the client schema:
   `VERIFIED_SOURCED` (A+), `VERIFIED_SMTP` (A), `PATTERN_CATCHALL` (B+), `INFERRED_CATCHALL` (B),
   `UNKNOWN_TEMP` (C), `RISKY` (D), `INVALID`/no-MX (F).
5. **Never promote a catch-all or unconfirmed result to "valid."** Store provenance (sourced URL or
   "inferred-from-pattern") and a timestamp on every email so the evidence survives even if a re-run cannot
   reach port 25.

## Options considered

- **Pluggable SMTP + catch-all detection + API fallback + honest grading (chosen).**
- **Pure local SMTP verification:** rejected. A deployed/cloud run host will likely have port 25 blocked
  (reproducibility risk), and SMTP is blind on catch-all domains, which is exactly the FO profile.
- **Pure paid verification API:** rejected. Free tiers are rate-limited (100-600/mo) and it hides the method;
  we want to own and show the verification logic.
- **Mark inferred emails as "verified":** rejected outright. That is the disqualifying move in the brief.

## Why this over the others

Family-office domains skew catch-all, so false certainty would fail the client's sample re-check and be
disqualifying. An honest confidence *distribution* (some A+, many B+/B, candid blanks) is more valuable and
more defensible than fake uniformity. Pluggability keeps the pipeline reproducible off this host.

## Assumptions and risks

- SMTP results on M365 are noisy; grade conservatively and cache per-domain catch-all status.
- The ~50-65% estimate is extrapolated, not measured for FOs. We will report the *actual* observed
  distribution from our own run as the real evidence.
- Ethics/legal: inferring + verifying a *work* email for B2B is standard; we keep provenance for GDPR/CAN-SPAM
  and prefer honest blanks over guessed personal data (esp. direct phone numbers).

## What would change this

If our observed confirm rate is far below estimate, we lean harder on the API cross-check and widen the
honest-blank policy. If the host we ultimately run on has port 25 blocked, we switch to API-primary verification.

## Measured update (2026-07-12) — belief revised by evidence

We probed the 143 real FO domains from Stage 1 (see `docs/findings/email-verifiability-probe.md`). The
pessimistic prior above did **not** hold:
- **73% of FO domains are mailbox-verifiable** (reject a known-fake address), only **18% catch-all**.
- **Microsoft 365 (49% of domains) is 0% catch-all** here, contradicting the "M365 is catch-all-prone" prior.
  Catch-all is concentrated in Google Workspace (58%), Proofpoint (44%), and Barracuda (100%).

Impact on the decision: the pluggable/honest-grading design stands unchanged, but the *expected distribution*
shifts optimistic, and provider-aware handling matters (grade Google/Proofpoint/Barracuda domains as
catch-all/B+ by default, treat M365 as verifiable). Still to confirm: verifier accuracy against a
known-valid/known-invalid ground-truth set (ADR-0007 Stage 6) — the 73% is a ceiling, not a measured confirm rate.

## Measured update 2 (2026-07-12) — the "verifiable" ceiling was optimistic; M365 RCPT is blocked

Running the per-address verifier over the extracted principals exposed the gap the first probe could not
see. Rejecting a *fake* address (5xx) does **not** imply a *real* one can be confirmed:
- **Microsoft 365 tenants 5xx-reject every external RCPT probe**, verified directly: `info@`, `contact@`,
  and `office@` on `flputnam.com` and `jfgfamilyoffice.com` (mailboxes that certainly exist) all return
  `550`. So the "73% mailbox-verifiable" figure counts M365's fake-rejection, but M365 will not confirm a
  real mailbox from an external host either — the actual SMTP confirm rate from this machine is ~0 for M365,
  which is ~half of all FO domains.
- Consequence for grading: "every inferred pattern rejected" must be graded **UNCONFIRMED (C), not
  undeliverable (D)** — `550` under anti-harvesting says nothing about whether the mailbox exists, and
  calling it undeliverable would overstate certainty (the disqualifying move, inverted). Code updated so
  M365 verifiable domains short-circuit to C without per-address probing (evidence-based + polite).

Impact on the decision: reinforces "never promote unconfirmed to valid" and vindicates the API-fallback
leg (ADR-0005 step 3) as the *only* path to a real A-grade confirmation for M365 domains. The honest
measured distribution from SMTP-alone is dominated by B (catch-all, plausible) and C (unconfirmable),
with A reachable only on the minority of non-M365 servers that answer RCPT truthfully. That candid
distribution — not a wall of fake "verified" — is the deliverable.
