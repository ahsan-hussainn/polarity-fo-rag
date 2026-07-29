# Assessment Stage 2 — Operating Plan

("Stage 2" here means the assessment stage, not pipeline stage 2 / website fetch.)

Window: **Mon 2026-07-27 12:00 → Sat 2026-08-01 12:00 (+05:00).** Brief:
`D:\Polarity IQ Final Round\Stage 2\Differentiator Stage 2 _v9_2026.docx`. This plan was written
2026-07-27 ~13:30, ~1.5h into the window, and is the prioritization record the Bridge Mandate asks
for: order of work is by product consequence, and deviations get recorded here, not silently made.

## Hard gates

1. **Deployed + scheduling by end of day 2** (brief ceiling ≈ Wed 2026-07-29 12:00). Internal
   target: **first cron-triggered run tonight (Mon)**; Tue noon is the fallback.
2. **Day-2 checkpoint email** to optimize@falconscaling.com — **hard deadline Wed 2026-07-29 12:00
   (+05)**. The window's days run 12:00→12:00, so "end of day two" is Wednesday noon, not Tuesday
   midnight; this was re-derived and confirmed on day 2 (see
   `docs/findings/stage2-brief-reconciliation.md`). **Ahsan's operating decision 2026-07-28: send
   Tuesday night if the system is genuinely complete, rather than running to the deadline — but the
   spare hours exist to mature the product, not to be burned.** Contents: link to deployed
   retrieval, link to running agent, scheduler screenshot, three one-line predictions (first
   breakage; cost to refresh 1 and 500; Goal-2 confidence + abstention). Predictions are read off
   the ops ledger, and committed in-repo before sending. The brief: "a submission with no day-2
   checkpoint behind it is incomplete."
3. **Window-completion conditions** (submit when all three show in logs, not before):
   - [ ] ≥2 scheduled runs, untriggered by us, ≥48h first→last, on a platform keeping run history
         (GitHub Actions), + 2 screenshots (run list; one run detail). First scheduled run
         2026-07-27 15:18Z → 48h completes **2026-07-29 15:18Z (Wed 20:18 PKT)**.
   - [x] ≥1 real dependency failure met while running (induced allowed → must be labeled induced).
         **MET, naturally, 2026-07-27:** 9 `fetch_candidate_site` errors on scheduled runs (sites
         blocking the scraper) + 5 firms' home pages moving HTTP 200 → 202 between runs 4 and 5.
         No induced failure needed. **The day-1 `DATABASE_URL` corruption does NOT count and must
         never be cited for this** — the brief excludes "deleting or disabling your own
         configuration."
   - [x] Cross-run evidence-based staleness/trust event (clock expiry explicitly does not count).
         **MET, 2026-07-27 run 5:** `website_dark` compares run 5 against run 4 and captures the
         HTTP status change as the reason; `decision_maker_gone` fired twice on roster evidence.

## Decisions locked (details in ADRs as they land)

- **Scheduler:** GitHub Actions cron `23 */6 * * *` (odd minute; UTC), `concurrency` group so runs
  never overlap; `workflow_dispatch` allowed for smoke tests but those runs are labeled manual and
  never counted toward the two scheduled runs.
- **Cycle shape (every run):** open run ledger row → observe (website status/hash + ADV filing date
  baselines for all held records) → compare vs prior observations → evidence-based trust events →
  refresh oldest-checked batch → discovery tranche (once the inclusion gate exists) → build-gold →
  reconcile → export → incremental rag-index → close ledger row with tokens/cost/latency.
- **Staleness detectors — CORRECTED 2026-07-29 (day 3) after measuring each one.** This line
  previously claimed "3, independent" and that was not true of the code. What is actually running:
  1. **Website field-level diff** (re-extract on hash change; cosmetic changes logged but labeled).
     Real from cycle 1, and the detector that satisfied window condition 3 — 101 trust events.
  2. **Registry re-check (ADR-0036)** — REBUILT. The original ADV filing-date detector compared our
     own held `data_asof` against our own previous observation of it, which nothing updates, so it
     could never fire: 772 observations, zero events. It now asks IAPD for the adviser's current
     record and compares four live facts (filing date, registration scope, registered name, whether
     the CRD still resolves). First run: 59/59 checked, 3 firms carrying a newer filing.
  3. **Vendor re-verification — NOT AVAILABLE, and the cycle says so every run.** The
     MillionVerifier credential has been out of credits since day 1 and now returns HTTP 403. It
     was never built and cannot be until the credential is replaced. Rather than drop the claim
     quietly, `_vendor_preflight` checks the credential each cycle and ledgers the failure with the
     vendor's actual response and its consequence (held grades keep their original basis and are
     not re-asserted as current). A capability the system knows it lacks is worth more than one it
     pretends to have.

  Condition 3 is satisfied by detectors 1 and 2, both evidence-based and cross-run.
