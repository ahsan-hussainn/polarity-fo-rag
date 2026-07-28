# Reconciling the build against the brief (day 2, 2026-07-28)

The brief was committed to the repo today (`docs/brief/`); before that it lived only as an absolute
path on one machine and was worked from memory and digests. This is the line-by-line reconciliation
of what we built against what it actually says. Three drifts found, two open questions closed, two
window conditions found already met.

The brief outranks every other document here. Where the operating plan or an ADR disagrees with it,
the brief is right.

---

## Closed: who releases a gate affirm

**Open question:** ADR-0029 says humans review "a defensible sample of gate-only decisions," but the
day-1/2 machinery routes every affirm through per-record ratification in `gold.entity_adjudications`.
With ~140 affirms incoming, the two readings differ by several hours of human time.

**The brief settles it** (Mandate, ¶3):

> The system must perform the repeatable work at scale. Human judgment is allowed and expected where
> identity, classification, source conflict, uncertainty, or release safety requires it. Human
> intervention does not occur inside unattended scheduled runs; your judgment must be visible in the
> policies you design, the inclusion and release decisions you make, and the final review of what you
> submit. **Manual row-by-row construction does not satisfy the mandate**, and automation does not
> replace your final review of what you ship.

Ratifying 140 records one at a time *is* row-by-row construction. It would move the release decision
out of the designed policy and into hand-work, which is the thing the brief names as not satisfying
the mandate. The gate is where the judgment belongs; sampled review measures whether the gate
deserves that trust; the final review pass covers what ships.

