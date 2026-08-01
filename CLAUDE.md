# CLAUDE.md — project context

Family Office Dataset + Micro-RAG. PolarityIQ Differentiator — Stage 1 passed; pre-window Bridge
Mandate corrections complete (signed off 2026-07-22). **Now INSIDE the Stage 2 operating window.**
Read this first each session. Keep it current.

## Current phase: Stage 2 operating window (Mon 2026-07-27 12:00 → Sat 2026-08-01 12:00 +05)

**Day numbering: window days run 12:00 → 12:00 PKT, not calendar midnight.** Day 1 Mon 27 12:00 →
Tue 28 12:00, day 2 → Wed 29 12:00, day 3 → Thu 30 12:00, day 4 → Fri 31 12:00, day 5 → **Sat Aug 1
12:00 = submission deadline**. This file and `docs/SESSION_LOG.md` label sittings by *calendar* date,
so their day labels and window-days differ at the edges — read the clock, not the label.

**Status: window CLOSED, packaging late (stamped 2026-08-02 00:30 PKT).** The submission ceiling was
**Sat 2026-08-01 12:00 (+05)** and it passed; the wrap sitting started ~Sun 00:00, so **submission
runs ~half a day late**. That is a packaging overrun, not an operating one — see
`docs/SESSION_LOG.md` for the plain statement. Day-2 checkpoint email **sent** Wed 29 12:00, on the
boundary. **All three window conditions met since day 3.** Measured window, end to end
(`data/ops_export/runs.jsonl`): **33 scheduled runs** (32 ok, 1 failed) from 2026-07-27 15:19Z to
2026-08-01 16:09Z = **5d 0h 51m**; 74 runs total, $0.4344. The scheduler was still firing at wrap.

Day 3 was a full adversarial review against the brief + Bridge Mandate, then the fixes it found:
ADRs **0034–0041**. Qualifying **40** as of 2026-07-30 12:05 (**34 SFO+MFO + 6 evidenced practices,
never summed**; 29 human-ratified + 11 band-released; 14 of 40 carry no contact under ADR-0028's
entity-strict/field-permissive standard; **zero `single_family_office`** — see the band gap below).
Queue: 361 candidates gated → 58 affirm / 77 needs_evidence / 226 exclude. Auto-release band
shipped, so unattended cycles can finally move the count; blanket auto-release stayed refused at
54.8% measured precision.
Second source class shipped (**13F**, ADR-0035). The ADV staleness detector was rebuilt because it
could not fire; its write volume exposed and fixed the system's real first bottleneck
(connection-per-ledger-write).

**Day-3-night funnel audit (2026-07-30, live-DB measured — read this before planning the climb).**
- **Domain resolution is the highest-yield lever.** Measured 2026-07-30 12:05: candidates with a
  resolved domain affirm at **29/82 (35.4%)**, without at **29/279 (10.4%)** — a 3.4× lift, and half
  of all affirms now come from the 23% of the queue the resolver rescued.
  `pipeline/ops/resolve.py`'s docstring says the same. Its addressable pool is now exhausted.
- **The band's route 2 was misdescribed** — corrected in ADR-0034 (documentation only; thresholds
  and `BAND_VERSION` unchanged, still 16/16 counted). **No 13F candidate can auto-release at all**:
  a 13F filer has no ADV client mix by construction, and route 2 needs a registry signal, so the
  max score across all 20 is 85 against a bar of 100. Disclosed as a measured blind spot, not
  patched. This is why the set holds **zero** `single_family_office` records.
- **CORRECTED 2026-07-31 — do not repeat the withdrawn figures.** An earlier version of this block
  claimed `hnw_raum` coverage of "state_adv 27/119 · sec_adv 54/222", i.e. that the band was starved
  of registry data. **Wrong** — a query artifact that read the newest `bronze.captures` row per
  entity (usually a `website` capture) instead of the ADV row `gate.assemble()` reads. Re-measured
  2026-07-31 06:27Z: **sec_adv 155/222 (70%) · state_adv 64/119 (54%) · 13F 0/20** — about **64% of
  ADV candidates**, not a quarter.
