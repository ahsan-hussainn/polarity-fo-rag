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

## Layout

| Path | What it holds |
|---|---|
| `adr/` | Architecture Decision Records. The "why this over that" trail. Start here to understand choices. |
| `.claude/commands/` | Claude Code slash commands (e.g. `/adr` to scaffold a new decision record). |
| `CLAUDE.md` | Project context loaded each session: constraints, schema, stack, ADR index. |

## Status

Scaffolding. Pipeline and RAG not yet built. See `adr/` for decisions made so far.
