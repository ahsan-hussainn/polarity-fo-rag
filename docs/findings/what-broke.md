# Finding: what broke while building, in full

**Stamped 2026-07-31** from `ops.runs`, `ops.run_events`, `ops.query_log` and git history.

This is the long form of §6 of `docs/architecture-notes.md`, which the brief caps at two to three
pages. Nothing here is summarised away there — the notes carry the one-line claim and point here for
the evidence. Every item below corresponds to a run, a commit, an ADR, or all three.

## Runs that did not end clean

Of 62 runs in the window, three did not close normally:

| run | status | what happened |
|---|---|---|
| 20 | `failed` | The reconcile release control failed the run — correctly — after publication. See "release control ran after publication" below. |
| 27 | `abandoned` | The process died without calling `finish_run`. Closed out by the next run's reaper. |
| 53 | `failed` | `server closed the connection unexpectedly` — the ledger connection exhaustion described in §5 of the notes. |

Run 27 is why the reaper exists. A killed process used to leave `status='running'` forever with cost
columns at zero while the real spend sat in `run_events`, so any total read from `ops.runs`
silently undercounted. An unattended loop whose process can die needs a way to mark the corpse.

## The defects

**Evidence laundering (run 9).** `fit_rank` promoted generic firms to "strong" healthcare fit on
token matches — `"services"` matched 15+ records. Fixed with a generic-token stoplist and a
stated-sector gate. **Recurred on day 3** in a different guise: `"lower-middle-market"` reduced to
`["lower","middle"]`, and `"middle"` substring-matched stated sectors — on the verbatim Goal 2
mandate itself. Same class of bug, second fix. Worth stating plainly because the first fix felt
complete and was not: tokenisation bugs recur wherever a new tokenizer path is added.

**The agent looped (run 10).** Five identical `fit_rank` calls, never submitted. Fixed with a
code-level loop-breaker plus a forced final submit — the last step may only call `submit_answer`.
Both are step-governance in code rather than prompt instructions, because a prompt can be argued
with.

**The staleness detector recorded model noise as world change.** 26 of 42 `website_change` events
were LLM free-text variance on pages that had not changed. Fixed with normalised comparison plus a
requirement that a delta reproduce across two cycles; then refined again when reproduction alone
turned out not to separate variance from genuine oscillation. Full detail:
`docs/findings/stage2-extraction-variance.md`.

**A detector that could never fire.** The ADV filing-date check compared our held value against our
own previous observation of that same held value — which nothing in the cycle updates. 772
observations, zero events. Rebuilt to ask IAPD what the regulator currently shows (ADR-0036).

**The third detector did not exist at all.** Rotating vendor re-verification of email grades was
claimed in the operating plan and never built; the MillionVerifier credential has been dead since
day 1 of the window and returns HTTP 403. The cycle now calls the vendor every run purely to record
the failure, with the vendor's actual response and the consequence, rather than the claim being
quietly dropped. See `METHODOLOGY.md` honest limitations.

**Release control ran after publication.** Scheduled run 20 correctly failed — 37 minutes after
shipping an inconsistent export to the live surface, which is the wrong half of the job. Split into
a pre-publication gate that runs the database-only checks before any CSV or index is written, plus
the full post-export check (surface-vs-CSV agreement cannot be tested until the CSVs exist).
ADR-0040.

**A counted category was unreachable in code.** ADR-0028 defined three counted categories; the build
could only reach two, so the first `embedded_fo_practice` record sat `unresolved` despite clearing
both human gates. Then, once reachable, it shipped **unlabelled** on four serving surfaces — a
record counted in one place and described in another.

**Auto-release, attempted and refused twice before it was accepted.** ADR-0029 rejected it at 59%
gate precision. ADR-0033 tried to fix precision by requiring published self-evidence and, measured,
did not — 54.8% — because every false affirm is a wealth manager publishing "family office" about
itself, so a self-evidence requirement cannot separate them. Only the client-mix band (ADR-0034)
cleared the bar, and blanket auto-release stayed refused. Calibration data:
`docs/findings/gate-calibration.md`.

**A record shipped with no ADV facts at all.** A state-channel firm had empty freshness, AUM, phone
and address because `_adv_facts` queried only the SEC feed. Guard added so it cannot recur silently.

