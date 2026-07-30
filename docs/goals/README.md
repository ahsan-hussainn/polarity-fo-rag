# Goal artifacts

Four artifacts per goal, as the brief requires: the exact goal string, the output a user would get
from the extended retrieval **manually**, the agent's structured output, and the **raw, unedited**
run log. Goal framings are committed in `docs/three-goals.md` ahead of the runs, so a goal is a
commitment rather than something reverse-engineered from a good-looking answer.

Figures here are stamped with the run that produced them. Live counts come from `reconcile` and
`GET /stats`.

---

## Goal 1 · Multi-step commercial search — run 2026-07-30, day 4

**Exact goal string** (as committed in `docs/three-goals.md`):

> We are raising a $150M lower-middle-market industrials buyout fund out of Chicago and need LPs.
> Build me an approach list from your dataset: which family offices should we contact first, who
> specifically do we contact at each, how reachable are they, and where is your information too old
> or too thin for us to rely on it?

Dataset state at run time: **40 qualifying** (34 SFO+MFO + 6 evidenced practices), 15 unresolved,
9 quarantined — from `GET /stats`, 2026-07-30 12:05 PKT.

| Artifact | File |
|---|---|
| Manual retrieval (both attempts, exact requests + latency) | `goal1-manual-fit.json` |
| Agent structured output | `goal1-agent-output.json` (**run 47**) |
| Raw run log — `ops.runs` + `ops.agent_messages` + `ops.run_events` | `goal1-run-log.jsonl` (43 rows) |
| **Superseded attempt 1, kept deliberately** | `goal1-agent-run45-FAILED.json` + `goal1-run45-FAILED-run-log.jsonl` |
| **Superseded attempt 2, kept deliberately** | `goal1-agent-run46-PARTIAL.json` + `goal1-run46-PARTIAL-run-log.jsonl` |

### What the manual path returns

Captured against the deployed service. Two attempts, because the difference between them *is* the
finding.

**Attempt 1 — mandate only, what a user types first.** 40 considered, 10 ranked, scores 0.34–0.42,
**every row tiered `insufficient_evidence`**, all 10 with a named contact. Top hits Denver, Naples,
Atlanta — **zero Illinois records**. The mandate says "out of Chicago" and the ranking cannot honour
it, because geography was not expressible.

**Attempt 2 — the same mandate with `state: "IL"`**, a filter added to `POST /fit` on 2026-07-30 as
part of this goal's fix. 40 considered → **1**, returning `BMO FAMILY OFFICE, LLC` (Chicago, IL),
still `insufficient_evidence` on mandate fit. The record the first attempt could never reach.

Even with the filter, the manual path cannot answer the freshness half of the question. That gap is
the point of comparison for this goal.

### What the agent adds, and what it costs

Run 47: 10 model calls, 9 tool calls (`fit_rank` ×2, `structured_search` ×2, `get_record` ×2,
`semantic_search` ×1, `record_history` ×1, `quarantine_summary` ×1), **$0.00636**. Verification
passed with no repair turn.

One pick — BMO Family Office, Chicago — at `weak` confidence with a caveat, a verdict stating the
industrials evidence is insufficient because the record's stated sectors do not include industrials,
and an honest outreach line: no decision-maker is established, so general channels only. It reached
for `structured_search` here, which run 45 never called, and consulted the operating ledger via
`record_history` — which the manual path structurally cannot do.

### Run 45 failed the release check's intent, and is kept as evidence

The first attempt shipped **three picks at `confidence: strong` with no caveats** — Xception, Fifth
Avenue, Eagle Bay — over records `fit_rank` had measured `insufficient_evidence`, each citing only
an AUM band as evidence. Xception's stated sectors contain no industrials. Verification reported
`passed: true`.

Root cause was a **release control that had silently stopped applying**. `_check_output` has exactly
the right guard (`loop.py`: a pick claiming strong/moderate over a measured `insufficient_evidence`
tier is a failure), but `grounding[crd] = r` overwrote unconditionally. `fit_rank` returns records
carrying `fit_confidence`; `get_record` does not, because the tier is computed per mandate and there
is no such column, and `_slim()` omits absent keys. So nine `get_record` calls erased the measured
tier for the same CRDs, the guard read `None`, and both confidence checks skipped. A control that
still reports "passed" while no longer applying is worse than an absent one.