- **Resolver pool is exhausted, and its payoff proves the band gap.** Manual backfill (runs 41–42,
  `trigger='manual_backfill'`) proved +21 domains, 61 → 82. All 21 have since been re-gated by
  scheduled cycles: **+12 affirms (57%)** — double the 28% historical rate for resolved candidates,
  because many resolved to literal `*familyoffice.com` domains. But **only +2 reached qualifying**
  (38 → 40); the band held the other 10 for want of client-mix data. That is the channel skew above,
  measured end-to-end on fresh records rather than argued. Batch 2 returned 0/40: every one of the
  112 remaining stranded candidates has already been attempted and failed, and `_note_attempt` is
  deliberately uncapped, so cycles keep re-burning ~5 min/run at 0% until new candidates are seeded.
- **31 candidates were excluded on fetch failures that will never be retried** — they hold a real
  domain, no site text was ever captured, and `_stranded()` only targets null/social URLs.
- **1,374 `client_mix`-tier candidates were never seeded** (150 SEC + 1,224 state). Low expected
  precision, so probably leave them — but "supply is exhausted" cannot be claimed while they sit.

### The 500 shortfall: the framing to use (settled 2026-07-31)

**Do not write "supply was exhausted", and do not write "the band lacked registry data".** Both are
contradicted by our own artifacts — the census says ~335–570 with 500 in "the aggressive upper half",
and ADV client-mix coverage is 64%, not a quarter. Write the **measured yield**, which is stronger
than either because every number regenerates:

| Stage | Measured (regenerated 2026-08-02 from the live DB) |
|---|---|
| Candidates gated | **361** |
| Gate affirms | **58** (16.1%) |
| **Band-released into the product** | **11** (19.0% of affirms) |
| End-to-end automated yield | **3.0%** of gated candidates |
| Qualifying today | **40** |

**CORRECTED 2026-08-02 — the earlier "14 band releases / 3.9% yield" was wrong; do not reuse it.**
Tracing all 58 affirms into gold: **11 gate_released, 2 human_ratified, 1 quarantined, 44 held.** The
14 summed the band's 11 with 2 records a human ratified and 1 that was withdrawn — counting a human
path as automated. `reconcile` and the release tag always read `gate_released: 11`; the 14 was the
outlier. Regenerate with the queue-joined latest-decision query, not from a stamped note.

The load-bearing sentence: **the gate over-affirms and the band is what catches it.** Of the 44 held
affirms, **32 are held because the client mix contradicts the entity claim** — firms with hundreds of
non-HNW clients — and only 12 for want of usable mix. That 55% contradiction rate matches the gate's
independently measured 54.8% precision. So the shortfall is not a plumbing failure; it is what
happens when a real inclusion standard meets a candidate pool where roughly half the plausible-
looking firms are wealth managers marketing themselves as family offices.

**The arithmetic, stated plainly.** 460 more records at a 3.0% yield needs ~15,100 gated candidates.
Everything still unseeded totals roughly 3,558 (1,374 ADV `client_mix`-tier + the 13F pool), which
yields **~109 more** — landing near **150**, not 500. (The conclusion is unchanged by the correction
above; only the path to it moved.) This arithmetic now also lives in `docs/architecture-notes.md` §7,
because it was previously only here — in a file that is context, not a deliverable.

**And say what would have closed it, honestly:** human ratification, which is how 29 of the current
40 were qualified. It works and it does not scale to 500 in five days, which is precisely why
ADR-0029 built the gate. Releasing the 32 contradicted affirms would reach the number by shipping
~45% non-family-offices — Stage 1's named failure, and the one move the brief calls disqualifying.