**Resolution:** gate-affirmed records enter gold labeled as gate-released, with the review sample's
measured precision stated on every surface. `gate-review` becomes the sampling instrument rather
than a per-record turnstile. Per-record adjudication stays available and still outranks the gate
wherever a human uses it (ADR-0029's precedence rule is unchanged). This needs a superseding ADR
because it changes what a release decision means.

Note the brief's own vocabulary supports the labeled-uncertainty approach: "a record may carry
clearly labelled uncertain fields."

## Closed: what days 3–4 are for

**Open question:** whether to spend days 3–4 building further discovery channels.

**The brief settles it** (Mandate, ¶4):

> Your source strategy is part of the product. A source may be good enough to surface a candidate
> record without being strong enough to establish its identity, classification, decision-makers,
> mandate, contacts, or current relevance. Use each source for what it can actually support. No
> minimum source count is prescribed, but **scaling one convenient registry does not demonstrate
> market discovery if its blind spots pass into your records unchanged.**

Both channels we ship are Form ADV — the SEC feed and the state feed are the same registry with the
same blind spots (advisers who file; no unregistered single-family offices; website coverage that is
a registry field, not a fact about the firm). Today's measurement is exactly the blind spot passing
through: 21 of 30 state candidates had no usable website, so 20 of them died on thin evidence.

This makes at least one structurally different source a **scored requirement**, not an optional
extra. 13F (holdings-derived) and 990-PF (foundation-derived) both reach entities Form ADV cannot.

The first half of that paragraph also ratifies the gate's existing design: ADV surfaces the
candidate, the firm's own site establishes identity. That split is already how the gate scores.

---

## Not a drift — the day-two deadline, stated explicitly so it is not re-litigated

The brief says "**By the end of day two**, send a brief checkpoint email." A first pass at this
reconciliation read "day two" as a calendar day (day 1 = Monday, so the email due Tuesday night) and
recorded the operating plan's Wednesday ceiling as drift. That was wrong, and the plan was right.

The window runs **Mon 2026-07-27 12:00 → Sat 2026-08-01 12:00 (+05)**, five 24-hour days whose
boundary is **12:00, not midnight**:

| day | from | to |
|---|---|---|
| 1 | Mon 12:00 | Tue 12:00 |
| 2 | Tue 12:00 | **Wed 12:00** |
| 3 | Wed 12:00 | Thu 12:00 |
| 4 | Thu 12:00 | Fri 12:00 |
| 5 | Fri 12:00 | Sat 12:00 |

So the checkpoint email is due **before Wed 2026-07-29 12:00 (+05)**, which is what
`docs/OPERATING_PLAN.md` already said. The same boundary governs "deployed and scheduling by the end
of day two" — met on day 1.

**Operating decision (Ahsan, 2026-07-28):** send tonight if the system is genuinely complete rather
than running to the deadline, but the deadline is Wednesday noon and the extra hours are there to
mature the product, not to be spent. The brief's stake is unchanged: "a submission with no day-2
checkpoint behind it is incomplete."

## Drift 1 — the day-1 CI failure does not count as the required failure

The window's second condition asks for "at least one real failure of something the system depends
on, met while running." Day 1's `DATABASE_URL` corruption (CI run 1) was a real failure and is
honestly logged, but the brief excludes exactly this class:

> **Deleting or disabling your own configuration does not count.**

That was our own configuration. It must not be cited as satisfying condition 2 anywhere in the
submission. Recorded here so no later document reaches for it.

## Drift 2 — the Stage 1 records still sit under the Stage 1 standard

> **What counts toward the 500.** The 500 includes your original Stage 1 records, **brought under the
> same Stage 2 standard before submission.**

The 24 currently-qualifying records were adjudicated under ADR-0020 (Stage 1). They have been
*scored* by the Stage 2 gate through `gate.retro()` as calibration, but scoring for calibration is
not the same as bringing them under the standard.

Two consequences, one of them favourable:

- The 24 must be re-evaluated under ADR-0028/0029 and carry the same category vocabulary and
  release basis as the new records, or the set is not one dataset under one standard.
- The 7 `ria_with_fo_practice` records currently sitting `unresolved` may re-enter as
  `embedded_fo_practice` **if** they clear category 3's evidence bar. ADR-0028 anticipated exactly
  this ("may re-enter qualifying only by clearing the category-3 evidence bar through
  adjudication"). That is measured upside, not a reclassification of convenience.

## Drift 3 — "500" is scored on how, but a miss is still a miss

Worth quoting in full because it changes where effort belongs:

> Five hundred is the bar, not a target to approach. We are not counting rows for their own sake. We
> are watching how the system reaches and holds that number: how it handles concurrency, rate limits,
> partial failures across hundreds of records, and the cost curve at volume. **Brute-forcing 500 with
> no concurrency design, no cost discipline, and no recovery hits the number and fails the stage.
> Reaching 500 cleanly, cheaply, and unattended is the thing we are scoring.**

…and immediately after:

> do not use future scalability claims to excuse missing the 500-record operating bar in this stage.

Both are true at once: padding to 500 fails, and missing 500 is a real miss that scalability prose
cannot cover. The measured projection (~105 qualifying at window close, `docs/SESSION_LOG.md`) is a
miss on the bar. The response is to maximise honestly through a second source class, keep the
concurrency/cost/recovery evidence strong because that is explicitly what is scored, and
pre-register how the shortfall is reported before the final count is known.

---

## Found already met: window conditions 2 and 3

Checked against the ledger rather than assumed.

**Condition 2 — a real dependency failure met while running.** Satisfied by natural failures, none
of them our own configuration:

- 9 `fetch_candidate_site` errors during scheduled runs — candidate sites that blocked or failed the
  scraper ("a source blocks the scraper"; "a record cannot be resolved").
- 5 firms whose home pages went HTTP 200 → HTTP 202 between run 4 and run 5 (CRD 106079, 106223,
  142856 among them) — a source shape-change met mid-window.

**Condition 3 — a staleness/trust check that fired across runs.** Satisfied, evidence-based and
cross-run: the `website_dark` events above compare run 5 against run 4 and capture the HTTP status
change as the reason; `decision_maker_gone` fired twice on roster evidence. Neither is clock-based.

Consequence: **no induced failure is required**, and days 3–4 do not need to be spent manufacturing
conditions. (Today's materiality fix matters here — a detector firing on its own model noise would
have made these real events unreadable among the false ones.)

**Condition 1** remains on track: first scheduled run 2026-07-27 15:18Z, so the 48-hour span
completes 2026-07-29 15:18Z (Wed 20:18 PKT).

---

## Confirmed aligned (checked, no action)

- **Goal 2 verbatim** — the goal string in runs 9–12 is character-exact against the brief.
- **Enforced control, not prompt instructions** — "the system must enforce, in its control flow,
  what it may claim, what it must refuse, and what data it may rely on." ADR-0023's verification
  floor and the deterministic post-output gate are code branches, not prompt text.
- **Climb inside the window** — "The climb to 500 can run inside the operating window; the system
  does not need to reach 500 before scheduled operation begins."
- **Quarantine is not a penalty** — "quarantining for an evidence-based reason is the system
  working," which is ADR-0019's position.
- **Uncertain records stay in for Goal 2** — "Do not remove or hide uncertain records merely to make
  this goal easier." The 18 unresolved and 8 quarantined records remain visible and labeled.

## Open items this reconciliation raises

- Architecture note §5 asks a question not yet answered from run data: at 5,000 records, what breaks
  first, which component, at what volume, on what evidence. "Nothing breaks" is explicitly rejected.
- Every user-visible state — success, absence, uncertainty, partial data, failure — must read to a
  nontechnical buyer. The `/agent` surface needs an audit against that list, not just `/`.
- Architecture note §1 must name each source class, what it was strong enough to establish, and its
  material blind spots. Today's website-coverage measurement is the substance of that section.
