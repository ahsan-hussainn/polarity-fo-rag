-- 0005_enrichment_fields.sql
-- FO-MAX parity fields (docs/findings/fo-max-comparison.md). Two are free -- street address and URL
-- quality come from data we already hold (ADV bronze + the website fetch signals) and are filled at
-- gold-build time. Corporate LinkedIn needs external enrichment, so it lands on silver.firms (with a
-- provenance column) where the enrichment stage can write it and gold can read it.

alter table silver.firms add column if not exists corporate_linkedin        text;
alter table silver.firms add column if not exists corporate_linkedin_source text;  -- how we found it

alter table gold.records add column if not exists street_address          text;
alter table gold.records add column if not exists url_quality             text;   -- Highest/Medium/Lower
alter table gold.records add column if not exists corporate_linkedin      text;
alter table gold.records add column if not exists primary_contact_location text;
