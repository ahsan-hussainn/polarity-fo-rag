# ADR-0041: A human-affirmed entity qualifies on entity evidence, same as a machine-affirmed one

- **Date:** 2026-07-29
- **Status:** Accepted (aligns the code with ADR-0028's pre-registered standard; makes ADR-0034
  consistent across both release paths)

## Context

Re-adjudicating the seven `ria_with_fo_practice` records under ADR-0028 category 3 promoted three
of them to `embedded_fo_practice`, `affirmed` — and **the qualifying count did not move.** They
stayed `unresolved`.

The reason exposed a defect that had been invisible until ADR-0034 landed. The build had two
release paths with different standards:

| path | requires | outcome |
|---|---|---|
| gate-released (ADR-0034) | entity evidence + the measured client-mix band | **qualifies**, `person_status='not_established'` |
| human-adjudicated | entity evidence **AND a ratified decision-maker** | held out without the contact |

So a **machine**-affirmed entity was released on entity evidence alone, while a **human**-affirmed
entity carrying the same category and stronger judgement was held out. The weaker signal got the
more permissive treatment. Nobody designed that; it is a Stage 1 rule (`qualifying` = entity +
person, from ADR-0021) that survived into a world where ADR-0034 had introduced a second path.

It also contradicts a standard pre-registered on **day 1**, before any count pressure existed —
ADR-0028 and the operating plan both state the bar as **entity-strict, field-permissive**:

> A counted record does NOT need a proven contact or graded email (honest labels + trust-ranked,
> per the locked 2026-07-19 policy).

## Decision

A record with a **human adjudication that is `affirmed`, in one of ADR-0028's counted categories,
and not a duplicate** qualifies on entity evidence alone — exactly like a gate-released record. It
ships with `person_status='not_established'`, `release_basis='human_ratified'`, and a
`release_basis_detail` saying plainly that no decision-maker has been ratified.

**No contact data ships on such a record.** Silver holds extracted people for most firms and the
build populates contact cells before release is decided, so both entity-only paths now route
through one `_suppress_unratified_contact()` helper. Presenting an extracted name as the proven
decision-maker is the Bridge Mandate's corrected failure, and having two copies of that rule is how
it comes back.

**The reconcile invariants were re-keyed from release *basis* to the *claim being made*,** which is
what they were always really about. "human_ratified implies a proven person" stopped being true;
these are stronger and basis-independent:

- claiming a proven decision-maker requires a ratified one;
- no unratified contact data ships on any record;
- a record released on entity evidence alone presents no decision-maker;
- `person_status` is always one of `proven` / `not_established`.

## Scope, measured before changing anything

Exactly **3 records** move: the three just re-adjudicated into category 3. Every other affirmed
record in a counted category already has a ratified contact (25 MFOs + Compass), and the 15
affirmed-but-not-counted records (wealth managers, the remaining RIAs) stay `unresolved` regardless
of this rule. Qualifying goes 32 → 35: **30 family offices + 5 evidenced practices**, still reported
separately and never summed.

## Options considered

- **Align the code to the pre-registered standard (chosen).**
- **Leave it and adjudicate contacts for the three:** rejected — it would fix three records while
  leaving the inconsistency in place for every future one, and the decision-maker work is a
  genuinely separate evidence pass that should not be forced by a release-rule bug.
- **Tighten ADR-0034 instead, so gate-released records also need a contact:** rejected — it would
  make the count fall, which is fine, but it would do so by abandoning a standard set on day 1 in
  favour of a stricter one adopted on day 3 with the count in view. Moving a bar *downward* under
  pressure is obviously wrong; moving one *upward* after seeing the number is the same error
  wearing a respectable coat.
- **A distinct `release_basis` for entity-only human records:** rejected — it fragments the
  vocabulary a buyer reads. `person_status` already carries that distinction, on the record.

## Assumptions and risks

Assumes a record with a proven entity and no decision-maker is worth counting — which is ADR-0028's
position, pre-registered, and is defensible precisely because the record says so on its face rather
than leaving a buyer to infer it. **The real risk is dilution:** the qualifying set can now grow
along an axis that carries no contact, and contact intelligence is the product's differentiator. The
mitigation is that the surfaces separate them — reachability tier, `person_status`, and the
practices file are all readable — and that `reconcile` reports the split every run, so the ratio is
visible rather than discovered at submission.

## What would change this

If entity-only records ever outnumber contact-bearing ones in the qualifying set, the honest
headline stops being a single count and becomes two ("N with a proven decision-maker, M entity-only
"), because at that point the average record is no longer actionable and one number would flatter
the set. If a decision-maker pass later ratifies contacts for these records, they upgrade in place
to `person_status='proven'` with no reclassification.
