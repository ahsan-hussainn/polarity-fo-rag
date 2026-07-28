-- 0018: let a ratified adjudication carry ADR-0028's third counted category.
--
-- gold.entity_adjudications was written under ADR-0020, when the counted set was SFO/MFO and
-- 'ria_with_fo_practice' meant "kept, not counted". ADR-0028 added embedded_fo_practice as a
-- COUNTED category with its own evidence bar (a named, substantiated FO practice + a second
-- source). The gate already emits it; without this the human ratification that releases a
-- gate affirm would fail the check constraint -- i.e. the release control could not record the
-- decision the standard asks it to make.
--
-- The two categories are deliberately kept distinct rather than renamed: 'ria_with_fo_practice'
-- remains the Stage 1 label for firms kept and NOT counted, and ADR-0028 says those firms may
-- re-enter qualifying only by clearing the category-3 bar through adjudication. Collapsing the
-- labels would silently promote seven firms nobody re-reviewed.

alter table gold.entity_adjudications drop constraint if exists entity_adjudications_category_check;
alter table gold.entity_adjudications add constraint entity_adjudications_category_check
  check (category in ('single_family_office', 'multi_family_office', 'embedded_fo_practice',
                      'ria_with_fo_practice', 'wealth_manager', 'not_fo', 'unresolved'));

comment on column gold.entity_adjudications.category is
  'ADR-0028 counted categories (single_family_office, multi_family_office, embedded_fo_practice) plus the non-counting outcomes a reviewer can reach. Never blended on any surface.';
