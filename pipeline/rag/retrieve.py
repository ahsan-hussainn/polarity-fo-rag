"""Hybrid retrieval over gold.rag_docs (ADR-0013, ADR-0016): dense pgvector + lexical tsvector,
fused by RRF, with typed SQL filters as a pre-filter leg.

Two rankings are produced independently -- semantic (cosine over the OpenAI embedding) and lexical
(Postgres full-text) -- then combined with Reciprocal Rank Fusion: a document's score is the sum of
1/(k + rank) across the lists it appears in. RRF is rank-based, so it needs no score normalisation or
per-corpus weight tuning, and a document strong on either signal surfaces.

Typed constraints (state, AUM) are applied as WHERE clauses on gold.records BEFORE ranking, not as a
third ranked list: if the user asked for California, a Texas firm is wrong, not merely lower-ranked.
Sector constraints deliberately stay semantic/lexical -- sectors are uncontrolled vocabulary extracted
from websites, so a hard filter there would silently drop true matches.

The fused top-k is joined back to the FULL gold record (contacts, grades + explanations, phone,
LinkedIn, AUM, provenance) so the grounding step can route outreach, not just recite facts.
"""
from __future__ import annotations

from pipeline import db

RRF_K = 60   # standard RRF constant; dampens the influence of low ranks

# Release gate: the RAG serves ONLY qualifying family offices (entity affirmed FO + decision-maker
# proven). Reclassified non-FOs (wealth managers / RIAs) and quarantined firms are never retrievable
# -- this is a family-office product, so a non-FO must not surface in an answer at all (stronger than
# labeling it after the fact). The reclassified firms live in reclassified_firms.csv for audit.
_RELEASE_GATE = "release_state = 'qualifying'"

# Everything the answer layer needs to say "whom to contact, why them, and how to reach them" --
# plus the entity category + person basis so every surface labels a firm the same way (ADR-0023:
# a reclassified non-FO must never be presented as a family office).
RECORD_COLUMNS = (
    "crd, family_office_name, city, state, country, founded_year, aum_usd, firm_phone, "
    "investing_sectors, investment_thesis, description, website, corporate_linkedin, "
    "primary_contact_name, primary_contact_title, primary_contact_email, primary_email_grade, "
    "primary_email_explanation, secondary_contact_name, secondary_contact_title, "
    "secondary_contact_email, secondary_email_grade, secondary_email_explanation, adv_filing_url, "
    "entity_category, person_status, primary_authority_basis, primary_selection_basis, "
    "reachability_tier, confidence_score, data_asof"
)


def _filter_sql(state: str | None, min_aum: int | None, max_aum: int | None) -> tuple[str, list]:
    """WHERE fragment (over alias r = gold.records) + params for the typed constraints."""
    conds, params = [], []
    if state:
        conds.append("r.state = %s")
        params.append(state.upper())
    if min_aum:
        conds.append("r.aum_usd >= %s")
        params.append(min_aum)
    if max_aum:
        conds.append("r.aum_usd <= %s")
        params.append(max_aum)
    return (" and " + " and ".join(conds)) if conds else "", params


def _vector_ranked(cur, qvec_literal: str, n: int, fsql: str, fparams: list) -> list[str]:
    cur.execute("select d.crd from gold.rag_docs d join gold.records r using (crd) "
                f"where d.embedding is not null and r.{_RELEASE_GATE}{fsql} "
                "order by d.embedding <=> %s::vector limit %s",
                (*fparams, qvec_literal, n))
    return [r[0] for r in cur.fetchall()]


def _lexical_ranked(cur, query: str, n: int, fsql: str, fparams: list) -> list[str]:
    cur.execute("select d.crd from gold.rag_docs d join gold.records r using (crd) "
                f"where d.tsv @@ plainto_tsquery('english', %s) and r.{_RELEASE_GATE}{fsql} "
                "order by ts_rank(d.tsv, plainto_tsquery('english', %s)) desc limit %s",
                (query, *fparams, query, n))
    return [r[0] for r in cur.fetchall()]


def _attach_signals(cur, records: list[dict]) -> list[dict]:
    """Attach each record's recent signals (the 'why now', most recent first) in place."""
    crds = [r["crd"] for r in records if r.get("crd")]
    if not crds:
        return records
    by = {r["crd"]: r for r in records}
    cur.execute("select crd, signal_type, signal_date, description from gold.record_signals "
                "where crd = any(%s) order by crd, signal_date desc", (crds,))
    for crd, stype, sdate, sdesc in cur.fetchall():
        by[crd].setdefault("signals", []).append({"type": stype, "date": sdate, "description": sdesc})
    return records


def records_by_crd(cur, crds: list[str]) -> dict[str, dict]:
    """Full gold records keyed by crd, each with its recent signals."""
    if not crds:
        return {}
    cur.execute(f"select {RECORD_COLUMNS} from gold.records where crd = any(%s)", (crds,))
    cols = [d[0] for d in cur.description]
    recs = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    _attach_signals(cur, list(recs.values()))
    return recs


