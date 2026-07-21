-- 0014_record_signals.sql
-- Time-sensitive signals (Bridge Mandate correction #6): the "why now" a fund manager needs -- recent
-- investments, key hires, leadership changes, news -- each DATED and SOURCED so staleness is visible
-- and a dated event is never silently converted into a current recommendation. Signals are researched
-- per firm and ratified (like the entity/contact adjudications); the OPERATING LOOP that keeps them
-- current over time is the Stage 2 agent, not this pre-window population.

create table if not exists gold.record_signals (
    id          bigserial primary key,
    crd         text not null,
    signal_type text not null check (signal_type in
                 ('recent_investment', 'key_hire', 'leadership_change', 'news', 'growth')),
    description text not null,
    signal_date text not null,          -- YYYY-MM or YYYY-MM-DD (the event date; freshness input)
    source_url  text not null,          -- every signal carries its basis
    observed_at timestamptz not null default now(),
    decided_by  text not null
);
create index if not exists record_signals_crd_idx on gold.record_signals (crd);
create unique index if not exists record_signals_uniq on gold.record_signals (crd, description);

comment on table gold.record_signals is
  'ADR/correction #6: dated, sourced recent signals per family office (why-now). Initial population pre-window; kept current by the Stage 2 operating agent.';
