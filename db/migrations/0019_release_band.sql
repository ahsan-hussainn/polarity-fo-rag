-- ADR-0034: the auto-release band. A qualifying record now carries HOW it was released, because
-- "a human ratified this entity" and "the measured gate released this entity" are different
-- strengths of claim and a buyer is entitled to tell them apart on the record itself.
--
-- release_basis: 'human_ratified' (ADR-0020/0021 adjudication) | 'gate_released' (ADR-0034 band).
-- release_basis_detail: the plain-English reason, e.g. the client-mix numbers that cleared the
-- band. Never a bare boolean on a surface.

alter table gold.records
    add column if not exists release_basis text,
    add column if not exists release_basis_detail text;

comment on column gold.records.release_basis is
    'How this record earned its release_state: human_ratified (a person adjudicated the entity and '
    'the decision-maker) or gate_released (the deterministic inclusion gate affirmed it AND it '
    'cleared the ADR-0034 auto-release band). Human adjudication always outranks the gate.';

comment on column gold.records.release_basis_detail is
    'The evidence that cleared the band, in plain English -- the client-mix consistency numbers or '
    'the concordant published-evidence rules. Shipped on the record, not summarised away.';

-- Gate-released records are entity-established but have no adjudicated decision-maker, so
-- person_status must be able to say exactly that rather than leaving a silent NULL.
comment on column gold.records.person_status is
    'proven = an adjudicated allocation-authority decision-maker (ADR-0021). not_established = the '
    'entity is released but no decision-maker has been proven yet; the record counts on entity '
    'evidence under ADR-0028 field-permissive, and says so.';
