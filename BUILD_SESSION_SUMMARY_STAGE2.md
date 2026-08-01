# Build session summary — Stage 2

> The Stage 1 build summary is `BUILD_SESSION_SUMMARY.md`. This is the Stage 2 summary required by
> the brief's Final Deliverables. Counts are stamped, not live — regenerate with
> `python -m pipeline.cli reconcile`. Full per-sitting time record: `docs/SESSION_LOG.md`.

**Approximate build time (unpadded):** **30.5 h** logged across six closed sittings through day 3,
reconciled against the commit history (`docs/SESSION_LOG.md`). The day-3-night funnel audit, day-4
goals, and day-5 documentation sittings are not yet totalled. **[AHSAN — finalize the total after
day 5; report actual hours, no padding.]**

**Main sessions.**
- **Day 1 (Jul 27)** — brief read + repo audit; `docs/OPERATING_PLAN.md`; ops layer + run ledger;
  GitHub Actions scheduler live on `master`; tiered-ontology decision (ADR-0028) taken before mass
  discovery, when the census showed FO-only 500 was aggressive.
- **Day 2 (Jul 28)** — domain resolution for registry-stranded candidates (ADR-0032); gate v3, an
  affirm now requires published self-evidence (ADR-0033); the agent + the `fit_rank` retrieval
  extension served at `POST /fit`; first Stage 2 qualifying records; **day-2 checkpoint email sent**.
- **Day 3 (Jul 29)** — auto-release band (ADR-0034); 13F as a second source class (ADR-0035);
  registry re-check detector + pooled ledger connections (ADR-0036); record-level trust state, agent
  trace, free-text release gate, operating robustness (ADR-0037–0040); full adversarial review.
- **Day 3 night → Days 4–5** — live-DB funnel audit; the three goals; documentation and final review.

**What the AI produced vs what I decided.** Claude Code generated most pipeline/agent code, the SQL
migrations, and the prompts. I owned the architecture and every judgment call: the tiered ontology
that refuses to blend FO categories (ADR-0028); a deterministic inclusion gate with **human** release
rather than blanket auto-release (ADR-0029), kept refused at the measured 54.8% gate precision; the
affirmative entity and decision-maker evidence standards (ADR-0020/0021); and the 500-shortfall
framing — presenting measured end-to-end yield (3.9%) honestly rather than releasing the 32
contradicted affirms to hit the number. AI-proposed figures I corrected in place rather than shipped:
a withdrawn ADV client-mix coverage figure (a query artifact reading the wrong `bronze.captures`
row), and a "~103 stranded never attempted" miscount (`resolve_attempts` increments only on failure).

**The one number I trust least.** The `VERIFIED_API` email deliverability grades. They are
vendor-*reported* deliverability on **inferred-pattern** addresses (not proven to be the named
person's mailbox), obtained pre-window while the MillionVerifier credential was live, and **never
re-verified during the operating window** (the credential has returned HTTP 403 every window run).
What would check it: restore the credential and re-run the verifier, plus a live SMTP probe and a
small real-send bounce test on the shipped grade-A rows. **[AHSAN — confirm this is your pick, or
substitute your own.]**

**Review attestation.** **[AHSAN — required; only you can sign this.]** State plainly that you
personally reviewed every submitted file and every customer-facing state (success, absence,
uncertainty, partial data, and failure) after the final build, and list anything you did not review.
