# polarity-fo-rag

Family Office Dataset + Micro-RAG pipeline. PolarityIQ Differentiator.
Stage 1 passed; currently in the **pre-window Bridge Mandate correction phase** (see
`docs/findings/bridge-audit-reconciliation.md` and ADRs 0019–0022).

## What this is

An automated system that **discovers, enriches, and adjudicates** family office records, then serves
them through a production-shaped Retrieval-Augmented Generation (RAG) pipeline that answers
natural-language queries grounded in the dataset.

**What the current gold layer holds** (reconciled against `data/gold/family_office_dataset.csv`,
2026-07-20): of 50 SEC-discovered firms, **24 are affirmed multi-family offices** (entity proven
under ADR-0020 *and* decision-maker proven under ADR-0021 — these are the `qualifying` records); 18
are firms whose "family office" label was marketing, kept but labeled as wealth managers /
RIAs-with-an-FO-practice and **not** counted as family offices; 8 are quarantined (2 not a family
office, 6 unresolved). Every high-value cell carries its basis; a validation result that makes a
field unsafe changes what the product may release. No single-family offices appear — true SFOs are
exempt from SEC registration, so the SEC-derived method structurally cannot reach them.

Two things are true of every part of this repo:

1. **The dataset is the product.** The pipeline is the delivery mechanism. A great RAG on a thin or
   over-claimed dataset fails. Effort goes to the data first.
2. **Reasoning is visible.** Why each decision was made, what was observed vs assumed and believed vs
   verified, and what would change our mind, is recorded in [`adr/`](./adr/) and
   [`docs/findings/`](./docs/findings/) as we go, not reconstructed at the end.
3. **A check controls release.** When adjudication finds a record or field untrustworthy, that finding
   governs what ships: quarantined firms are unretrievable, vendor-rejected addresses are removed from
   operational fields, and a claim is never stronger than its evidence.

**Live demo:** https://polarity-fo-rag.onrender.com (Render free tier — first request after idle
cold-starts in ~30–60 s).

## The deliverables, and where they live

| Deliverable | Where |
|---|---|
| Gold dataset CSV (24 affirmed family offices) + auditable sidecars | [`family_office_dataset.csv`](./data/gold/family_office_dataset.csv), [`reclassified_firms.csv`](./data/gold/reclassified_firms.csv), [`quarantined.csv`](./data/gold/quarantined.csv) |
| Methodology summary | [`METHODOLOGY.md`](./METHODOLOGY.md) |
| Records with a full validation chain | [`docs/validation-chains.md`](./docs/validation-chains.md) |
| Measured principal-selection benchmark (proxy labels, FP/FN) | [`docs/findings/validation-layer.md`](./docs/findings/validation-layer.md) |
| Entity + decision-maker adjudication findings | [`docs/findings/entity-adjudication.md`](./docs/findings/entity-adjudication.md), [`decision-maker-evidence.md`](./docs/findings/decision-maker-evidence.md) |
| RAG documentation note | [`docs/rag-note.md`](./docs/rag-note.md) |
| Build session summary (Stage 1) | [`BUILD_SESSION_SUMMARY.md`](./BUILD_SESSION_SUMMARY.md) |
| Reasoning trail | [`adr/`](./adr/) (22 ADRs) + [`docs/findings/`](./docs/findings/) |

## Layout

| Path | What it holds |
|---|---|
| `pipeline/` | The system: `bronze/` discovery+fetch, `silver/` extraction+validation, `gold/` product build, `verify/` email verification, `rag/` retrieval+serving, `eval.py` ground-truth measurement. |
| `db/migrations/` | Postgres schema (medallion: bronze/silver/gold + RAG index). |
| `adr/` | Architecture Decision Records. The "why this over that" trail. Start here to understand choices. |
| `docs/findings/` | Measured results and belief updates per pipeline stage. |
| `CLAUDE.md` | Project context loaded each session: constraints, schema, stack, ADR index. |

## Run it

```
pip install -r requirements.txt          # then set DATABASE_URL + OPENAI_API_KEY (see .env.example)
python -m pipeline.cli db-migrate        # schema
python -m pipeline.cli discover-adv      # Stage 1: SEC ADV -> candidates
python -m pipeline.cli fetch-websites --write
python -m pipeline.cli build-silver --write
python -m pipeline.cli validate-emails --write --verifier millionverifier
python -m pipeline.cli build-gold --write && python -m pipeline.cli gold-export
python -m pipeline.cli rag-index --write
uvicorn pipeline.rag.app:app             # or use the live URL above
```
