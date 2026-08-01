# Scheduler run-history screenshots

The brief requires two screenshots of the scheduling platform's own run history: one showing the full
list of scheduled runs across the window, and one showing the detail page for any single run. A third
is included because the failed run is evidence for a separate window condition.

The scheduler is **GitHub Actions**, workflow `.github/workflows/operate.yml`, cron `23 */6 * * *`.
The run history is public and browsable directly at
<https://github.com/ahsan-hussainn/polarity-fo-rag/actions/workflows/operate.yml?query=event%3Aschedule>
— the screenshots are a point-in-time capture, not the only access path.

| file | what it shows |
|---|---|
| `Schedule Runs Full List.png` | The workflow run list filtered to `event:schedule`, so only platform-fired runs appear — **34 workflow run results**. Captured 2026-08-02 00:43 (+05). |
| `Runs Detail Page.png` | Detail page for `operate #32` ([run 30692096381](https://github.com/ahsan-hussainn/polarity-fo-rag/actions/runs/30692096381)) — a normal scheduled cycle, succeeded in 19m 8s, every job step visible. |
| `Failed Run Detail Page.png` | Detail page for `operate #9` ([run 30369862035](https://github.com/ahsan-hussainn/polarity-fo-rag/actions/runs/30369862035)) — the window's one failed scheduled run, **`Run operating cycle` failed after 32m 13s**, 1 error and 1 warning. Included because window condition 2 asks for real failures, and a red run in the platform's own history is better evidence than prose about one. |

**Known limitation of the full-list capture.** It is scrolled to the top of the list, so it shows
runs from **Jul 30 through Aug 2** — the visible span already exceeds the required 48 hours, and the
`34 workflow run results` header establishes the total, but the earliest scheduled runs (Jul 27–29)
are below the fold and not visible in the frame. Stated here rather than left for a reviewer to
notice. The authoritative record of all 33 scheduled runs, with exact UTC start and finish times, is
`data/ops_export/runs.jsonl` (`trigger='schedule'`), and the platform's own list at the URL above
scrolls back to the first run.

**Cross-check.** GitHub Actions reports 33 scheduled runs from `2026-07-27T15:18:47Z` to
`2026-08-01T15:45:21Z` with 1 failure. Our internal ledger reports 33 scheduled runs from
`2026-07-27T15:19:07Z` to `2026-08-01T16:09:48Z` with 1 failure. The platform history and the ledger
agree on count, span, and failure count. (The list header reads 34 because a further scheduled run
fired while the screenshot was being taken, after the deliverables were frozen.)
