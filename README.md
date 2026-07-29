# polarity-fo-rag

Family Office Dataset + Micro-RAG pipeline. PolarityIQ Differentiator.
Stage 1 passed; Bridge Mandate pre-window corrections complete (signed off 2026-07-22; see
`docs/BRIDGE_MANDATE_DISCLOSURE.md`). **Now inside the Stage 2 operating window**
(2026-07-27 → 2026-08-01): scaling to 500 records under scheduled, unattended operation —
plan and gates in [`docs/OPERATING_PLAN.md`](./docs/OPERATING_PLAN.md).

## What this is

An automated system that **discovers, enriches, and adjudicates** family office records, then serves
them through a production-shaped Retrieval-Augmented Generation (RAG) pipeline that answers
natural-language queries grounded in the dataset.

**What the gold layer held at the pre-window sign-off** (reconciled 2026-07-22; the Stage 2 climb
grows these numbers — `python -m pipeline.cli reconcile` regenerates the current counts from the
artifacts): of 50 SEC-discovered firms, **24 are affirmed multi-family offices** (entity proven
under ADR-0020 *and* decision-maker proven under ADR-0021 — these are the `qualifying` records); 18
are firms whose "family office" label was marketing, kept but labeled as wealth managers /
RIAs-with-an-FO-practice and **not** counted as family offices; 8 are quarantined (2 not a family
office, 6 unresolved). Every high-value cell carries its basis; a validation result that makes a
field unsafe changes what the product may release. No single-family offices appear — true SFOs are
exempt from SEC registration, so the SEC-derived method structurally cannot reach them.

Three things are true of every part of this repo:

1. **The dataset is the product.** The pipeline is the delivery mechanism. A great RAG on a thin or
   over-claimed dataset fails. Effort goes to the data first.
2. **Reasoning is visible.** Why each decision was made, what was observed vs assumed and believed vs
   verified, and what would change our mind, is recorded in [`adr/`](./adr/) and
   [`docs/findings/`](./docs/findings/) as we go, not reconstructed at the end.
3. **A check controls release.** When adjudication finds a record or field untrustworthy, that finding
   governs what ships: quarantined firms are unretrievable, vendor-rejected addresses are removed from
   operational fields, and a claim is never stronger than its evidence.

**Live system** (Render free tier — first request after idle cold-starts in ~30–60 s):

| surface | what it is |
|---|---|
| [`/`](https://polarity-fo-rag.onrender.com) | Coverage Desk — grounded natural-language Q&A over the dataset (Stage 1) |
| [`/agent`](https://polarity-fo-rag.onrender.com/agent) | the goal agent: give it a commercial goal, it plans, retrieves repeatedly, and returns a structured answer with per-pick confidence and explicit abstentions (Stage 2) |
| `POST /fit` | **`fit_rank`** — the Stage 2 retrieval extension: rank the whole qualifying set against an investor mandate with per-record evidence, caveats and an evidence-based confidence tier. Same function the agent calls as a tool |
| `GET /stats` | live release-state and per-category counts, regenerated from the database on every call — so no surface hand-carries a number |
| `GET /agent/tools` | the agent's tool schemas, served from the running code |

## The deliverables, and where they live

| Deliverable | Where |
|---|---|
| Gold dataset CSV (affirmed family offices) + auditable sidecars | [`family_office_dataset.csv`](./data/gold/family_office_dataset.csv), [`reclassified_firms.csv`](./data/gold/reclassified_firms.csv), [`quarantined.csv`](./data/gold/quarantined.csv) |
| Methodology summary | [`METHODOLOGY.md`](./METHODOLOGY.md) |
| Records with a full validation chain | [`docs/validation-chains.md`](./docs/validation-chains.md) |
| Measured principal-selection benchmark (proxy labels, FP/FN) | [`docs/findings/validation-layer.md`](./docs/findings/validation-layer.md) |
| Entity + decision-maker adjudication findings | [`docs/findings/entity-adjudication.md`](./docs/findings/entity-adjudication.md), [`decision-maker-evidence.md`](./docs/findings/decision-maker-evidence.md) |
| RAG documentation note | [`docs/rag-note.md`](./docs/rag-note.md) |
| Build session summary (Stage 1) | [`BUILD_SESSION_SUMMARY.md`](./BUILD_SESSION_SUMMARY.md) |
| Reasoning trail | [`adr/`](./adr/) (indexed in [`CLAUDE.md`](./CLAUDE.md)) + [`docs/findings/`](./docs/findings/) |

### Stage 2 deliverables

| Deliverable | Where |
|---|---|
| Architecture notes (7 sections) | [`docs/architecture-notes.md`](./docs/architecture-notes.md) |
| The three goals — framing, then artifacts | [`docs/three-goals.md`](./docs/three-goals.md) |
| Complete operating logs (uncurated) | `python -m pipeline.cli ops-export` → `runs`, `run_events`, `observations`, `trust_events`, `query_log`, `agent_messages` as JSONL |
| Day-2 checkpoint predictions (committed before sending) | [`docs/day2-checkpoint-predictions.md`](./docs/day2-checkpoint-predictions.md) |
| Operating plan, hard gates, window conditions | [`docs/OPERATING_PLAN.md`](./docs/OPERATING_PLAN.md) |
| Brief reconciliation + Stage 1 records under the Stage 2 standard | [`docs/findings/stage2-brief-reconciliation.md`](./docs/findings/stage2-brief-reconciliation.md), [`stage1-under-stage2-standard.md`](./docs/findings/stage1-under-stage2-standard.md) |

## Operating the system

```bash
python -m pipeline.cli operate --write        # one full cycle (what the scheduler runs)
python -m pipeline.cli reconcile              # assert every surface agrees; exit 0 = agree
python -m pipeline.cli ops-export             # dump the whole operating ledger to JSONL
python -m pipeline.cli agent-goal "<goal>"    # one agent session, traced to ops.agent_messages
python -m pipeline.cli discover-13f --write   # seed candidates from SEC 13F filers
```

The scheduler is GitHub Actions (`.github/workflows/operate.yml`), every ~6 hours, with a
concurrency group so cycles can never overlap. Its run history is the platform-kept record the
Stage 2 brief requires.

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
