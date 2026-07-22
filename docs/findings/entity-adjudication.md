# Finding: entity adjudication of the original 50 (WS2, ADR-0020)

**Date:** 2026-07-20 · **Method:** per-firm research (firm's own site + >=1 independent third
party + SEC ADV client mix), draft proposals machine-assembled, every decision ratified by the
human release control. Evidence spans + URLs in `data/curation/entity_adjudications.json`;
applied via `entity-apply --write`.

## The governing result

Of the 50 firms Stage 1 shipped as "family offices," **24 are affirmed genuine family offices.**
The other 26 are real firms that were mislabeled, unprovable, or not family offices at all. The
Stage 1 method — keyword-match the SEC adviser feed, exclude the obvious misses — could not tell
these apart, because it never asked the affirmative question.

| Outcome | Count | Ships in product? | Counts toward the 500? |
|---|---|---|---|
| Affirmed family office (all multi-family) | 24 | yes | **yes** |
| Reclassified: RIA with an FO practice | 7 | yes, labeled | no |
| Reclassified: wealth manager | 11 | yes, labeled | no |
| Quarantined: not a family office | 2 | no | no |
| Quarantined: entity unresolved | 6 | no | no |

## Three findings worth stating plainly

1. **Zero single-family offices — and that is structural, not a miss.** Every affirmed FO is a
   *multi*-family office. True single-family offices are generally exempt from SEC registration
   (the family-office rule), so a dataset sourced from the SEC adviser feed *cannot* contain them.
   This is direct evidence for the Bridge Mandate's point that SEC-alone discovery is insufficient,
   and it scopes the Stage 2 multi-source strategy: the SFO segment is reachable only off-registry.

2. **The FO label is frequently marketing.** 18 of 50 firms carry "Family Office" in their name or
   copy but are, on the evidence, wealth managers (Tarbox: 100+ client families as a business;
   Compound Planning: 11,500 clients, a "digital family office"; Chilton: "single-family office
   *feel*" as a simile) or broad RIAs with an FO service line (1919, Sapient, Summit Trail). They
   are kept, labeled by category, and excluded from any "family office" claim — honest adjacent
   inventory, not filler dressed as FOs.

3. **Two wrong-entity data defects surfaced** (same class as the Stage 1 SpiderRock->blackrock
   case): Arrowroot's domain on file is a separate M&A investment bank; Class VI's is its affiliated
   investment bank, not the family office. Their website-derived cells may describe the wrong
   company. Arrowroot reclassifies to wealth manager regardless; **Class VI is an affirmed MFO whose
   enrichment must be re-sourced in WS3** before its contact cells can be trusted.

## What controls release now

`gold.entity_adjudications` holds all 50 decisions with evidence. `build.py::_release` folds them
into `release_state`: rejected + unresolved-entity => `quarantined` (dropped from the product CSV
into `quarantined.csv`, unretrievable on every RAG path — verified: Callan/Clearbrook/Taylor Frigon
return no hits); affirmed => ships, labeled by `entity_category`, `release_state='unresolved'`
pending the ADR-0021 person pass (WS3). No firm is yet certified `qualifying` — that requires the
person evidence pass.

## Honest limits of this pass

- **Two directory sources are not fully independent.** Where a firm was affirmed partly on directory
  listings (Preqin, Altss, fintrx), those aggregators sometimes copy each other. Pine Ridge is the
  weakest case (first-party site cookie-gated; affirmed on Preqin + an all-HNW regulatory book) and
  its rationale says so.
- **The 6 unresolved are quarantined, not judged non-FO.** Several (Capitol under construction,
  Elyseum a foreign affiliate, Taylor Frigon a 0-client shell) may be genuine FOs recoverable with
  deeper Stage 2 digging. Quarantine is "not proven," not "disproven."
- **Reclassification boundaries are judgment calls.** The RIA-with-FO-practice vs wealth-manager
  line (e.g. Alpha Capital, Innovative) rests on client-mix + self-description; each carries its
  evidence so the call is inspectable and arguable.
