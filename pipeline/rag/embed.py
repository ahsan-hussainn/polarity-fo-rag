"""Embed the gold dataset for retrieval (ADR-0013).

Each gold record is rendered to one prose document (`_content_for`) and embedded with OpenAI
text-embedding-3-small, stored in gold.rag_docs alongside a generated tsvector. The embedding call is
the seam point -- swap `embed_texts` for a local sentence-transformers implementation without touching
retrieval. Vectors are written as pgvector string literals so no extra Python client is needed (keeps
the deploy container small, per ADR-0013).
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from pipeline import db

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536  # text-embedding-3-small; must match db/migrations/0006_rag.sql

# ADV stores state as a USPS code, but users ask in words ("family offices in California"). tsvector
# cannot match 'california' against 'CA', so the rendered prose carries both forms.
_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "Washington DC", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin",
    "WY": "Wyoming",
}


def _aum_words(aum) -> str | None:
    if not aum:
        return None
    if aum >= 1_000_000_000:
        return f"${aum / 1e9:.1f} billion"
    return f"${aum / 1e6:.0f} million"


def _content_for(r: dict) -> str:
    """Render a gold record to the searchable prose we embed + full-text index."""
    state = r.get("state")
    state_full = f"{state} ({_STATES[state]})" if state in _STATES else state
    loc = ", ".join(x for x in (r.get("city"), state_full, r.get("country")) if x)
    parts = [f"{r['family_office_name']} is a family office"]
    if loc:
        parts.append(f" based in {loc}")
    if r.get("founded_year"):
        parts.append(f", founded {r['founded_year']}")
    parts.append(".")
    if r.get("aum_usd"):
        parts.append(f" Regulatory assets under management (AUM): {_aum_words(r['aum_usd'])}.")
    if r.get("investment_thesis"):
        parts.append(f" Investment thesis: {r['investment_thesis']}")
    if r.get("description"):
        parts.append(f" {r['description']}")
    if r.get("investing_sectors"):
        parts.append(f" Sectors: {', '.join(r['investing_sectors'])}.")
    if r.get("primary_contact_name"):
        title = r.get("primary_contact_title") or "principal"
        parts.append(f" Primary contact: {r['primary_contact_name']}, {title}.")
    return "".join(parts)


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """The embedding seam. One batched OpenAI call; returns one vector per input text."""
    from openai import OpenAI

    resp = OpenAI().embeddings.create(model=model or EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def build_index(write: bool = False) -> dict:
    """Render every gold record, embed the batch, and upsert into gold.rag_docs."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, family_office_name, city, state, country, founded_year, aum_usd, "
                    "investment_thesis, description, investing_sectors, primary_contact_name, "
                    "primary_contact_title from gold.records order by crd")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    docs = [(r["crd"], _content_for(r)) for r in rows]
    out = {"documents": len(docs), "written": write, "model": EMBED_MODEL}
    if not write:
        out["sample"] = docs[0][1] if docs else None
        return out

    vectors = embed_texts([d[1] for d in docs])
    with db.get_conn() as c, c.cursor() as cur:
        for (crd, content), vec in zip(docs, vectors):
            cur.execute(
                "insert into gold.rag_docs (crd, content, embedding) values (%s, %s, %s::vector) "
                "on conflict (crd) do update set content=excluded.content, "
                "embedding=excluded.embedding, updated_at=now()",
                (crd, content, _vec_literal(vec)))
        c.commit()
    out["embedded"] = len(vectors)
    return out
