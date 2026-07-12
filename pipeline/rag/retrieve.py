"""Hybrid retrieval over gold.rag_docs (ADR-0013): dense pgvector + lexical tsvector, fused by RRF.

Two rankings are produced independently -- semantic (cosine over the OpenAI embedding) and lexical
(Postgres full-text) -- then combined with Reciprocal Rank Fusion: a document's score is the sum of
1/(k + rank) across the lists it appears in. RRF is rank-based, so it needs no score normalisation or
per-corpus weight tuning, and a document strong on either signal surfaces. Returns the fused top-k
joined back to the full gold record so the grounding step has the contact + email grade to cite.
"""
from __future__ import annotations

from pipeline import db

RRF_K = 60   # standard RRF constant; dampens the influence of low ranks


def _vector_ranked(cur, qvec_literal: str, n: int) -> list[str]:
    cur.execute("select crd from gold.rag_docs where embedding is not null "
                "order by embedding <=> %s::vector limit %s", (qvec_literal, n))
    return [r[0] for r in cur.fetchall()]


def _lexical_ranked(cur, query: str, n: int) -> list[str]:
    cur.execute("select crd from gold.rag_docs where tsv @@ plainto_tsquery('english', %s) "
                "order by ts_rank(tsv, plainto_tsquery('english', %s)) desc limit %s",
                (query, query, n))
    return [r[0] for r in cur.fetchall()]


def hybrid(query: str, k: int = 5, pool: int = 20) -> list[dict]:
    """Fuse semantic + lexical rankings (RRF) and return the top-k gold records with provenance."""
    from pipeline.rag.embed import embed_query, _vec_literal

    qvec = _vec_literal(embed_query(query))
    with db.get_conn() as c, c.cursor() as cur:
        vec_ids = _vector_ranked(cur, qvec, pool)
        lex_ids = _lexical_ranked(cur, query, pool)
        scores: dict[str, float] = {}
        for rank, crd in enumerate(vec_ids, 1):
            scores[crd] = scores.get(crd, 0.0) + 1.0 / (RRF_K + rank)
        for rank, crd in enumerate(lex_ids, 1):
            scores[crd] = scores.get(crd, 0.0) + 1.0 / (RRF_K + rank)
        if not scores:
            return []
        top = sorted(scores, key=lambda c: scores[c], reverse=True)[:k]
        cur.execute(
            "select crd, family_office_name, city, state, investing_sectors, investment_thesis, "
            "founded_year, primary_contact_name, primary_contact_title, primary_contact_email, "
            "primary_email_grade, corporate_linkedin, website "
            "from gold.records where crd = any(%s)", (top,))
        cols = [d[0] for d in cur.description]
        by_crd = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    return [
        {**by_crd[crd], "score": round(scores[crd], 4),
         "matched": [s for s, hit in (("semantic", crd in vec_ids), ("lexical", crd in lex_ids)) if hit]}
        for crd in top if crd in by_crd
    ]