Fixed by merging rather than clobbering: keys in the newer view win, keys only the older view had
survive. A re-rank under a new mandate still updates the tier; a thin lookup can no longer disarm
the gate. Verified by replaying the exact sequence — **old path 0 failures, new path 1 failure**
with the correct message.

**What run 46 does not prove.** Its nine picks are all `weak` with caveats, and `limitations` now
states the fit rests on insufficient evidence — but `repaired: false`, so the model produced
compliant output on its own. `grounding` feeds the gate, not the model, so the fix did not cause the
better labels; run-to-run variation did. The fix's guarantee is narrower and worth stating exactly:
a strong-over-insufficient claim can no longer pass **silently**.

### Run 46 dropped the stated constraint too — fixed in two halves

Run 46 fixed the confidence problem and kept the geographic one: no mention of Chicago, Illinois or
BMO anywhere, `limitations` empty. `docs/three-goals.md` pre-registered exactly this ("silently
relaxing a stated constraint is the failure mode to watch for"), and the uncomfortable part was that
it was **not** a capability gap — `structured_search` already accepted a `state` filter and the logs
show the agent simply never called it.

Two things were wrong, so two things changed.

**Capability.** `fit_rank` now accepts `state`/`city` as exact filters, applied before ranking and
deliberately *not* folded into the weighted score — a firm does not become a better mandate fit by
being nearby. Plumbed through the tool and `POST /fit`. An empty geographic result now states that
the constraint held and the answer is genuinely empty, rather than looking like a failed search.

**Enforcement**, because the brief is explicit that prompt instructions do not count as enforced
control. `_check_output` extracts geographic constraints from the goal and requires each to be
honoured or disclosed. The constraint vocabulary is read from the corpus itself — distinct city and
state of qualifying records — so it cannot drift from the data. Conservative by construction: full
state names mapped to codes, city names ≥5 characters, word-boundary matching only, and **never**
bare two-letter codes, because `IN`, `OH`, `MA` and `CA` are ordinary words. `ADA` is skipped for the
same reason; a missed constraint is a disclosure gap, a false one blocks a correct answer.

The rule enforces **disclosure, not judgment.** It does not require that a record in the stated place
be recommended — the honest answer may well be "we hold one and it is a poor fit." What it forbids is
silence. Verified three ways: the run-45/46 shape fails, disclosing-without-matching passes, and
returning a matching record passes. Goals 2 and 3 extract no location, so no false positives.

### Still open: the AUM band is derived from the fund's size

Run 47 called `fit_rank` with `min_aum_usd: 150000000` and `structured_search` with
`min_aum_usd: 150000000, max_aum_usd: 10000000000`. The $150M is **the fund's size, not a constraint
on family-office AUM**, and the `min_aum_usd` tool description says so explicitly: *"Never derive
this from a fund's market segment... A $5B family office writing an LP cheque into a
lower-middle-market fund is a fit, not a mismatch."* The `max_aum_usd` value is invented outright.

It changed nothing here — Illinois holds exactly one qualifying record at any AUM — but it made the
prose wrong: `coverage_note` and `limitations` both attribute the narrow result to "the AUM
criteria" when the actual cause is geography. A customer-facing string crediting the wrong filter is
a small honesty defect, not a cosmetic one.

Reported rather than fixed, and the reason is the same one this note keeps returning to: the
guardrail is currently a **tool description**, which is a prompt instruction, and the brief says
those do not count as enforced control. Doing it properly means a deterministic rule — a size band
is only legitimate when the goal constrains the family office, not the fund — and that needs
measuring against goals that legitimately do constrain FO size before it goes in front of a release
path. Left as a known defect with the run log as evidence.

---

## Goal 2 · Uncertain-data case (verbatim) — run 2026-07-30, day 4

**Exact goal string.** Character-exactness was verified programmatically against
`docs/brief/Differentiator-Stage-2-v9-2026.txt` itself, not against a transcription:

> Identify the family offices in the dataset that are the best fit for a lower-middle-market
> healthcare services fund seeking limited partners, and tell me how confident you are in each.

Dataset state at run time: **40 qualifying**, 15 unresolved, 9 quarantined. Per the brief, no
uncertain record was cleaned away before the run.

| Artifact | File |
|---|---|
| Manual retrieval (`POST /fit`, exact request + latency) | `goal2-manual-fit.json` |
| Agent structured output | `goal2-agent-output.json` (run 48) |
| Raw run log | `goal2-run-log.jsonl` (10 rows) |

### What the manual path returns

40 considered, 10 ranked, scores 0.33–0.42, and **every single row tiered
`insufficient_evidence` with an empty evidence list**. That is the honest state of the data: no
qualifying record carries stated healthcare-sector evidence. The ranking is document similarity and
says so in `method_note`.

No AUM band was passed, deliberately. "Lower-middle-market" describes the *fund's deals*, not a
ceiling on how large its LPs may be.

### What the agent produced

Run 48: 2 model calls, 1 tool call (`fit_rank`), **$0.00117**. Verification passed, no repair.

**One pick at `weak`, eight explicit abstentions, and a coverage note saying the dataset does not
support a confident answer.** This is the behaviour the brief asks for — *"a strong system does not
confidently launder weak evidence into a clean answer"* — and it is the end of the run-9 → run-10 →
run-12 progression recorded in architecture note §6: evidence laundering, then an identical-call
loop, now an honest weak answer. The `fit_confidence` tier ceiling from `fit.py` is doing the work:
`strong` requires a *stated* sector match, so prose similarity cannot reach it.

It also correctly did **not** derive an AUM band here, which locates the run-47 defect precisely:
that was triggered by the literal "$150M" in Goal 1's text, not by a systematic bug.

### Two honest weaknesses in this run

**1. `evidence` contains an absence of evidence.** The single pick's evidence list reads *"No stated
sectors or thesis in the record; fit cannot be evidenced."* That is a caveat, not evidence.
`Pick.evidence` is declared `min_length=1`, so a record with genuinely no mandate evidence cannot be
picked without putting *something* in the field — and the model does the least-dishonest thing
available, which is to invert it. The schema is applying pressure in the wrong direction: it should
permit an empty evidence list and let the confidence tier carry the weight. Recorded rather than
changed mid-goal-run.

**2. The excluded population is not disclosed.** The answer never mentions that beyond the 40 ranked
records the system holds 15 unresolved and 9 quarantined entities. The brief's Goal-2 framing asks
that unresolved status "remain visible", and while those records are visible on every other
surface — `/stats`, `reconcile`, the Coverage Desk — this answer does not point at them. A stronger
answer would name the excluded count and why it is excluded. `abstained` also lists eight firms as
bare names with no reason, where the schema asks for the reason.

---

## Goal 3 · Paid-tier case — run 2026-07-30, day 4

**Exact goal string** (as committed in `docs/three-goals.md`):

> Which records in your coverage have changed in a way that would change how I approach them since I
> last looked, what specifically changed, and which ones should I now stop trusting?

| Artifact | File |
|---|---|
| Manual retrieval — both surfaces tried | `goal3-manual.json` |
| Agent structured output | `goal3-agent-output.json` (**run 56**) |
| Raw run log | `goal3-run-log.jsonl` (30 rows) |
| **Superseded — refused, kept deliberately** | `goal3-agent-run49-REFUSED.json` + log |
| **Superseded — answered on faulty flags, kept deliberately** | `goal3-agent-run50-PREFIX.json` + log |

### The manual path cannot answer this at all

Not "answers it worse" — cannot answer. Both surfaces, same goal text:

- **`POST /query`** returns a **refusal** from the out-of-scope floor (ADR-0026): *"That question is
  outside what this dataset covers, so I don't have grounded records to answer it."* Correct
  behaviour, and it is the whole point — the scope gate knows this is not a question about record
  content.
- **`POST /fit`** returns 5 records ranked by document similarity against a nonsense mandate, every
  one `insufficient_evidence`. Arguably worse than the refusal: plausible-looking output with no
  relationship to what was asked.

The reason is structural. Change over time is not a property of any record; it is a property of the
*history* of records. Both retrieval surfaces return current state, so neither can reach it. This is
the widest manual-vs-agent gap of the three goals, which is what the brief asks Goal 3 to show.

### What the agent produced

Run 56: 7 steps, **$0.00637**, verification passed with no repair. **4 watchlist entries, 0 picks** —
complete recall against the 4 records the ledger actually flags — each citing the current IAPD filing
date *and* the filing date the held record was built from. That two-date evidence is what makes the
answer actionable rather than a warning light.

### Run 49 refused, and the control fired on the wrong target

The agent named all 8 then-flagged records; the gate rejected every one as *"not a record any tool
returned this session"*; the repair turn could not fix it and the session withheld its answer.
Refusing beat laundering, but Goal 3 produced nothing.

Two causes, both fixed. `t_record_history` returned `recs=[]` and was `pickable: False` — yet its
no-arg branch returns `release_state='qualifying'` records, already released, as its own note says.
ADR-0039 made it non-pickable to stop **never-released** candidates being presented as family offices
to distrust, and `quarantine_summary` is still rightly non-pickable for exactly that. The same flag
also blocked the released records the tool exists to surface. Separately, the schema had nowhere to
put the answer: `picks` carry `fit_summary`/`confidence`/`outreach` — the shape of a recommendation to
act — whereas "stop trusting this" is its opposite. Added a **gated** `watchlist`, verified three ways
including the ADR-0039 regression case (a never-released firm on a distrust list must fail).

### Run 50 answered — on flags that were not evidence

Run 50 passed the gate with 7 entries, and none of them should have been there. Auditing it exposed a
defect in the **dataset**, not the goal: `website_dark` fired on `prior == 200 and now != 200`, so any
non-200 counted as the source going dark. Across the window that produced 20 events, of which **16
were HTTP 202** — a success code — and 2 were HTTP 429.

The proof was accidental. Two cycles overlapped, and the **same six firms** returned HTTP 200 at
09:03–09:04Z and HTTP 202 at 09:08–09:11Z. A host that answers 200 and 202 five minutes apart has not
gone dark; that is CDN or bot-protection behaviour toward our crawler. And 429 means we were
throttled — with a per-host politeness budget the likely cause is our own crawl rate, so counting it
as decay lets our own behaviour reduce a firm's trust.

Corrected in `pipeline/ops/cycle.py`: 2xx/3xx reachable, 429 → "could not check", 4xx/5xx flag when
the host served us before, and timeouts flag only if they reproduce on two consecutive cycles — the
same rule the materiality classifier already applies to text changes. Also added the **recovery path,
which never existed**: `trust_latest` takes the newest event per `(crd, check_type)`, so a flag stood
forever with nothing to supersede it. ADR-0037 promised a re-verified firm stops carrying a scar; that
is now true.

Flags fell **8 → 4**, and all four survivors are `adv_filing` — live IAPD showing a filing newer than
the held record's basis, which is genuine evidence. Every `website_dark` flag was withdrawn, because
every one rested on a 2xx or 429. The two raised on 429 could not clear through the normal recovery
path (that needs an observed 2xx, and a throttling host never gives one), so they were withdrawn by an
explicit ledgered correction run which states that it asserts nothing about whether the site is up —
it withdraws an inference the evidence never supported.

**Window condition 3 is unaffected.** It rests on `adv_filing` and `decision_maker_gone`, not on these.

### Remaining weakness: severity is overstated

All four entries are labelled `stop trusting`. The evidence does not support that. An `adv_filing`
event means *our source document has been superseded* — the correct action is the enum's other option,
`re-verify before contacting`. The agent's own verdict prose is closer to right ("stop trusting these
records **until they can be re-verified**") than its structured label. `coverage_note` and
`limitations` are also both empty, so the answer never states its denominator: 4 of 40.

Recorded rather than patched. The honest fix is another deterministic rule — an evidence type caps the
severity it can justify, so `adv_filing` cannot reach "stop trusting" while a confirmed dark or
`decision_maker_gone` event can. Severity is the actionable part of this answer, so it deserves
measurement rather than a same-day patch.
