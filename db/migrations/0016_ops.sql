-- 0016: the OPS layer -- the operating system's memory (assessment Stage 2, ADR-0027).
--
-- Stage 1 ran as hand-invoked batches; Stage 2 is judged on what the system did while running
-- unattended ("we read the system by what it did while running"). These tables are that record:
-- every run, every discrete action, every per-record observation, every trust decision, every
-- serving query. Nothing here is a cache -- it is the submission artifact (the complete, uncurated
-- run logs) and the evidence base the architecture notes' cost/latency claims are computed from.

create schema if not exists ops;

-- One row per run: a scheduled cycle, a manual invocation, a goal session, an eval pass.
create table if not exists ops.runs (
    run_id      bigint generated always as identity primary key,
    kind        text        not null,                 -- 'cycle' | 'goal' | 'eval'
    trigger     text        not null,                 -- 'schedule' | 'workflow_dispatch' | 'local' | 'api'
    git_sha     text,                                 -- what code ran (replay/inspect; arch note 4)
    started_at  timestamptz not null default now(),
    finished_at timestamptz,
    status      text        not null default 'running',  -- 'running' | 'ok' | 'failed'
    error       text,
    config      jsonb,                                -- flags/batch sizes the run started with
    tokens_in   bigint      not null default 0,       -- rolled up from run_events at close
    tokens_out  bigint      not null default 0,
    usd_est     numeric(12,6) not null default 0,
    summary     jsonb                                 -- per-phase counts, written at close
);

-- Every discrete action inside a run: model call, external fetch, retrieval, decision. call_class
-- gives the architecture notes their required breakout (model vs retrieval vs external API).
create table if not exists ops.run_events (
    id          bigint generated always as identity primary key,
    run_id      bigint      not null references ops.runs (run_id),
    at          timestamptz not null default now(),
    phase       text        not null,                 -- 'observe' | 'refresh' | 'discover' | 'rebuild' | 'goal'
    event       text        not null,                 -- e.g. 'fetch_home', 'embed_batch', 'reconcile'
    call_class  text,                                 -- 'model' | 'external_api' | 'retrieval' | 'db' | 'decision'
    target      text,                                 -- crd / url / other subject
    status      text,                                 -- 'ok' | 'error' | 'skipped'
    duration_ms int,
    tokens_in   int,
    tokens_out  int,
    usd_est     numeric(12,6),
    detail      jsonb
);
create index if not exists run_events_run_idx on ops.run_events (run_id, at);

-- Per-record evidence baselines. Cross-run staleness = a LATER run's observation contradicting an
-- EARLIER run's for the same (crd, kind), with the delta captured as the reason. The mandate is
-- explicit that a clock-based expiry alone does not satisfy the staleness condition; these rows are
-- what makes a staleness/trust decision evidence-based instead.
create table if not exists ops.observations (
    id          bigint      generated always as identity primary key,
    run_id      bigint      not null references ops.runs (run_id),
    crd         text        not null,
    kind        text        not null,                 -- 'website_home_hash' | 'website_http_status' | 'adv_filing_date' | 'email_grades'
    value       text,                                 -- hash / status / date / grades
    url         text,
    observed_at timestamptz not null default now(),
    detail      jsonb
);
create index if not exists observations_crd_kind_idx on ops.observations (crd, kind, observed_at desc);

-- Trust decisions: what changed, the evidence, and what the system DID about it.
create table if not exists ops.trust_events (
    id          bigint      generated always as identity primary key,
    run_id      bigint      not null references ops.runs (run_id),
    crd         text        not null,
    check_type  text        not null,                 -- 'website_change' | 'website_dark' | 'adv_filing' | 'email_reverify'
    prior       text,
    current     text,
    evidence    text        not null,                 -- the captured, evidence-based reason (mandate condition 3)
    action      text        not null,                 -- 'noted' | 'flagged' | 'refreshed' | 'trust_reduced' | 'quarantined'
    created_at  timestamptz not null default now()
);
create index if not exists trust_events_crd_idx on ops.trust_events (crd, created_at desc);

-- Serving query log (ADR-0026 Layer 3, approved 2026-07-23, built here): per-query scope decision,
-- outcome, and verification verdict -- the "protections firing on real runs" evidence, and the data
-- a boundary recalibration would be measured on.
create table if not exists ops.query_log (
    id               bigint      generated always as identity primary key,
    at               timestamptz not null default now(),
    source           text        not null,            -- 'ui' | 'api' | 'cli' | 'agent' | 'eval'
    query            text        not null,
    intent           text,
    nearest_distance double precision,                -- ADR-0026 floor input
    outcome          text        not null,            -- 'answered' | 'no_match' | 'refused_out_of_scope' | 'refused_verification' | 'error'
    verification     jsonb,                           -- ADR-0023 verdict as returned to the caller
    latency_ms       int,
    run_id           bigint      references ops.runs (run_id)   -- set when an agent/eval run asks
);
create index if not exists query_log_at_idx on ops.query_log (at desc);

comment on schema ops is 'Operating layer (Stage 2): run ledger, per-record evidence, trust decisions, query log (ADR-0027).';
comment on table ops.runs is 'One row per run (cycle/goal/eval); totals rolled up from run_events at close.';
comment on table ops.observations is 'Per-record evidence baselines; cross-run diffs here are what make staleness evidence-based.';
comment on table ops.trust_events is 'What changed, the captured evidence, and the action taken (mandate condition 3).';
comment on table ops.query_log is 'ADR-0026 Layer 3: every serving query with scope decision + verification verdict.';
