-- 0002_bronze.sql
-- Bronze: one append-only row per fetch (ADR-0006). This is the provenance backbone --
-- every downstream silver/gold cell can trace back to the exact raw capture it came from.

create table if not exists bronze.captures (
    id            bigint generated always as identity primary key,
    source        text        not null,               -- 'sec_adv' | 'smtp_probe' | ...
    source_url    text,                                -- where it came from (provenance)
    entity_key    text,                                -- natural key when known (CRD #, email domain)
    fetched_at    timestamptz,                         -- when the source produced it (if known)
    raw           jsonb       not null,                -- the raw record, verbatim
    content_hash  text        not null,                -- sha256(source|raw), for dedupe + immutability audit
    ingested_at   timestamptz not null default now()   -- when it landed in bronze
);

-- Same raw capture from the same source should not be stored twice.
create unique index if not exists captures_dedupe_idx    on bronze.captures (source, content_hash);
create index        if not exists captures_source_idx    on bronze.captures (source);
create index        if not exists captures_entity_idx    on bronze.captures (entity_key);
create index        if not exists captures_raw_gin_idx   on bronze.captures using gin (raw);

comment on table bronze.captures is 'Append-only raw captures (ADR-0006). Never updated; corrections land as new rows.';
