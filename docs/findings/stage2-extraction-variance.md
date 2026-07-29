# Finding: the staleness detector was reporting model variance as world change

**Measured 2026-07-28, day 2 of the operating window, over runs 2–14 of `ops.trust_events`.**

## What was observed

Four firms — CRD 133370, 142856, 159306, 329496 — fired `website_change` on nearly every scheduled
cycle since run 2, most of them with action `refreshed`, meaning the cycle rewrote silver and
rebuilt gold each time. Twenty-six of the 42 `website_change` events in the ledger are these four
firms. The evidence strings name the fields that moved:

```
159306 run 6:  sectors ['Equity','Fixed Income','Hedge Funds'] -> ['Equity','Fixed Income','External Managers']
159306 run 14: home-page text changed since run 8; extracted facts identical
329496 run 6:  sectors ['Estate, Trusts & Philanthropy'] -> ['Estate Planning','Philanthropy']
329496 run 8:  sectors ['Asset Protection & Risk Management'] -> ['Asset Protection','Risk Management']
142856 run 8:  title changed for yuli petreikov: 'Senior ...' -> ...
```

The values alternate between two forms and back again across consecutive cycles. Websites do not
oscillate on a six-hour period. Extraction does.

## Diagnosis

The day-1 materiality classifier already split *prose* (thesis, description) from *fact-shaped*
fields, on the measured grounds that the LLM paraphrases prose differently every run. That fix was
correct and held: 133370 and 159306 now land as `noted` on wording alone.

Its next assumption did not hold. The module asserted in its own docstring that "fact-shaped fields
are stable under re-extraction." Sector labels and job titles are not facts in this sense — they
are LLM-authored free text that happens to sit in a list. `Estate, Trusts & Philanthropy` and
`Estate Planning; Philanthropy` are the same page read twice.

The consequence is worse than churn. Window-completion condition 3 asks for a cross-run,
evidence-based staleness event. A ledger where the staleness detector fires constantly on its own
model noise cannot support that claim: a real event would be indistinguishable from the 26 that
were not real. The detector was measuring itself.

## The fix (two mechanisms, both in `pipeline/ops/materiality.py`)

1. **Normalized comparison.** Sectors compare as a normalized token set (case, punctuation,
   ordering, and `,;/&`/"and" splitting removed); titles normalize case, punctuation, and common
   abbreviations (`Sr.`→senior, `VP`→vice president). Replaying the four recorded pairs above, this
   alone collapses two of them to "no change."

2. **Corroboration before belief.** A fact delta moves silver only on its **second consecutive
   identical sighting**. The reasoning: a site change is a claim about the world, extraction
   variance is a claim about the model, and the two separate on one property — a real change
   reproduces, variance does not. First sightings are recorded as `noted` with the delta named and
   labelled "not yet reproduced," never as `refreshed`.

   Each field confirms independently (a flapping sector list no longer blocks a real roster
   change). The per-cycle normalized fact surface is persisted as an `ops.observations` row of kind
   `fact_fingerprint`, so the comparison is itself auditable.

`decision_maker_gone` is now gated on the roster delta being confirmed. Telling a reviewer that
their ratified contact has vanished, on evidence that turns out to be one flaky extraction, spends
the scarcest resource in the system.

## Replay against the recorded pattern

Feeding 159306's actual alternating sequence through the new comparison:

| cycle | extracted sectors | outcome |
|---|---|---|
| 1 | …External Managers | delta seen once → `noted`, silver untouched |
| 2 | …Hedge Funds (flaps back) | no delta → cosmetic |
| 3 | …External Managers | delta seen once → `noted`, silver untouched |
| 4 | …External Managers (repeat) | **confirmed → material**, silver refreshed |

A genuine persistent change lands on its second cycle. A value that alternates never lands.

## Cost and residual risk

- **Cost:** a real site change is believed one cycle (~6h) later than before. Stated plainly
  because it is a real trade, not a free win.
- **Residual:** a model that produces the wrong value ~50% of the time will occasionally emit it
  twice in a row and confirm a false delta. Corroboration lowers the rate; it does not zero it.
  The honest bound is "two independent extractions agreed," and that is what the trust event now
  says — not "the site changed."
- **First cycle after deploy** confirms nothing (no prior fingerprint exists), so the detector is
  deliberately quiet for one cycle and returns to normal on the next.

## What would change this

If a firm's fingerprint never stabilizes across many cycles, the honest reading is that the page is
machine-generated per request and the record's site-derived cells cannot be kept current by this
mechanism at all. That firm should be labelled as such on the record rather than silently
re-extracted forever. No firm has yet shown that pattern over 14 runs; if one does, it is a record
label, not a detector tweak.

---

## Update, run 22: the predicted residual fired, and reproduction alone was not enough

The residual named above — "a model that produces the wrong value ~50% of the time will
occasionally emit it twice in a row and confirm a false delta" — occurred within a day, on the same
firm.

CRD 329496's fact fingerprints across runs 15, 17, 20 and 22 hold exactly **two** distinct sector
sets: one of ten items, and the same list with `Asset Protection & Risk Management` dropped. Set A
appeared at run 15, was displaced by set B at run 17, and returned at runs 20 and 22. Because 20
and 22 agreed, the delta confirmed, the trust event said "site facts changed", and silver was
rewritten. Nothing on the site had changed; the extractor is intermittently dropping one sector
from a ten-item list.

**Why reproduction could not see it.** Holding only the previous observation, a value that returned
and a value that repeated are the same observation. `A, B, A, A` and `X, X, Y, Y` have identical
last-two elements and opposite meanings. The sequence distinguishes them; the last element cannot.

**The rule now.** A delta is OSCILLATING when its value appeared earlier in the observation window
and was subsequently displaced by a different value — regardless of how many times it has repeated
since. `A, B, A, A` stays oscillating on its fourth observation, because a model alternating between
two forms does not become truthful by repeating itself. Silver is not rewritten, and the trust event
says the record's site-derived cells cannot be kept current by re-extraction alone, which is more
useful to a reader than a fifth "site facts changed".

A first-time value still confirms on its repeat: `X, X, X, Y, Y` reaches material at the second `Y`.
Verified by replaying 329496's actual recorded sequence (never confirms) and a synthetic genuine
change (confirms on the repeat).

**Not corrected:** run 22's false refresh already rewrote 329496's silver sectors before this
landed. It is left in place. Reverting would mean hand-editing a record row, which the operating
discipline forbids, and the two sets describe the same page — the defect was the *claim* that the
site changed, not the values themselves. Subsequent cycles will not re-flap it.

**What this says about the detector's limits.** Three iterations, each driven by production
evidence: prose is variance (day 1), fact-shaped fields are variance too (day 2 morning), and
reproduction does not separate variance from change (day 2 evening). The honest current claim is
narrow: the detector reports a change when two independent extractions agree on a value that has
never previously been displaced. That is weaker than "the site changed" and is what the trust events
now say.
