-- 0010_person_evidence.sql
-- Decision-maker evidence standard (ADR-0021) + contact selection by allocation authority (ADR-0022).
-- Stage 1 chose contacts by a title-prestige ladder and graded mailboxes, not people. This adds the
-- affirmative person layer: per presented contact, evidence on four axes (identity, current
-- affiliation, investment authority, email->person link), the selection rationale, and whether the
-- authority is stated or only title-inferred. build.py reads the ratified adjudication to overwrite
-- the product's primary/secondary contact and to gate final qualification.

create table if not exists gold.contact_adjudications (
    crd               text not null,
    contact_role      text not null check (contact_role in ('primary', 'secondary')),
    name              text,
    title             text,
    -- ADR-0022: why THIS person is the pitch contact (e.g. 'named CIO, Schedule A officer').
    selection_basis   text,
    -- ADR-0021: 'stated' = a source describes investment/allocation authority; 'title_inferred' =
    -- authority assumed from a senior title only (must be labeled as such to the customer).
    authority_basis   text check (authority_basis in ('stated', 'title_inferred')),
    -- dated affiliation evidence: the person is at the firm as of this date/source (staleness input).
    affiliation_asof  text,
    -- the ONLY thing that proves the mailbox belongs to the person: a published address. NULL means
    -- any address we hold is an inferred pattern, never presented as the person's confirmed email.
    published_email   text,
    evidence          jsonb not null default '[]',  -- [{axis, source_url, observed}] per the four axes
    decided_by        text not null,                -- human release control (ADR-0021)
    decided_at        timestamptz not null default now(),
    primary key (crd, contact_role)
);

-- Per-firm person outcome. 'proven' = >=1 contact affirmatively passes the standard; 'none_proven' =
-- no qualified decision-maker could be shown (record says so plainly and ranks bottom-of-queue,
-- ADR-0019 policy), rather than promoting a guess.
alter table gold.records add column if not exists person_status         text;
alter table gold.records add column if not exists primary_authority_basis text;
alter table gold.records add column if not exists primary_selection_basis text;

comment on table gold.contact_adjudications is
  'ADR-0021/0022: per-contact person evidence (four axes) + selection rationale, ratified by the human release control. build.py enforces it on the product contact and on qualification.';
