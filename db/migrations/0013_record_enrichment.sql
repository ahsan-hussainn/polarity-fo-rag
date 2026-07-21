-- 0013_record_enrichment.sql
-- Record-level KPIs that make a family-office record decision-grade rather than merely complete
-- (buyer question: whom to contact, why them, why now, how much to trust it). All are computed
-- deterministically at build time from evidence the pipeline already holds:
--   actionability  -- can a fund manager act on this today? proven decision-maker + reach quality.
--   confidence     -- how well-PROVEN the record is: entity evidence + person proof + email proof.
--   data_asof      -- freshness anchor: the firm's most recent SEC ADV filing date.
--   is_stale       -- the freshness anchor is older than the annual-filing window (trust signal).
-- (Time-sensitive SIGNALS -- recent investments/hires/news -- are added separately with their own
--  research + dating; the operating loop that keeps them current is the Stage 2 agent.)

alter table gold.records add column if not exists actionability_tier  text;   -- High | Medium | Low
alter table gold.records add column if not exists actionability_score int;    -- 0-100
alter table gold.records add column if not exists confidence_score    int;    -- 0-100
alter table gold.records add column if not exists data_asof           date;   -- SEC ADV latest filing
alter table gold.records add column if not exists is_stale            boolean;

comment on column gold.records.actionability_tier is
  'ADR: can a fund manager act on this FO today? High = proven decision-maker + firm-published/vendor-deliverable email; Medium = + catch-all/phone; Low = LinkedIn/none.';
