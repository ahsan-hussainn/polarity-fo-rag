-- 0004_gold.sql
-- Gold: decision-grade, FO-MAX-shaped records (ADR-0006, ADR-0011). One row per family office, with
-- the firm's facts, a PRIMARY and SECONDARY contact chosen from its principals by seniority, each
-- carrying the honest email chain (email -> validation code -> explanation -> quality grade), and a
-- per-record data-completion score. This is the shape a capital allocator consumes; silver is the
-- normalized workbench, gold is the product.

create table if not exists gold.records (
    crd                  text primary key,
    family_office_name   text,
    domain               text,
    website              text,
    description          text,
    investment_thesis    text,
    investing_sectors    text[]  not null default '{}',
    founded_year         int,
    city                 text,
    state                text,
    country              text,
    -- PRIMARY contact: the best-targeted principal (seniority-ranked). Where we beat FO-MAX, whose
    -- Walton contact is an Accounting Manager -- here the primary is a founder/CEO/CIO by construction.
    primary_contact_name        text,
    primary_contact_title       text,
    primary_contact_email       text,
    primary_email_grade         text,   -- quality assessment: A/B/C/D/F
    primary_email_code          text,   -- validation code: VERIFIED_API / INFERRED_CATCHALL / ...
    primary_email_explanation   text,   -- plain-English, from the verifier
    -- SECONDARY contact: next-ranked principal (FO-MAX carries a secondary too).
    secondary_contact_name      text,
    secondary_contact_title     text,
    secondary_contact_email     text,
    secondary_email_grade       text,
    secondary_email_code        text,
    secondary_email_explanation text,
    -- quality signals
    data_completion_score int,          -- 0-100: share of key cells populated
    principal_count       int,          -- how many principals the firm lists (targeting breadth)
    people_count          int,          -- total named people (over-inclusion denominator)
    -- provenance
    extracted_by  text,
    generated_at  timestamptz not null default now()
);
create index if not exists gold_domain_idx  on gold.records (domain);
create index if not exists gold_sectors_idx on gold.records using gin (investing_sectors);

comment on table gold.records is 'Decision-grade FO records (ADR-0011): firm facts + seniority-ranked primary/secondary principal contacts + honest email grade + completion score. The product view.';
