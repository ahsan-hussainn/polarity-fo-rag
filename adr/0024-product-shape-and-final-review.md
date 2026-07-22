# ADR-0024: Product shape (family offices only) + final-review release decisions

- **Date:** 2026-07-22
- **Status:** Accepted (amends ADR-0019, ADR-0020)

## Context

WS6 (the human release review) and the reconciliation pass surfaced two things the earlier decisions
left inconsistent. **Observed:** (1) ADR-0020 kept reclassified non-FOs (wealth managers / RIAs) in
the product file, labeled — but this is a *family-office* product, and a non-FO in the FO file, even
labeled, is adjacent to "presenting a non-FO as a family office" (the exact line the mandate polices);
it also carried unproven Stage-1 title-ladder contacts and stale D/F grades. (2) 12 grade-C primary
emails were uniform `first.last@` guesses the vendor could neither confirm nor reject — a column of
look-alikes reads more confident than the "unconfirmed" label admits. Both were ratified by the human
review, so this ADR records the revised decisions and the enforcement that keeps the surfaces honest.

## Decision

The product is **the 24 affirmed family offices only** (`family_office_dataset.csv`). The other 26 of
the 50 move to auditable sidecars: `reclassified_firms.csv` (18 wealth managers / RIAs, **firm-level
only** — no contact fields, since their decision-makers were never proven to the ADR-0021 standard,
with category + basis) and `quarantined.csv` (8 not-FO + unresolved). Every one of the 50 lands in
exactly one file. The RAG retrieval gate tightens to `release_state = 'qualifying'` — a non-FO is
never retrievable at all (stronger than post-hoc labeling). **C-grade (unknown) inferred emails are
withheld**, not shipped: only firm-published (PUB) and vendor-deliverable/plausible (A/B) addresses
ship. `pipeline/reconcile.py` asserts the three files partition the 50 and that every surface agrees
(15 checks), run as the substrate for the human review.

## Options considered

- **Option A (chosen):** FOs-only product + firm-level reclassified sidecar + C withheld.
- **Option B:** keep the 42-row product with non-FOs labeled (the original ADR-0020 policy). Rejected
  on the corrected count logic: the goal is 500 *qualifying* FOs, so a non-FO is not product inventory
  — labeling it inside the FO file still mixes the count and keeps the unproven-contact problem.
- **Option C:** run the ADR-0021 person pass on the 18 non-FOs too, then keep them in-product.
  Rejected: they are not the product's target and don't count toward the 500; proving ~18 non-FO
  decision-makers is effort spent off the family-office goal.
- **Option D:** keep C-grade guesses with the label (the pre-registered policy). Rejected at review:
  honest labeling does not fully offset a column of look-alike addresses; withholding is the
  conservative, more trustworthy call (reachability down, trust up).

## Why this over the others

"Family-office dataset" should mean family offices. Sorting each of the 50 into what-it-actually-is
(FO / reclassified / quarantined) is the honest version of "50 examined → 24 are family offices," and
it removes the two defects the review found in one move. Withholding unconfirmable guesses matches the
mandate's rule that a claim must never read stronger than its evidence.

## Assumptions and risks

Assumes the reclassified firms have no product value as family offices — true for the FO buyer, though
they remain auditable. Withholding C emails lowers raw reachability (15 of 24 FOs now route to phone /
LinkedIn); accepted as the honest tradeoff and disclosed. The count is now 24, not 50 — defensible
because the mandate forbids padding and targets 500 *qualifying* entities in Stage 2, of which these
24 are the validated seed.

## What would change this

The official Stage 2 brief defining a multi-segment product (which could bring the reclassified firms
back as their own segment); a re-verification pass converting withheld C guesses into vendor-
deliverable (A) addresses (they would then ship); a decision to prove the non-FO decision-makers if
those firms become a supported product line.
