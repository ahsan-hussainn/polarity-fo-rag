-- 0003_silver.sql
-- Silver: normalized, entity-resolved, VALIDATED records (ADR-0006, ADR-0009). Bronze is one
-- append-only row per fetched PAGE; silver resolves those pages to one row per FIRM (silver.firms)
-- and one row per PERSON (silver.people). The person row is the grade-able contact unit -- it is
-- where the validation layer (email -> verification -> quality grade) will attach.
--
-- Verifiability-first (ADR-0003): believed facts (email, principal call) live in plain columns;
-- VERIFIED facts (SMTP result, final grade) live in their own columns and are NULL until the
-- validation layer fills them. A NULL here is an honest "not yet verified", never a guess.

-- One resolved firm. Multiple bronze 'website' captures (home/team/about/...) collapse to one row.
create table if not exists silver.firms (
    id             bigint generated always as identity primary key,
    crd            text        not null,               -- entity key: SEC CRD number (from bronze.entity_key)
    firm_name      text,
    domain         text,                                -- registered domain (for email inference join)
    -- extracted facts (believed; each traces to source_urls/bronze_ids below)
    thesis         text,                                -- investment strategy, one sentence; null if unstated
    description    text,                                -- 1-2 sentence firm overview; null if absent
    sectors        text[]      not null default '{}',   -- de-duplicated asset classes / industries
    founded_year   int,                                 -- 4-digit year only if stated
    -- lineage / provenance (every silver cell traces back to raw bronze -- ADR-0003, ADR-0006)
    source_urls    text[]      not null default '{}',   -- the exact pages this firm was extracted from
    bronze_ids     bigint[]    not null default '{}',   -- the exact bronze.captures rows consumed
    extracted_by   text,                                -- 'openai:gpt-4o-mini' | 'mock:heuristic'
    extraction_usage jsonb,                             -- token/cost bookkeeping from the extractor
    extracted_at   timestamptz not null default now()
);
create unique index if not exists firms_crd_idx      on silver.firms (crd);
create index        if not exists firms_domain_idx   on silver.firms (domain);
create index        if not exists firms_sectors_idx  on silver.firms using gin (sectors);

-- One named person on a firm's site. The contact record the validation layer grades.
create table if not exists silver.people (
    id               bigint generated always as identity primary key,
    firm_crd         text        not null references silver.firms (crd) on delete cascade,
    name             text        not null,
    title            text,
    -- the high-value judgment (where we beat FO-MAX). Believed, and auditable via the reason.
    is_principal     boolean     not null,
    principal_reason text,                              -- why classified this way -- not a black box
    -- CONTACT INTELLIGENCE. Believed vs verified are separated on purpose (ADR-0003, ADR-0005):
    email            text,                              -- inferred/found address (BELIEVED)
    email_pattern    text,                              -- how it was inferred, e.g. 'first.last@domain'
    email_status     text,                              -- VERIFIED: null|'valid'|'catch_all'|'undeliverable'|'unknown'
    email_verification jsonb,                           -- VERIFIED: raw SMTP/MX probe evidence
    quality_grade    text,                              -- final honest grade (validation layer output)
    -- lineage
    source_url       text,                              -- the page this person was extracted from
    extracted_by     text,
    extracted_at     timestamptz not null default now()
);
create index if not exists people_firm_idx      on silver.people (firm_crd);
create index if not exists people_principal_idx on silver.people (is_principal);

comment on table silver.firms  is 'Entity-resolved firms (one row per CRD) with extracted facts + full bronze lineage (ADR-0009).';
comment on table silver.people is 'Per-person contact records; the grade-able unit for the validation layer. email_status/email_verification/quality_grade are NULL until verified (ADR-0003, ADR-0005).';
