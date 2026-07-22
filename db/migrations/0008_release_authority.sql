-- 0008_release_authority.sql
-- Release authority (ADR-0019, Bridge Mandate correction #1). Stage 1 graded contacts honestly and
-- then released vendor-rejected addresses anyway: 28 D-grade emails shipped in operational fields.
-- This migration gives a validation verdict authority over release:
--  1. gold.contact_audit -- the audit history the mandate permits: rejected values live HERE,
--     clearly separated from usable fields, with when/why they were quarantined.
--  2. gold.records.release_state -- every record carries its release decision. 'quarantined' records
--     are never retrievable; 'unresolved' means adjudication (ADR-0020/0021) has not yet run.
-- Boundary: silver keeps full verification evidence (it is the internal workbench); gold + CSV + RAG
-- are the product surfaces, and rejected values must not be operational on any of them.

create table if not exists gold.contact_audit (
    id             bigserial primary key,
    crd            text not null,
    contact_role   text not null check (contact_role in ('primary', 'secondary')),
    contact_name   text,
    email          text not null,      -- the rejected address removed from the operational field
    grade          text not null,      -- vendor grade at quarantine time (D/F)
    code           text not null,      -- INVALID_API / INVALID_NO_MX
    explanation    text,               -- the vendor's plain-English verdict
    reason         text not null,      -- why release policy quarantined it
    quarantined_at timestamptz not null default now()
);
create unique index if not exists contact_audit_uniq
    on gold.contact_audit (crd, contact_role, email);   -- rebuilds are idempotent, not duplicating
create index if not exists contact_audit_crd_idx on gold.contact_audit (crd);

-- Release decision per record. Default 'unresolved': no record is presumed qualifying -- it must
-- pass the entity (ADR-0020) and person (ADR-0021) standards to earn 'qualifying'.
alter table gold.records add column if not exists release_state   text not null default 'unresolved'
    check (release_state in ('qualifying', 'unresolved', 'quarantined'));
alter table gold.records add column if not exists release_reasons text[] not null default '{}';

comment on table gold.contact_audit is
  'ADR-0019 quarantine: vendor-rejected contact values removed from operational fields. Audit history, never joined into product surfaces.';
comment on column gold.records.release_state is
  'ADR-0019: qualifying (passed release standards) | unresolved (adjudication pending; not presented as proven) | quarantined (not released, not counted, not retrievable).';
