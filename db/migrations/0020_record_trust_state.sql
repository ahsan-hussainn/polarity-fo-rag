-- ADR-0037: evidence-based freshness ON the delivered record.
--
-- Until now the only freshness field a buyer could see was `is_stale`, computed as "the ADV filing
-- is more than 15 months old" -- calendar arithmetic. The Stage 2 brief is explicit that this does
-- not count: "A clock-based expiry alone does not satisfy this condition." Meanwhile every piece of
-- real evidence the system gathers -- website went dark, registration lapsed, a newer filing
-- exists, a decision-maker vanished from the roster -- lived in ops.trust_events and never reached
-- the artifact the customer receives.
--
-- These three columns join that evidence to the record, so deliverable 5 ("the 500 records
-- including whatever the system uses to track how fresh or trustworthy each record is") is
-- satisfied by the record itself rather than by a separate log a reader has to correlate by hand.

alter table gold.records
    add column if not exists last_checked_at   timestamptz,
    add column if not exists trust_state       text,
    add column if not exists trust_reason      text;

comment on column gold.records.last_checked_at is
    'When an operating cycle last OBSERVED this firm''s external evidence (site fetch, registry '
    're-check). Distinct from data_asof, which is the age of the source document; this is the age '
    'of our last look at it.';

comment on column gold.records.trust_state is
    'current = no unresolved trust event. flagged = a cycle found evidence that reduces confidence '
    'in this record and nothing has since resolved it. Derived from ops.trust_events (latest event '
    'per check type), never set by hand.';

comment on column gold.records.trust_reason is
    'The evidence behind a flagged state, in the words the detector recorded -- e.g. the HTTP '
    'status change, the newer filing date, the lapsed registration. Empty when trust_state is '
    'current.';
