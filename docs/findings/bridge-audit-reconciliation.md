# Finding: Bridge Mandate WS0 — reconciliation audit of the Stage 1 artifact

**Date:** 2026-07-19 · **Scope:** every load-bearing count and claim in the shipped Stage 1
submission, regenerated from the final artifact (`data/gold/family_office_dataset.csv`), the live
database, and the code — per the Bridge Mandate rule that counts must be *generated from, or
reconciled against, the final artifact*. This document is the first entry of the pre-window
operating record. Method for every row: the number was recomputed, not re-read.

---

## 1. Count reconciliation — claimed vs measured

| Claim | Where stated | Claimed | Measured | Verdict |
|---|---|---|---|---|
| Shipped records | METHODOLOGY §3, §4 | 50 | 50 | ✅ |
| Records with a named primary contact | METHODOLOGY §4 | 39/50 | 39/50 | ✅ |
| Records with no principal contact | METHODOLOGY limits | 11 | 11 | ✅ |
| Records leading with senior principal **and** A-grade primary email | METHODOLOGY §4 | **13** | **12** | ❌ |
| Principals measured (grade distribution base) | METHODOLOGY §3 | 250 | 250 (DB) | ✅ |
| Model-flagged principals / B-grade count | validation-layer.md | **251 / B=27** | **250 / B=26** | ❌ |
| People adjudicated for ground-truth labels | METHODOLOGY §3, validation-layer.md | 425 | 425 label rows; **silver now holds 424** | ⚠️ stale |
| A-grade principals (API-confirmed deliverable) | validation-layer.md | 88 | 88 (DB) | ✅ |
| Corporate LinkedIn coverage | METHODOLOGY §2 | 54/59 | 54/59 (DB); 45/50 in shipped file | ✅ |
| Curation-gate exclusions | METHODOLOGY §3 | 9 | 9 (`gold.excluded_firms`) | ✅ |
| ADR count | METHODOLOGY header, README | "15 ADRs" | 18 ADRs | ❌ stale |
| Discovery funnel (23,519 → 439 → 207) | METHODOLOGY §1 | — | not re-run this audit; re-runnable via `discover-adv` | ⏸ unverified here |

### Root causes of the two real mismatches (not just the deltas)

