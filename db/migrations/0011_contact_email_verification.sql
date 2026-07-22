-- 0011_contact_email_verification.sql
-- WS3b: vendor-verified inferred email for the PROVEN decision-maker (ADR-0021/0010). Where the firm
-- does not publish an individual address, we infer the pattern for the ratified contact and verify it
-- with the email API -- honest two-axis grade, precisely labeled. Distinct from published_email:
-- an inferred A grade means "vendor reports this pattern deliverable", NOT "proven to be this person's
-- mailbox" (the exact overclaim the Bridge Mandate flagged). Rejected verdicts (D/F) never ship.

alter table gold.contact_adjudications add column if not exists inferred_email       text;
alter table gold.contact_adjudications add column if not exists inferred_grade       text;   -- A/B/C (D/F never released)
alter table gold.contact_adjudications add column if not exists inferred_code        text;
alter table gold.contact_adjudications add column if not exists inferred_explanation text;
alter table gold.contact_adjudications add column if not exists inferred_evidence    jsonb;

comment on column gold.contact_adjudications.inferred_grade is
  'WS3b vendor verdict on the inferred address for this proven person. A=vendor-deliverable (pattern, not proven to be their mailbox), B=catch-all, C=unknown. D/F are quarantined, never shipped.';
