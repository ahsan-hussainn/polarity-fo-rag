# Finding: decision-maker evidence pass over the 24 family offices (WS3, ADR-0021/0022)

**Date:** 2026-07-20 · **Method:** per-firm person research (firm team page + web/LinkedIn for
current affiliation + SEC ADV Schedule A for ownership/officer authority), ratified into
`gold.contact_adjudications`; then WS3b inferred + vendor-verified the proven person's email where
the firm publishes none. Evidence per contact in the adjudication rows; research summaries in
`data/curation/research/ws3/`.

## The governing result

**All 24 affirmed family offices now have an affirmatively-proven primary decision-maker** — the
allocation-authority contact a fund manager would actually pitch (CIO / head of investments /
owner-principal), not a title-ladder guess. Every one carries a `selection_basis` ("why this
contact") and an authority label; all 24 primaries are `stated` authority (Schedule A ownership or
an explicit investment title), none rest on title-inference alone. These 24 are now
`release_state='qualifying'` — entity affirmed (ADR-0020) **and** decision-maker proven (ADR-0021).

## What the pass corrected (the person layer was thin and partly wrong)

- **3 firms had zero people extracted** — filled from scratch: Pine Ridge (Baldo Fodera, sole owner
  of a ~$5B discretionary book), Element Pointe (Dominguez/Savir), TFO Family Office Partners
  (Chuck Carroll, CIO).
- **Over- and mis-extraction fixed:** JFG's 58-name dump reduced to the two real investment leads;
  Xception's broken `null` row resolved to two co-founders; Matter's lone contact (Kathy Lintz) was
  no longer the investment lead after the 2025-26 IWP merger (real CIO: Jerrel Armstrong).
- **A stale primary caught by Schedule A:** Timonier led with founder Tim Baker, who is **off** the
  current ADV Schedule A; Nicholas Baker is now President and majority owner. The website still
  brands Tim CEO — a live succession the Stage 1 data missed.
- **A namesake** (a different Christopher Witham) and the **Class VI investment-bank mix-up** (our
  two names ran the affiliated bank, not the family office) were caught before shipping.

## The email reality — honest, and the hardest axis

Proving *who* is far easier than proving *their email*. Across the 24 primaries:

| Email basis | Count | What it means |
|---|---|---|
| **PUB** — published by the firm | 5 | The firm publishes the individual's address; proven to be theirs. |
| **A** — vendor-deliverable inferred | 3 | Vendor reports the inferred pattern deliverable — but **not proven to be this person's mailbox**. |
| **B** — catch-all inferred | 1 | Plausible pattern on a catch-all domain; unconfirmable. |
| none (C withheld / rejected) | 15 | Unknown-inferred (C) `first.last@` guesses the vendor could not confirm were **withheld** at the WS6 review; plus JFG's vendor-**rejected** patterns. All route to the SEC-filed phone / LinkedIn. |

So **9 of 24 have a routable email** (5 firm-published + 4 vendor-checked); the other 15 route to
phone/LinkedIn. Only the firm-published 5 are proven to belong to the person. This is the axis the
Bridge Mandate singled out ("an A-grade did not prove the mailbox belonged to the named person"), and
the labels now say exactly that — an inferred A reads "vendor-reported deliverable … NOT proven to be
this person's mailbox," never "verified." **WS6 decision:** rather than ship 12 unconfirmed (C)
`first.last@` guesses labeled "unconfirmed," they were withheld — a column of look-alike inferred
addresses reads as more confident than the label admits; withholding is the honest, conservative call
(reachability down, trust up).

## What controls the product now

`build.py::_apply_contact` overlays the ratified contact, resolves the email (PUB > A/B/C >
quarantine D/F), sets `person_status='proven'`, and flips affirmed FOs to `qualifying`. Outreach
routing (`best_channel`) treats PUB as the strongest channel, A/B as emailable-but-qualified, and
sends C / no-email records to the SEC-filed phone. Export ordering leads with qualifying FOs, best
email basis first (ADR-0019 trust-ranked queue).

## Honest limits

- **Inferred A/B/C emails are pattern guesses for the proven person**, verified only for
  deliverability (A) or not at all (C). They are labeled as such and never routed as "verified."
  Converting more C's to proven addresses needs a sourced-email crawl (mailto/press), a Stage 2 job.
- **Some authority rests on ownership, not an investment title** (e.g. Hampshire's Reidy is the sole
  owner but ADV-titled CCO; Timonier's Baker is President/owner with no CIO). Ownership is a valid
  basis to commit the firm, but "runs the investment process" is inferred there — noted per record.
- **Schedule A is dated to the filing.** Affiliation `as-of` dates are recorded so the Stage 2
  monitoring loop can re-check; a 2026 filing is current now but will age.
