-- 0007_curation_and_provenance.sql
-- Curation gate + per-cell provenance (ADR-0015). Two fixes the pre-submission review surfaced:
--  1. gold carried records whose entity is NOT a family office (institutional managers matched via
--     ADV free-text) or whose ADV WebAddr points at a different company. Excluded firms are recorded
--     with reasons in gold.excluded_firms -- an auditable judgment, not a silent deletion.
--  2. High-value cells must carry their basis (the brief's verification test). The data already
--     existed in bronze/silver; these columns surface it in the product view: AUM + phone (SEC ADV),
--     and the source URLs firm facts and website-derived cells trace back to.

alter table gold.records add column if not exists aum_usd            bigint;  -- SEC ADV Item 5.F RAUM
alter table gold.records add column if not exists firm_phone         text;    -- SEC ADV MainAddr phone
alter table gold.records add column if not exists adv_filing_url     text;    -- basis: ADV-sourced cells
alter table gold.records add column if not exists profile_source_url text;    -- basis: website-derived cells

create table if not exists gold.excluded_firms (
    crd        text primary key,
    firm_name  text,
    reason     text not null,       -- why this entity does not belong in a family-office dataset
    decided_at timestamptz not null default now()
);

comment on table gold.excluded_firms is
  'Curation gate (ADR-0015): firms discovery surfaced but validation rejected as not-a-family-office or wrong-entity data. Kept as an auditable record of the judgment.';