- **Concurrency:** bounded worker pool (~8) with per-host politeness + exponential backoff; batch
  caps sized so a cycle finishes well under the 6h cadence; DB work-claiming so an interrupted run
  resumes instead of duplicating (also the architecture-note §4 answer).
- **500-bar standard: entity-strict, field-permissive — RESOLVED to a tiered ontology (ADR-0028,
  decided by Ahsan 2026-07-27 day 1, census-triggered, before mass discovery).** Three counted,
  always-labeled, never-blended categories: SFO, MFO, embedded_fo_practice (evidenced, real bar).
  Wealth managers never count. A counted record does NOT need a proven contact or graded email
  (honest labels + trust-ranked, per the locked 2026-07-19 policy). Climb target ~510–520 so
  quarantines don't drop the end-of-window count below the bar.
- **Agent:** same Render service, `/agent` route; framework-free tool loop behind the provider seam;
  v1 tools: structured_search, semantic_search, fit_rank, get_record, quarantine_summary
  (per-record, metadata-only). Deterministic post-output gate (checkanswer extended), abstention
  thresholds in code, per-session raw logs in ops.
- **Retrieval extension:** fit_rank (mandate-fit ranked retrieval with per-record confidence +
  evidence trail) shipped in the public UI/API as well — the checkpoint links to it, and every goal
  submits the manual-retrieval output beside the agent output.
- **Mid-window pushes:** allowed (brief days 3–4 = "fix what breaks"); never hand-trigger the
  scheduled workflow, never hand-edit record rows, batch merges, no pushes during goal runs or
  evidence capture.

## Day plan

- **Mon (today):** MV key issue flagged (balance verified −10 credits; cycles preflight and degrade
  honestly until a fresh key lands) → 4 landmine fixes → ops schema + cost/latency instrumentation →
  operate-cycle v1 (baseline sweep of all held records + refresh + rebuild/reconcile/export/index) →
  GH Actions workflow live on master, first cron run overnight. In parallel: source census (widened
  ADV, ERA, 13F-without-ADV, 990-PF) → funnel table → inclusion-standard fork decided tonight.
- **Tue:** inclusion standard as code + ADR (identity-key crosswalk CRD/CIK/EIN/domain; retro-score
  the seed 24 through the same gate; thresholds pre-registered) → discovery tranches enter cycles →
  agent v1 + fit_rank UI → G2-shaped manual probe → checkpoint email (Tue night target).
- **Wed AM:** contingency for the checkpoint only. **Wed–Thu:** system runs; watch, fix between
  runs; climb continues; detectors accumulate; induce a labeled failure only if nothing real occurs.
- **Fri:** run goals G1–G3 (four artifacts each), architecture notes against artifacts, day-5
  checklist below. **Sat AM:** submit; keep cron running + tagged end-of-window snapshot.

## Day-5 deliverables checklist

- [ ] Complete uncurated ops export (runs, run_events, observations, trust_events, query_log) + GH
      artifacts for every run in the window.
- [ ] End-of-window export of all records incl. per-record freshness/trust fields; git tag.
- [ ] Three goals × (exact goal, manual retrieval output, structured agent output, raw run log).
- [ ] Agent tool JSON schemas (emitted from the typed definitions).
- [ ] Both screenshots; plain statement of how long the window took.
- [ ] Architecture notes (7 sections, 2–3 pages, every claim traceable to an artifact).
- [ ] Build summary <½ page: actual unpadded hours (from docs/SESSION_LOG.md), what AI produced vs
      what I changed/rejected, least-trusted claim + what would check it, personal-review
      confirmation — with a real final review pass budgeted for it.
- [ ] Email requests receipt confirmation; links stay live 7 days (cron stays on; keepalive ping;
      API credit balances checked day 5).

## Risk register

| Risk | Mitigation |
|---|---|
| MV credits −10 (verified 13:25 today) | Fresh key today/Tue (human task); cycle preflights balance, logs skip reason, never emits fake grades |
| Condition 3 never fires | 3 independent detectors from cycle 1; full baseline sweep tonight; widen compared batch Thu if silent by Wed night |
| 500 unreachable FO-only | Census decides fork tonight, pre-registered; superseding ADR if scope amended |
| Tue overload | Agent v1 trimmed to 5 tools; census moved to Mon; checkpoint contingency Wed AM |
| GH cron lag/skip | Odd-minute cron; 6h cadence gives ~12–14 runs of slack |
| Render redeploy mid-run | Batch pushes; web service and cycles are separate processes (cycles run on GH runners) |
