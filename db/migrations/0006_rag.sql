-- 0006_rag.sql
-- Retrieval index over the gold dataset (ADR-0013). One document per firm = the decision-grade record
-- rendered to searchable prose. Hybrid retrieval needs both halves in one place: a dense `embedding`
-- (semantic, pgvector) and a `tsv` (lexical, Postgres full-text). Keeping both on the same row lets a
-- single query fuse them. Embedding dim 1536 = OpenAI text-embedding-3-small.

create table if not exists gold.rag_docs (
    crd        text primary key references gold.records (crd) on delete cascade,
    content    text not null,                       -- the firm rendered to prose (what we embed + index)
    embedding  vector(1536),                        -- dense semantic vector
    tsv        tsvector generated always as (to_tsvector('english', content)) stored,
    updated_at timestamptz not null default now()
);

create index if not exists rag_docs_tsv_idx on gold.rag_docs using gin (tsv);
-- 59 rows: a flat/seq scan on the vector is exact and instant, so no ANN index is needed yet. Add an
-- hnsw index here if the corpus grows to thousands.

comment on table gold.rag_docs is 'Hybrid retrieval index over gold (ADR-0013): dense embedding + lexical tsvector per firm.';
