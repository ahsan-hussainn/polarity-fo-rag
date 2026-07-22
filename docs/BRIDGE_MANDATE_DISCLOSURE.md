# Bridge Mandate — pre-window correction disclosure

**Purpose.** The Bridge Mandate's timing rule permits correcting the original 50 records and building
the release/entity/decision-maker standards before the Stage 2 window opens, and requires: *"Disclose
all pre-window work; it enters under the same evidence and reporting standards as everything else you
submit."* This document is that disclosure. Every number here is reconciled against the final artifact
(`python -m pipeline.cli reconcile`, 13/13 surfaces agree, 2026-07-20/21).

---

## 1. What was pre-window vs. what remains window work

**Done pre-window** (correcting the 50 + the standards those corrections require):

| Correction | What it required | Status |
|---|---|---|
| #1 Release authority | vendor-rejected data must not remain actionable | **Done** — ADR-0019; 28 addresses quarantined to `gold.contact_audit`, removed from operational fields |
| #2 Entity standard | affirmatively prove each entity's type; resolve identity | **Done** — ADR-0020; all 50 adjudicated with ≥2 evidence classes |
| #3 Decision-maker | prove identity, current affiliation, authority, chain | **Done** — ADR-0021/0022; 24/24 FOs have a proven allocation-authority contact |
| #5 Answer-verification floor | independent post-generation check on every surface | **Done** — ADR-0023; deterministic check gates release, measured 8/8 grounded |
| #7 Exact language | narrowest accurate wording; reconcile every count | **Done** — docs/UI/prompt swept; counts regenerated from the artifact |

**Deferred to the Stage 2 window** (the timing rule assigns new discovery + the operating agent to
the five days), disclosed here as not-yet-done:

- **#4 Broaden the source base.** New discovery beyond SEC ADV is explicitly window work. The entity-
  adjudication machinery (`pipeline/curate.py`) is source-agnostic and ready to vet new candidates.
- **#6 Time-sensitive signals — signal FIELDS + initial population built pre-window; operating loop is
  window work.** The 24 FOs now carry dated, sourced recent signals (27 across 17 firms, 7 honest
  blanks) in `gold.record_signals` / `record_signals.csv`, plus per-record freshness (ADV filing
  as-of + staleness flag). What is NOT built here is the mandate's *"the system notices these changes
  and adjusts"* — that operating loop is the Stage 2 agent.

## 2. Thresholds set BEFORE measurement (governance, not hindsight)

Per *"Do not set the threshold after seeing the score,"* the release policy was fixed before any
re-adjudication and is recorded in ADRs 0019–0022 and the four pre-registered decisions (2026-07-19):
qualification requires entity-affirmed **and** decision-maker-proven; entity affirmation requires ≥2
independent evidence classes; unresolved/rejected entities are quarantined (not counted); reclassified
non-FOs are kept but not counted as family offices; C-grade emails stay with a bounded label, D/F are
quarantined. The measured outcomes below followed those thresholds; none was loosened to raise a count.

## 3. Final reconciled numbers

Of the 50 SEC-discovered firms (a further 9 were hard-excluded pre-gold under ADR-0015):

- **24 affirmed multi-family offices** — `qualifying` (entity proven + decision-maker proven). Zero
  single-family offices: true SFOs are exempt from SEC registration, so the SEC-derived method cannot
  reach them (a finding, not a miss — it scopes the Stage 2 source strategy).
- **18 reclassified, kept, labeled non-FOs** — 11 wealth managers + 7 RIAs-with-an-FO-practice;
  retrievable but never presented or counted as family offices.
- **8 quarantined** — 2 not a family office, 6 unresolved; withheld from the product file into
  `quarantined.csv`, unretrievable on every path.
- **28 vendor-rejected email addresses** removed from operational fields into `gold.contact_audit`.
- **Contact reachability of the 24 FOs:** 5 firm-published emails (PUB, proven to be the person's),
  3 vendor-deliverable inferred (A, not proven to be theirs), 1 catch-all (B); the other 15 route to
  the SEC-filed phone / LinkedIn. Unknown (C) inferred addresses — uniform `first.last@` guesses the
  vendor could not confirm — were **withheld** at the WS6 human review rather than shipped as
  look-alike signal (a tightening of the pre-registered C-grade policy, in the conservative direction:
  lower reachability, higher trust).

## 4. How the work was ordered (consequence first)

The operating standard requires the order to be visible in the record. The git history and
`docs/findings/` show it: reconciliation audit → pre-registered standards → contact quarantine (#1)
→ entity proof (#2) → decision-maker proof (#3) → exact language (#7) → answer-verification floor
(#5) → cross-surface reconciliation. Highest-consequence truths (is it an FO? is the person proven?
is the contact safe?) were resolved before presentation polish.

## 5. Known gaps and honest limits (stated, not hidden)

- **Email is the weakest axis.** Only 5 of 24 FO contacts have an address proven to be theirs; the
  rest are inferred patterns (labeled as such) or blank. A sourced-email crawl is Stage 2 enrichment.
- **The grounding check is structural, not semantic.** It verifies emails/suppression/counts/category
  honesty deterministically; a grounded-but-misleading sentence is not caught (an LLM faithfulness
  judge is the next layer).
- **One eval case fails, reported:** an out-of-scope query sharing a token with a firm ("weather in
  Zurich" → Marcuard) is answered about that firm — grounded but off-intent (`rag-eval` 7/8).
- **The signal-refresh loop (#6's "over time" half) and broadened sources (#4) are not present** —
  window work per §1. The signal fields carry an initial dated population, not live maintenance.
- **Product shape resolved:** the product is the 24 affirmed family offices; the 18 reclassified firms
  live in `reclassified_firms.csv` (firm-level, category + basis, not counted), the 8 in
  `quarantined.csv`. Every one of the 50 is in exactly one file.
- **Decision-grade KPIs are heuristic composites** (documented weights in `build.py`): reachability
  (how directly you can reach the proven decision-maker — High = usable email, Medium = plausible
  email or phone+LinkedIn, Low = a single cold route; 8/13/3), confidence (proof depth), and a
  data-completeness score. They summarise the underlying proof columns; a buyer can still read every
  axis (entity category, person status, email grade) directly. "Actionability" as a holistic idea is
  reachability + confidence + a recent signal, read across those columns rather than fudged into one.

## 6. Evidence pointers

- Reasoning: `adr/0019`–`0023`; findings: `docs/findings/{bridge-audit-reconciliation,
  entity-adjudication,decision-maker-evidence}.md`.
- Adjudications with evidence: `data/curation/entity_adjudications.json`,
  `contact_adjudications.json`; research: `data/curation/research/`.
- Reproduce: `python -m pipeline.cli reconcile` (surfaces agree) and `rag-eval` (deployed path).

## 7. Human release review

The final human review (the mandate's release control) is recorded in
`data/curation/ws6_review_worksheet.md`. **Status: to be completed by the reviewer** — this section
will state the reviewer, date, and any corrections once the review is done. Until then, no record or
surface in this submission is described as "reviewed" on the strength of this document; the automated
reconciliation (§ above) is the only completed check.
