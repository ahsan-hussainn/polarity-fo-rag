-- 0015_rename_reachability.sql
-- Rename actionability -> reachability: the metric measures how directly you can reach the proven
-- decision-maker (the contact channel), which is more precisely "reachability". Holistic
-- actionability = reachability + confidence + a recent signal, read across those columns rather than
-- collapsed into one composite.

alter table gold.records rename column actionability_tier  to reachability_tier;
alter table gold.records rename column actionability_score to reachability_score;

comment on column gold.records.reachability_tier is
  'How directly you can reach the proven decision-maker. High = usable email (firm-published PUB or vendor-deliverable A); Medium = plausible email (B) or phone+LinkedIn; Low = a single cold route (phone-only / LinkedIn-only).';
