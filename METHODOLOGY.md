# Methodology summary — how the system found, enriched, and validated the dataset

Deliverable #2 of the brief. One page; the full reasoning trail is in `adr/` (15 records) and
`docs/findings/` (measured results per stage). Every number below is observed from a live run, not
estimated.

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

## 3. Validation — measured, not asserted (ADR-0005, 0010, 0015; `docs/findings/validation-layer.md`)

Three validated judgments, each with its method exposed and re-runnable:

- **Principal identification.** 425 people adjudicated blind against a documented title rubric →
  precision 0.49 (strict) / 0.78 (lenient bracket), recall 0.98, FP rate 0.43, FN rate 0.02. Failure
  mode: over-inclusion. Corroborated non-circularly against ADV employee counts (`gt-crosscheck`).
- **Emails.** Candidate addresses inferred from corporate patterns, verified via a paid API
  (MillionVerifier) behind a pluggable seam, and graded two-axis: **A** verified deliverable /
  **B** catch-all, plausible / **C** unknown / **D** authoritatively invalid / **F** no mail server.
  A catch-all or unconfirmed address is **never** graded valid. Distribution over 250 principals:
  35% A, 11% B, 4% C, 43% D, 7% F — the D bucket is reported as a finding, not hidden.
- **Entity validity (curation gate).** Nine discovered firms were institutional managers or
  wrong-entity records (e.g. Oak Hill Advisors, Hamilton Lane, SpiderRock→blackrock.com). They are
  excluded in code with written reasons persisted to `gold.excluded_firms` (ADR-0015). The shipped
  file is exactly **50 records**.

## 4. The deliverable

`data/gold/family_office_dataset.csv` — 50 records, FO-MAX-shaped, sorted actionability-first.
Per-cell basis: firm facts cite the SEC ADV filing PDF; profile cells cite the firm's website; each
email carries grade + validation code + plain-English explanation. 13 records lead with a senior
principal **and** an A-grade verified email; 39/50 carry a named senior contact.

## Honest limitations (what a buyer should know)

- **Coverage:** the SEC-registered universe. Exempt single-family offices are structurally absent;
  the planned 990-PF track was not built in the window.
- **Boundary judgment calls kept in the file** (disclosed, not hidden): wealth managers with
  family-office practices (1919, Chilton, F.L.Putnam); TFO's two registrants share a parent/domain.
- **Signals/recent-activity fields** (recent investments, hires, news) were not built — scoped out for
  verification depth on contacts over breadth of unverified columns.
- **11 records carry no principal contact** (honest blanks where team pages don't exist or the ADV
  site was social-only). They ship because their firm-level cells are verified; they are the weakest
  records and are last in the file.
- Principal `is_principal` over-inclusion is measured but not yet prompt-tuned; `Principal Count`
  should be read with the published FP rate in mind.
