-- 0017: automated inclusion gate + identity crosswalk + candidate queue (Stage 2, ADR-0029).
--
-- ADR-0028 defines WHAT counts toward the 500 (three labeled categories); this is the machinery
-- that decides it at scale: deterministic gate decisions with every evidence point listed
-- (append-only history -- the latest row per entity is the standing decision), an identity
-- crosswalk so one real-world entity discovered through different registries counts exactly once,
-- and a work queue so discovery advances across scheduled cycles with claimable, resumable stages
-- (an interrupted run resumes; it never duplicates work -- architecture-note 4 in table form).

create table if not exists gold.entity_gate (
    id             bigint generated always as identity primary key,
    entity_key     text not null,        -- 'crd:<n>' for SEC/state registrants; plain digits = legacy CRD; 'cik:<n>'; 'ein:<n>'
    gate_version   text not null,        -- pre-registered rules version that produced this decision
    decision       text not null check (decision in ('affirm', 'needs_evidence', 'exclude')),
    category       text check (category in ('single_family_office', 'multi_family_office',
                                            'embedded_fo_practice')),
    score          int  not null,
    evidence       jsonb not null,       -- [{rule, points, detail}] -- every point traceable
    contradictions jsonb not null default '[]',
    run_id         bigint references ops.runs (run_id),
    decided_at     timestamptz not null default now()
);
create index if not exists entity_gate_key_idx on gold.entity_gate (entity_key, decided_at desc);

create table if not exists gold.identity_links (
    canonical_key text not null,
    alias_key     text not null,
    method        text not null,         -- 'same_crd' | 'name_state' | 'domain' | 'human'
    evidence      text not null,
    created_at    timestamptz not null default now(),
    primary key (canonical_key, alias_key)
);

create table if not exists ops.candidate_queue (
    entity_key text primary key,
    source     text not null,            -- 'sec_adv' | 'state_adv' | '13f' | '990pf'
    firm_name  text,
    stage      text not null default 'discovered',  -- discovered -> fetched -> extracted -> gated -> done
    status     text not null default 'pending',     -- pending | in_progress | done | failed | duplicate
    claimed_by bigint references ops.runs (run_id),
    detail     jsonb,
    updated_at timestamptz not null default now()
);
create index if not exists candidate_queue_stage_idx on ops.candidate_queue (stage, status);

comment on table gold.entity_gate is
  'ADR-0029: automated inclusion decisions under the ADR-0028 tiered standard. Human adjudication (gold.entity_adjudications) outranks the gate wherever both exist.';
comment on table gold.identity_links is
  'Cross-registry identity resolution: 500 = 500 unique entities, whichever registry surfaced them.';
comment on table ops.candidate_queue is
  'Discovery work queue: per-candidate stage machine advanced by scheduled cycles with run-claimed, resumable transitions.';
