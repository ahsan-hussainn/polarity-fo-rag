-- 0009_entity_adjudication.sql
-- Affirmative entity standard (ADR-0020, Bridge Mandate correction #2). Stage 1's entity logic was
-- negative (discovered + not manually excluded => shipped as a family office). This table holds the
-- affirmative judgment per firm: what the entity IS, with the evidence that proves it (>=2
-- independent classes), or an honest 'unresolved'. It persists across gold rebuilds -- the
-- adjudication is a curation decision, not derived data -- and build.py stamps its outcome onto
-- gold.records and folds it into release_state (unresolved/rejected/duplicate => not qualifying).

create table if not exists gold.entity_adjudications (
    crd          text primary key,
    firm_name    text,
    category     text check (category in ('single_family_office', 'multi_family_office',
                                          'ria_with_fo_practice', 'wealth_manager',
                                          'not_fo', 'unresolved')),
    status       text not null check (status in ('affirmed', 'unresolved', 'rejected')),
    duplicate_of text,                  -- CRD of the surviving record when this one is an affiliate/dup
    evidence     jsonb not null default '[]',  -- [{class, source_url, observed_at, detail}] >=2 classes to affirm
    rationale    text not null,         -- the judgment in plain words
    decided_by   text not null,         -- who ratified (human release control, per the mandate)
    decided_at   timestamptz not null default now()
);

alter table gold.records add column if not exists entity_category text;
alter table gold.records add column if not exists entity_status   text;

comment on table gold.entity_adjudications is
  'ADR-0020: per-firm affirmative entity judgment with evidence. Curation decision, survives rebuilds; build.py enforces it in release_state.';