**Remaining — all of it needs Ahsan, none of it needs code.** Done at wrap: three goals × 4
artifacts; architecture notes (all `[regen]` filled, §6 complete); `reconcile` 26/26 all_agree;
`ops-export` force-added (74 runs); agent tool schemas emitted; git tag; MillionVerifier 403 written
up as a stated limit; 500-shortfall framing settled. **Open, Ahsan only:** (1) **two scheduler
screenshots** — full run list + one run detail page, `docs/assets/` is still empty and the brief
names them explicitly — **DONE 2026-08-02**, 3 shots + README in `docs/assets/`; (2) build summary
blanks — **DONE**: hours closed at **42.7 h** across eleven sittings (all times Ahsan-supplied),
least-trusted claim set to the qualifying count of 40 and its 11 band-released records, attestation
walked and signed. **Only remaining: send the submission email** to optimize@falconscaling.com —
single email, request receipt confirmation, attach the 3 screenshots. Draft is written. Keep cron
running and links live 7 days.
**Counts anywhere in docs are stamped, not live — regenerate from `reconcile` / `/stats`.**

Brief: **`docs/brief/` (in-repo, .docx + greppable .txt) — it outranks this file, the operating
plan, and every ADR; where they disagree the brief is right.** Mandate: 24 → 500
qualifying records, kept current by scheduled unattended cycles; an agent using retrieval as a tool;
one new retrieval capability; everything read from what the system did while running. Plan, hard
gates, window-completion checklist, and locked decisions: **`docs/OPERATING_PLAN.md`** (deploy +
scheduling + day-2 checkpoint email by Wed 12:00 — internal target Mon/Tue night). Time log:
`docs/SESSION_LOG.md`. Pre-window correction record: `docs/BRIDGE_MANDATE_DISCLOSURE.md`; standards
ADR-0019/0020/0021 still govern release. **Brief reconciliation (day 2, 3 drifts fixed + 2 window
conditions found already met): `docs/findings/stage2-brief-reconciliation.md` — read it before
planning work.** Language rule everywhere: narrowest accurate status word —
"vendor reported deliverable," never "verified"; counts regenerated from the artifact, never
hand-carried.

## The one thing that matters most

**The dataset is the product; the pipeline is the delivery mechanism.** A sophisticated RAG on a thin or
unverified dataset fails, flatly. Effort goes to the *data* first: real family offices, actionable contact
intelligence, and per-cell verification. The RAG is how a client uses that data, not the point of it.

## Hard constraints (from the assessment brief)

- **50 real family office records**, produced by an **automated pipeline** (discover -> enrich -> validate).
  Manual spot-checks, judgment, and validation notes are allowed; **manual compilation is not.**
- **Dataset is pass/fail.** Scored on (1) actionability: could a fund manager act on this record today?
  and (2) verification: every high-value cell carries its basis (source + method). Reviewers sample-check.
- **Honesty beats coverage-theater.** An honest blank marked "could not verify" scores as candor. A guessed
  value dressed as verified is **disqualifying**. But a mostly-blank file is not sellable and also fails.
- **Visible reasoning or it is not evaluated.** Observed vs assumed, believed vs verified, what would change
  the conclusion. This lives in `adr/` and in honest commits, not a final polish pass.
- **Real git history.** Do not squash/strip/recreate history. No ZIP submission. Build incrementally.
- **Production-shaped RAG.** Deployable (not localhost/notebook), structured + semantic retrieval, grounding
  discipline (refuse when ungrounded), failure handling, layer separation, a live URL.
- **Ethics/legal:** principal emails/phones are PII. Source only from legitimately public data; mark honest
  blanks rather than guess.

## Deliverables