def nearest_distance(qvec: list[float]) -> float | None:
    """Smallest cosine distance from the query embedding to ANY qualifying record -- the topical-
    relevance signal the answer layer uses to detect out-of-scope queries (ADR-0026).

    Deliberately UNFILTERED (no state/AUM): this measures whether the query is about the family-office
    dataset at all, independent of any narrowing constraint -- "family offices in Ohio" is on-topic
    even if Ohio has few matches. RRF scores cannot serve here: they are rank-based, so the top hit of
    every query scores ~1/(RRF_K+1) regardless of true similarity; raw cosine distance is the number
    that separates in-scope (~0.24-0.50) from out-of-scope (~0.79-1.00). Returns None if no qualifying
    record exists (empty index)."""
    from pipeline.rag.embed import _vec_literal

    lit = _vec_literal(qvec)
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute("select d.embedding <=> %s::vector as dist "
                    "from gold.rag_docs d join gold.records r using (crd) "
                    f"where d.embedding is not null and r.{_RELEASE_GATE} "
                    "order by d.embedding <=> %s::vector limit 1", (lit, lit))
        row = cur.fetchone()
    return float(row[0]) if row else None


def by_name(name: str, limit: int = 3) -> list[dict]:
    """Lookup path: match a named firm directly (name or domain), no embedding round-trip."""
    like = f"%{name.strip()}%"
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(f"select {RECORD_COLUMNS} from gold.records "
                    f"where (family_office_name ilike %s or domain ilike %s) and {_RELEASE_GATE} "
                    "order by data_completion_score desc limit %s", (like, like, limit))
        cols = [d[0] for d in cur.description]
        recs = [{**dict(zip(cols, r)), "score": 1.0, "matched": ["name"]} for r in cur.fetchall()]
        return _attach_signals(cur, recs)


def by_filters(state: str | None = None, min_aum: int | None = None, max_aum: int | None = None,
               sector_term: str | None = None, limit: int = 50) -> tuple[int, list[dict]]:
    """Aggregate path: EXACT matching over gold.records via SQL -- returns (total_count, records).
    Sector matching here is keyword-based over sectors/thesis/description and the answer layer
    labels it as such; state/AUM are typed and exact."""
    fsql, params = _filter_sql(state, min_aum, max_aum)
    if sector_term:
        fsql += (" and (exists (select 1 from unnest(r.investing_sectors) s where s ilike %s) "
                 "or r.investment_thesis ilike %s or r.description ilike %s)")
        like = f"%{sector_term}%"
        params += [like, like, like]
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(f"select count(*) from gold.records r where r.{_RELEASE_GATE}{fsql}", params)
        total = cur.fetchone()[0]
        cur.execute(f"select {RECORD_COLUMNS} from gold.records r where r.{_RELEASE_GATE}{fsql} "
                    "order by r.aum_usd desc nulls last, r.data_completion_score desc limit %s",
                    (*params, limit))
        cols = [d[0] for d in cur.description]
        recs = [{**dict(zip(cols, r)), "score": 1.0, "matched": ["sql"]} for r in cur.fetchall()]
    return total, recs


def hybrid(query: str, k: int = 5, pool: int = 20, *, state: str | None = None,
           min_aum: int | None = None, max_aum: int | None = None,
           qvec: list[float] | None = None) -> list[dict]:
    """Fuse semantic + lexical rankings (RRF), optionally pre-filtered by typed constraints,
    and return the top-k FULL gold records with provenance. Pass qvec when the query embedding
    was already computed (the answer layer embeds speculatively, in parallel with intent
    classification -- ADR-0017) to skip a second embedding round-trip."""
    from pipeline.rag.embed import embed_query, _vec_literal

    qvec = _vec_literal(qvec if qvec is not None else embed_query(query))
    fsql, fparams = _filter_sql(state, min_aum, max_aum)
    with db.get_pool().connection() as c, c.cursor() as cur:
        vec_ids = _vector_ranked(cur, qvec, pool, fsql, fparams)
        lex_ids = _lexical_ranked(cur, query, pool, fsql, fparams)
        scores: dict[str, float] = {}
        for rank, crd in enumerate(vec_ids, 1):
            scores[crd] = scores.get(crd, 0.0) + 1.0 / (RRF_K + rank)
        for rank, crd in enumerate(lex_ids, 1):
            scores[crd] = scores.get(crd, 0.0) + 1.0 / (RRF_K + rank)
        if not scores:
            return []
        top = sorted(scores, key=lambda c: scores[c], reverse=True)[:k]
        by_crd = records_by_crd(cur, top)
    return [
        {**by_crd[crd], "score": round(scores[crd], 4),
         "matched": [s for s, hit in (("semantic", crd in vec_ids), ("lexical", crd in lex_ids)) if hit]}
        for crd in top if crd in by_crd
    ]
