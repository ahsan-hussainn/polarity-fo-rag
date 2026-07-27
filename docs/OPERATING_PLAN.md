# Assessment Stage 2 — Operating Plan

("Stage 2" here means the assessment stage, not pipeline stage 2 / website fetch.)

Window: **Mon 2026-07-27 12:00 → Sat 2026-08-01 12:00 (+05:00).** Brief:
`D:\Polarity IQ Final Round\Stage 2\Differentiator Stage 2 _v9_2026.docx`. This plan was written
2026-07-27 ~13:30, ~1.5h into the window, and is the prioritization record the Bridge Mandate asks
for: order of work is by product consequence, and deviations get recorded here, not silently made.

## Hard gates

1. **Deployed + scheduling by end of day 2** (brief ceiling ≈ Wed 2026-07-29 12:00). Internal
   target: **first cron-triggered run tonight (Mon)**; Tue noon is the fallback.
2. **Day-2 checkpoint email** to optimize@falconscaling.com — target Tue night, internal hard stop
   Wed 10:00: link to deployed retrieval, link to running agent, scheduler screenshot, three
   one-line predictions (first breakage; cost to refresh 1 and 500; Goal-2 confidence + abstention).
   Predictions are read off the ops ledger, and committed in-repo before sending.
3. **Window-completion conditions** (submit when all three show in logs, not before):
   - [ ] ≥2 scheduled runs, untriggered by us, ≥48h first→last, on a platform keeping run history
         (GitHub Actions), + 2 screenshots (run list; one run detail).
   - [ ] ≥1 real dependency failure met while running (induced allowed → must be labeled induced).
   - [ ] Cross-run evidence-based staleness/trust event (clock expiry explicitly does not count).

## Decisions locked (details in ADRs as they land)

- **Scheduler:** GitHub Actions cron `23 */6 * * *` (odd minute; UTC), `concurrency` group so runs
  never overlap; `workflow_dispatch` allowed for smoke tests but those runs are labeled manual and
  never counted toward the two scheduled runs.
- **Cycle shape (every run):** open run ledger row → observe (website status/hash + ADV filing date
  baselines for all held records) → compare vs prior observations → evidence-based trust events →
  refresh oldest-checked batch → discovery tranche (once the inclusion gate exists) → build-gold →
  reconcile → export → incremental rag-index → close ledger row with tokens/cost/latency.
- **Staleness detectors (3, independent):** website field-level diff (re-extract on hash change;
  cosmetic changes logged but labeled), ADV filing-date delta, rotating small-sample vendor
  re-verification. Any one firing satisfies condition 3; status tracked daily.
- **Concurrency:** bounded worker pool (~8) with per-host politeness + exponential backoff; batch
  caps sized so a cycle finishes well under the 6h cadence; DB work-claiming so an interrupted run
  resumes instead of duplicating (also the architecture-note §4 answer).
- **500-bar standard: entity-strict, field-permissive.** Only affirmed FO classes count toward 500;
  a counted record does NOT need a proven contact or graded email (honest labels + trust-ranked, per
  the locked 2026-07-19 policy). Reclassified wealth managers never count. If the Mon-night source
  census shows this cannot reach 500, the fallback is decided then via a superseding ADR amending
  ADR-0024 — before mass measurement, never after. Climb target ~510–520 so quarantines don't drop
  the end-of-window count below the bar.
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
