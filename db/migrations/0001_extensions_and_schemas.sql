-- 0001_extensions_and_schemas.sql
-- Hybrid-retrieval extensions (ADR-0002) + medallion layout (ADR-0006). Idempotent; safe to re-run.

-- pgvector: semantic similarity for the RAG retrieval layer (ADR-0002).
create extension if not exists vector;

-- pg_trgm: fuzzy name matching for entity resolution / dedup when promoting bronze -> silver.
create extension if not exists pg_trgm;

-- Medallion schemas (ADR-0006). tsvector (lexical/full-text) is built into Postgres; no extension needed.
create schema if not exists bronze;   -- raw, immutable captures (the provenance backbone)
create schema if not exists silver;   -- normalized, entity-resolved, VALIDATED records (the validation layer)
create schema if not exists gold;     -- curated records that clear the bar, served to the RAG

comment on schema bronze is 'Raw immutable source captures. Append-only, one row per fetch (ADR-0006).';
comment on schema silver is 'Normalized + validated records with per-cell source/verification. The validation layer.';
comment on schema gold  is 'Curated decision-grade records served to the RAG.';
