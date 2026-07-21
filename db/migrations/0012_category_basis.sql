-- 0012_category_basis.sql
-- Make the entity decision visible ON the artifact (ADR-0020; Bridge Mandate: "make the
-- qualification decision visible in the data"). The rationale already lives in
-- gold.entity_adjudications; this surfaces it on the gold record so the shipped CSV carries the
-- REASON a firm is a family office / wealth manager / RIA, not just the bare category.

alter table gold.records add column if not exists category_basis text;

comment on column gold.records.category_basis is
  'ADR-0020 rationale for entity_category, copied from gold.entity_adjudications so the shipped artifact shows WHY, not just the label.';