- **13 → 12.** The "13 lead with A-grade" figure was measured over the **pre-curation 59-firm
  silver set** (`validation-layer.md` Part 2, which names Oak Hill's Glenn August as an example).
  The ADR-0015 curation gate then excluded Oak Hill, and METHODOLOGY copied the stale
  pre-curation number into a post-curation claim. Lesson encoded in WS4: counts in prose must be
  regenerated from the final artifact by script, never carried forward by hand.
- **425/251/B=27 → 424/250/B=26.** Person id 332 — firm "Element Pointe Family Office", name
  "Element Pointe", title **"Founders"** — was a non-person artifact row (the extractor emitted
  the firm's founders as a single person). It was correctly deleted from silver *after* the
  ground-truth export and the validation-layer write-up, and neither document was updated. Two
  defects in one: a reconciliation failure, and direct evidence that the person pipeline could
  emit non-persons (relevant to the WS3 decision-maker standard).

## 2. Vendor-rejected contact inventory — the precise formulation

The Bridge Mandate's count is **exact and complete**: the shipped file contains **28 vendor-rejected
email addresses in operational fields** — 16 in `Primary Email`, 12 in `Secondary Email`, all
grade **D** (`INVALID_API`: the verifier reported every inferred pattern undeliverable).

Additionally there are **4 F-grade contact slots** (2 primary, 2 secondary; `INVALID_NO_MX`, at
Collective Family Office and Crestwood Advisors) — these already ship a **blank** email cell with
only the grade/code as metadata, so no rejected *address* ships for them. Under the WS1 release
policy the F evidence moves to the audit trail like the D's, but the defect class differs:
D = rejected value in an operational field; F = correctly blanked, metadata only.

**Precision note for our own reporting:** an earlier internal draft described "4 F-grade
addresses" — wrong; they are graded slots with no address. This is exactly the class of
imprecision the mandate penalizes, caught by reconciling against the artifact before claiming.

C-grade slots (2, both primary; `UNKNOWN_API`) ship addresses and **stay** under the
pre-registered policy: not vendor-rejected, bounded label, never a recommended channel.

## 3. Identity-resolution findings (WS2 targets)

- **Confirmed duplicate-domain pair:** two shipped records share `tfopartners.com` (TFO's two SEC
  registrants under one parent/domain). METHODOLOGY disclosed this as a "boundary judgment call";
  under the mandate's standard ("an affiliate counted separately without evidence that it is a
  separate office does not count") it must be resolved to one entity or affirmatively evidenced
  as two.
- **Known entity-category suspects, already disclosed in METHODOLOGY:** 1919 Investment Counsel,
  Chilton, F.L.Putnam — wealth managers with family-office practices. Under WS2 they get
  affirmative category labels (`ria_with_fo_practice` / `wealth_manager`) instead of shipping as
  unlabeled "family offices".
- **Structural gap:** the exported CSV carries **no CRD / stable entity identifier** — identity
  resolution cannot be audited from the artifact alone. WS1 schema work adds the identifier to
  the export.

## 4. Claim-language and surface defects (file:line inventory)

Suppression / surface-consistency (code):

- `pipeline/rag/answer.py:106` — D-grade addresses are rendered **into the model prompt** (with
  their grade, but present and quotable).
- `pipeline/rag/answer.py:137-140` (`_sources`) — D-grade primary and secondary addresses ship
  to the UI source cards ("tagged alternatives" — the leak the mandate named).
- `pipeline/rag/index.html:297` — coverage panel shows `sources.length` as "N targets", which
  counts nearest-match fallback records that the prose correctly labels as non-matching (the
  live probe the mandate described).
- `pipeline/gold/build.py:116-126` — `data_completion_score` counts `primary_contact_email` and
  `primary_email_grade` as populated even when the grade is D, so unusable contact data inflates
  the completion score.

Language stronger than the evidence (docs/copy):

- `pipeline/rag/index.html:153-155` — the interface promise the mandate quoted verbatim.
- `pipeline/rag/answer.py:39,43` — `best_channel()` calls A-grade "verified"; SYSTEM prompt
  equates grade A with "verified". Bounded form: "vendor reported deliverable".
- `pipeline/eval.py` module docstring, `pipeline/cli.py:359-366`, `docs/findings/validation-layer.md:17,77` —
  "ground truth", "hand-labelled", "human adjudication" for what is a **proxy-label benchmark**
  (422/425 labels rule-generated, 3 manual overrides).
- `docs/findings/validation-layer.md:119` — "88 principals now carry a verified work email".
- `docs/validation-chains.md:29` — "person, title, and firm are **verified** from the firm's own
  site" (a site mention proves neither identity nor current affiliation per the mandate);
  `:38` — "named principals … remain verified and actionable".
- `README.md` deliverables table — "50 **validated** family-office records";
  `BUILD_SESSION_SUMMARY.md` — "exactly 50 **defensible** records", "88 **verified** emails";
  `METHODOLOGY.md:48` — "A-grade **verified** email" (count + status word).
- Outside the repo: the Task 2 analysis mixed one-time revenue into an MRR argument (named in
  the mandate; correction lives in the Stage 2 submission, not this repo).

## 5. What a buyer-grade honest statement of the file now looks like

50 records; 39 name a primary contact; 12 lead with a contact whose inferred address the vendor
reported deliverable; 28 operational email cells hold vendor-rejected addresses; one domain is
double-counted pending identity resolution; at least 3 records are wealth managers with FO
practices rather than family offices; no record carries dated evidence of the named person's
current affiliation or authority beyond a title. That statement — not "50 validated records" —
is the baseline the pre-window corrections start from.

## 6. What happens next (pre-registered before any further measurement)

The correction standards are defined **before** re-adjudication, per the mandate's
thresholds-before-measurement rule: ADR-0019 (release & quarantine policy), ADR-0020 (affirmative
entity standard + identity resolution), ADR-0021 (decision-maker evidence standard). The four
governing policy decisions (trust-ranked qualifying bar; quarantine unresolved entities; labeled
ontology retained; C-grades kept with bounded labels) were fixed on 2026-07-19 before this audit's
adjudication work begins, and are recorded in those ADRs.
