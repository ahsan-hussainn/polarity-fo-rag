# Methodology summary — how the system finds, enriches, and adjudicates the dataset

The full reasoning trail is in `adr/` (22 records) and `docs/findings/`. Every number below is
reconciled against the final artifact (`data/gold/family_office_dataset.csv`, 2026-07-20), not
estimated. This reflects the corrected state after the Bridge Mandate pre-window pass
(`docs/findings/bridge-audit-reconciliation.md`); it supersedes the original Stage 1 figures, which
described the file before entity/decision-maker adjudication.

## 1. Discovery — public regulatory data, over-discover then filter (ADR-0004, 0007)

`python -m pipeline.cli discover-adv` streams the **SEC Form ADV bulk feed** (23,519 registered
advisers) and classifies family-office candidates in precision tiers: firm **name** contains "family
office" (71 firms, highest precision), ADV free-text mentions (167), family-capital/wealth naming (51),
and a weak HNW-client-mix heuristic (150). 439 candidates total, 207 "enrichment-ready" (website + AUM)
— ~4× headroom over the 50-record target, which let us be selective rather than scrape aggressively.
Discovery optimizes recall; entity validity is validated later, not assumed (ADR-0015).

## 2. Enrichment — website extraction behind a pluggable LLM seam (ADR-0008, 0009, 0012)

For each candidate: fetch the homepage + high-signal internal pages (team/about/strategy/contact) into
an append-only **bronze** layer with per-page provenance; stitch pages and extract structured fields
(thesis, description, sectors, founded year, named team with `is_principal` + reason) via
**gpt-4o-mini Structured Outputs** behind a provider-agnostic seam. The prompt's cardinal rule mirrors
the brief: *extract only what the text states; an honest blank beats a guess.* Provenance URLs are
stamped by our code, never by the model. Corporate LinkedIn was search-assisted and committed as a
reviewable data artifact (54/59 firms). Firm phone, street address, and **AUM** come from the ADV
filing itself — regulatory-sourced, with the filing PDF cited per record.

## 3. Adjudication — a finding controls release (ADR-0019/0020/0021/0022)

Three affirmative standards, each ratified by a human release control and each able to block a record:

- **Entity (ADR-0020).** Every firm must affirmatively prove its category from ≥2 independent
  evidence classes (SEC ADV Item 5 client mix + the firm's own self-description + third-party
  corroboration). Result over the 50: **24 affirmed multi-family offices**; 18 reclassified as
  wealth managers (11) or RIAs-with-an-FO-practice (7), kept but not counted as family offices; 2
  not a family office and 6 unresolved, both quarantined. No single-family offices — true SFOs are
  exempt from SEC registration. Details: `docs/findings/entity-adjudication.md`.
- **Decision-maker (ADR-0021/0022).** Each of the 24 FOs leads with an affirmatively-proven
  allocation-authority contact anchored on SEC ADV Schedule A (named owners/officers) plus dated
  web/LinkedIn; all 24 primaries are `stated` authority, each with a shipped "why this contact"
  basis. Details: `docs/findings/decision-maker-evidence.md`.
- **Email (ADR-0005/0010/0019).** An address is the firm-published individual address where one
  exists (5 of 24 FOs, grade **PUB** — proven to be the person's), otherwise an inferred pattern
  vendor-verified two-axis: **A** vendor-reported deliverable (inferred; *not* proven to be this
  person's mailbox) / **B** catch-all, plausible / **C** unknown. Vendor-**rejected** addresses (D
  invalid / F no mail server) are removed from operational fields into `gold.contact_audit` (28
  addresses) and never shipped. FO primary email basis: 5 PUB, 3 A, 1 B, 14 C, 1 none (JFG,
  vendor-rejected → routes to phone).

## 4. The deliverable

`data/gold/family_office_dataset.csv` — **42 rows** (24 qualifying family offices + 18 labeled
non-FOs), sorted with qualifying FOs first, best email basis first; `quarantined.csv` holds the 8
withheld firms with reasons. Per-cell basis: firm facts cite the SEC ADV filing; profile cells cite
the firm's website; each contact carries its authority basis, selection reason, and email grade +
code + plain-English explanation. **9 of 24 FOs carry a routable primary email** (PUB/A/B); 23 of 24
show a graded address.

## Honest limitations (what a buyer should know)

- **Coverage:** the SEC-registered adviser universe. Exempt single-family offices are structurally
  absent; the planned 990-PF track was not built. Reaching 500 unique FOs (the Stage 2 target)
  requires broadening beyond this source.
- **Email is the weakest axis.** Only the 5 PUB addresses are proven to belong to the named person;
  A/B/C addresses are inferred patterns, verified only for deliverability (A) or not at all (C), and
  are labeled as such — never "verified." Converting C's to proven addresses needs a sourced-email
  crawl (a Stage 2 job).
- **Some authority rests on ownership, not an investment title** (e.g. a sole owner ADV-titled CCO);
  where "runs the investment process" is inferred rather than stated, the record says so.
- **Time-sensitive signals** (recent investments, hires, news) are not yet built — a Stage 2
  requirement, not present here.
- The `is_principal` extractor over-includes (measured; see the benchmark below); `Principal Count`
  is a raw extraction count, not a validated headcount.