**A trust detector fired on a success code.** `website_dark` used the rule "was 200, is not 200,"
which called any non-200 a source going dark. Across the window it produced 20 such events, of which
**16 were HTTP 202** — a success code — and 2 were HTTP 429, i.e. evidence about our own crawl rate
rather than about the firm. Records a buyer receives were carrying `trust_state='flagged'` on the
strength of a 2xx response, and a Goal-3 run told a user to stop trusting seven records on that
basis. Reachability is now classified (2xx/3xx reachable, 429 throttled, 4xx/5xx unreachable, errors
transient and required to reproduce across two cycles), and a recovered site supersedes its own
flag — without that branch there was no path back, because `trust_latest` takes the newest event per
(crd, check_type) and a flag stood forever. `pipeline/ops/cycle.py::_reach`.

**The release rule was asymmetric between humans and the machine.** A gate-released record qualified
on entity evidence alone, while a human-adjudicated one additionally needed a ratified
decision-maker — so a machine-affirmed entity shipped and a human-affirmed one was held out,
contradicting ADR-0028's own entity-strict/field-permissive standard. Found while re-adjudicating
the seven `ria_with_fo_practice` firms, when affirming three of them did not move the count. Fixed
(ADR-0041); qualifying went 32 → 35.

**A published coverage figure was wrong, and the correction changed the argument.** A day-3 note
claimed the auto-release band was starved of registry data (`hnw_raum` on 27/119 state and 54/222
SEC candidates). The query read the *newest* `bronze.captures` row per entity — usually a website
capture — not the ADV row `gate.assemble()` actually reads. Re-measured 2026-07-31: **155/222 SEC
and 64/119 state, about 64% of ADV candidates.** The figure was withdrawn in its own commit rather
than quietly edited, because the false version supported a comfortable story about the 500 shortfall
("we lacked the data") and the true one does not.

**The band's second release route was described as something it is not.** Route 2 was documented as
the path for firms with no usable client mix; in fact its three named signals total 85 against a bar
of 100, so it *also* requires a registry signal. The consequence is structural and was disclosed
rather than patched: **no 13F candidate can auto-release at all**, which is why the set holds zero
single-family offices. ADR-0034.

## Cases tried beyond the three goals

`ops.query_log` holds **22 logged queries** — 19 agent sessions, 2 API, 1 UI. Only three of the 19
are the submitted goal artifacts (runs 47, 48, 56). The other 16 are probes and rejected attempts,
four of which are committed under their own names rather than deleted:

| artifact | what it records |
|---|---|
| `goal1-agent-run45-FAILED.json` | a run that failed outright |
| `goal1-agent-run46-PARTIAL.json` | a run that answered incompletely |
| `goal3-agent-run49-REFUSED.json` | a run that refused |
| `goal3-agent-run50-PREFIX.json` | a run that produced a truncated prefix |

Outcomes across all 22 logged queries: **19 answered, 2 refused on the verification floor, 1 refused
as out of scope.** The refusals are the grounding discipline firing on the record rather than being
asserted in prose.

## Scale: what breaks next, with the reasoning

The first bottleneck already broke and is fixed (ledger connection establishment, §5 of the notes).
In order after it:

1. **Website fetch wall-clock, ~500–800 records.** A cycle makes one home-page fetch per held record
   plus the discovery tranche. At ~1.4s mean and 8 workers that is ~15 min at 500 and ~2.5 hours at
   5,000 — past the 6-hour cadence once retries and per-host politeness are counted. The fix is
   sharding by cadence (not every record every cycle), which is a policy change, not an architecture
   one.
2. **`build_gold` full recompute, ~1,000–2,000 records.** It rebuilds every row every cycle (60s at
   50, ~1.2s/record). Linear, that is ~10 min at 500 and ~100 min at 5,000; if superlinear it binds
   sooner. Incremental rebuild is the fix and is not built.
3. **The per-cycle re-extraction budget** — already found and fixed once. A flat cap of 10 against a
   measured 11.4% change rate does not merely delay work, it fails to *converge*: skipped records
   keep their old hash and re-count as changed next cycle, so the backlog grows without bound. It now
   scales with the set (30%, floor 25). `pipeline/ops/cycle.py::reclassify_budget`.
