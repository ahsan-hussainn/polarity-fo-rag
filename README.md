# polarity-fo-rag

Family Office Dataset + Micro-RAG pipeline. PolarityIQ Differentiator, Stage 1, Task 1.

## What this is

An automated system that **discovers, enriches, and validates** real family office records,
then serves them through a production-shaped Retrieval-Augmented Generation (RAG) pipeline that
answers natural-language queries grounded in the dataset.

Two things are true of every part of this repo:

1. **The dataset is the product.** The pipeline is the delivery mechanism. A great RAG on a thin,
   unverified dataset fails. Effort goes to the data first.
2. **Reasoning is visible.** Why each decision was made, what was assumed vs verified, and what would
   change our mind, is recorded in [`adr/`](./adr/) as we go, not reconstructed at the end.

**Live demo:** https://polarity-fo-rag.onrender.com (Render free tier — first request after idle
cold-starts in ~30–60 s).

## The deliverables, and where they live

| Deliverable | Where |
|---|---|
| 50 validated family-office records (CSV) | [`data/gold/family_office_dataset.csv`](./data/gold/family_office_dataset.csv) |
| Methodology summary | [`METHODOLOGY.md`](./METHODOLOGY.md) |
| 3 records with full validation chains | [`docs/validation-chains.md`](./docs/validation-chains.md) |
| Measured validation results (FP/FN, email grades) | [`docs/findings/validation-layer.md`](./docs/findings/validation-layer.md) |
| RAG documentation note | [`docs/rag-note.md`](./docs/rag-note.md) |
| Build session summary | [`BUILD_SESSION_SUMMARY.md`](./BUILD_SESSION_SUMMARY.md) |
| Reasoning trail | [`adr/`](./adr/) (15 ADRs) + [`docs/findings/`](./docs/findings/) |

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