1. CSV/XLSX of 50 validated records. 2. Methodology summary. 3. Three records with a full validation chain.
4. Public/shared GitHub repo (share with optimize@falconscaling.com) with the full pipeline + real history.
5. Live URL doing real queries on real results. 6. Doc note (stack, chunking, embedding, retrieval,
what works/doesn't, improvements). Plus a half-page build session summary (actual hours, no padding).

## Stack (see ADRs for the why)

- Data + retrieval: **Supabase** — Postgres (structured) + `pgvector` (semantic) + `tsvector` (lexical). [ADR-0002]
- Schema: **mirrors FO-MAX sample**, extended with per-cell `*_source` + `*_verification`. [ADR-0003]
- Reasoning trail: **self-built lightweight ADRs**; `/adr` to add one. [ADR-0001]
- Pipeline shape: **medallion** bronze/silver/gold as Postgres schemas. [ADR-0006]
- Sourcing: **SEC Form ADV + IRS 990-PF (ProPublica) + 13F**, all public/free/verified-live. [ADR-0004]
- Email verification: **pluggable** (syntax+MX -> local SMTP probe, port 25 open here -> Reoon free API
  fallback) with honest two-axis grading; catch-all never graded valid. [ADR-0005]
- Extraction LLM: **OpenAI `gpt-4o-mini`** (Structured Outputs) behind a provider-agnostic `extract()`
  seam; escalate hard sites to Claude Haiku / Gemini free tier without a rewrite. [ADR-0008]
- RAG: **OpenAI text-embedding-3-small + hybrid RRF retrieval** [ADR-0013]; served by **one FastAPI
  app on Render** (live URL) [ADR-0014]. Gold ships through a **curation gate** — non-FO / wrong-entity
  firms excluded with auditable reasons in `gold.excluded_firms` [ADR-0015].

## Feasibility (verified live 2026-07-12)

Outbound **port 25 is OPEN** on the build machine (real SMTP banners from Google + MS MX). SEC ADV bulk feed,
IRS 990-PF ProPublica API, and EDGAR 13F all reachable and return real data. Caveat: sample FO domains are on
Microsoft 365 (catch-all prone), so email confirm rate will be modest; honest grading handles it. Principal
names are NOT in the ADV bulk feed and need a separate enrichment step (website/990-XML/ADV-PDF).

## Reference: FO-MAX sample schema (32 cols)

Entity: name, validation period, data completion score, description, investment thesis, investing sectors,
domain, website, URL quality, corporate LinkedIn, street/city/state/country.
Contact: first/last/full name, job title, location, LinkedIn, **primary email + validation code +
code explanation + quality assessment + phone**, then the same block for a **secondary email**.
(In the sample, all contact-intelligence cells are `Hidden` — that redaction marks the paid value.)

## Architecture Decision Records

| # | Title | Status |
|---|-------|--------|
| [0001](./adr/0001-adopt-lightweight-adr-system.md) | Adopt a lightweight, self-built ADR system | Accepted |
| [0002](./adr/0002-data-and-retrieval-store-supabase.md) | Supabase as data + retrieval store | Accepted |
| [0003](./adr/0003-dataset-schema-mirrors-fo-max.md) | Dataset schema mirrors FO-MAX, verifiability-first | Accepted |
| [0004](./adr/0004-sourcing-strategy-public-regulatory-data.md) | Sourcing from public regulatory data (ADV, 990-PF, 13F) | Accepted |
| [0005](./adr/0005-email-verification-and-honest-grading.md) | Pluggable email verification + honest two-axis grading | Accepted |
| [0006](./adr/0006-medallion-pipeline-in-postgres.md) | Medallion pipeline (bronze/silver/gold) in Postgres | Accepted |
| [0007](./adr/0007-pipeline-architecture-staged-medallion-dag.md) | Pipeline: staged medallion DAG, over-discover then filter | Accepted |
| [0008](./adr/0008-extraction-llm-openai-behind-pluggable-seam.md) | Extraction LLM: OpenAI gpt-4o-mini behind a provider-agnostic seam | Accepted |
| [0009](./adr/0009-silver-schema-firm-and-people-split.md) | Silver schema: firm + person split, believed vs verified cells | Accepted |
| [0010](./adr/0010-email-verification-api-millionverifier.md) | Email verification via API (MillionVerifier) behind the verifier seam | Accepted |
| [0011](./adr/0011-gold-record-shape-and-primary-contact.md) | Gold record shape: FO-MAX-mirroring, primary contact by seniority | Accepted |
| [0012](./adr/0012-fo-max-parity-enrichment.md) | FO-MAX parity enrichment: held-data fields + search-assisted LinkedIn | Accepted |
| [0013](./adr/0013-rag-embeddings-and-hybrid-retrieval.md) | RAG index: OpenAI embeddings + hybrid (pgvector + tsvector) retrieval | Accepted |
| [0014](./adr/0014-rag-serving-fastapi-and-render.md) | RAG serving: one FastAPI app (page + API), deployed on Render | Accepted |
| [0015](./adr/0015-gold-curation-gate.md) | Gold curation gate: entity validity is validated, not assumed | Accepted |
| [0016](./adr/0016-rag-intent-routing-and-actionable-answers.md) | RAG: intent routing, typed filters, actionability-shaped answers | Accepted |
| [0017](./adr/0017-rag-latency-streaming-and-connection-reuse.md) | RAG latency: streaming answers, connection reuse, parallel calls | Accepted |
| [0018](./adr/0018-ui-coverage-desk-presentation.md) | Presentation: "Coverage Desk" UI designed around grade + routing | Accepted |
| [0019](./adr/0019-release-and-quarantine-policy.md) | Release and quarantine policy for vendor-rejected contact data | Accepted |
| [0020](./adr/0020-affirmative-entity-standard.md) | Affirmative entity standard and identity resolution | Accepted |
| [0021](./adr/0021-decision-maker-evidence-standard.md) | Decision-maker evidence standard | Accepted |
| [0022](./adr/0022-contact-selection-allocation-authority.md) | Contact selection: allocation authority first, conditioned on entity category | Accepted |
| [0023](./adr/0023-answer-verification-floor.md) | Independent answer-verification floor + surface consistency | Accepted |
| [0024](./adr/0024-product-shape-and-final-review.md) | Product shape (family offices only) + final-review release decisions | Accepted |
| [0025](./adr/0025-decision-grade-record-enrichment.md) | Decision-grade record enrichment: reachability, confidence, freshness, signals | Accepted |
| [0026](./adr/0026-out-of-scope-relevance-floor.md) | Out-of-scope relevance floor: deterministic cosine-distance scope gate | Accepted |
| [0027](./adr/0027-operating-layer-cycles-run-ledger.md) | Operating layer: scheduled cycles, run ledger, evidence-based staleness | Accepted |
| [0028](./adr/0028-qualifying-500-tiered-ontology.md) | Qualifying-record ontology for the 500: tiered, labeled, never blended | Accepted |
| [0029](./adr/0029-automated-inclusion-gate.md) | Automated inclusion gate: deterministic triage, human release, measured precision | Accepted |
| [0030](./adr/0030-fit-rank-retrieval-extension.md) | fit_rank: mandate-fit ranked retrieval with evidence-based confidence | Accepted |
| [0031](./adr/0031-goal-agent-architecture.md) | Goal agent: model plans, code releases | Accepted |
| [0032](./adr/0032-domain-resolution-for-stranded-candidates.md) | Domain resolution: proving a firm's website when the registry didn't carry one | Accepted |
| [0033](./adr/0033-gate-v3-affirm-requires-published-self-evidence.md) | Gate v3: an affirm requires evidence the firm published about itself | Accepted |
| [0034](./adr/0034-auto-release-band.md) | Auto-release band: releasing gate affirms the client mix corroborates | Accepted |
| [0035](./adr/0035-thirteenf-discovery-channel.md) | 13F as the second source class: reaching the family offices ADV cannot see | Accepted |
| [0036](./adr/0036-registry-recheck-detector.md) | Registry re-check detector + pooled ledger connections | Accepted |
| [0037](./adr/0037-record-level-trust-state.md) | Evidence-based freshness on the record a buyer receives | Accepted |
| [0038](./adr/0038-agent-trace-and-history.md) | Agent raw session trace + record_history (cross-cycle tool) | Accepted |
| [0039](./adr/0039-free-text-release-gate.md) | The release gate covers free text, not just picks | Accepted |
| [0040](./adr/0040-operating-robustness.md) | Operating robustness: politeness, backoff, retry, pre-publication gate | Accepted |
| [0041](./adr/0041-entity-evidence-qualifies-either-path.md) | A human-affirmed entity qualifies on entity evidence, same as a machine-affirmed one | Accepted |
