"""The agent's tool registry (ADR-0031). Typed schemas are a submission deliverable.

Each tool wraps an existing retrieval capability -- the agent gets no path to data that the
serving layer does not already have, and no tool exposes what release policy suppresses:
quarantine_summary returns status + evidence-based reason ONLY (never contact data), and its
firms are recorded as non-pickable so the output gate can reject any answer that promotes one.

Every execution is ledgered (ops.run_events) and its returned records are added to the session's
GROUNDING SET -- the closed world the final answer is checked against.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from pipeline import db


def _jsonable(x):
    if isinstance(x, (date, datetime)):
        return str(x)
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonable(v) for v in x]
    return x


def _slim(rec: dict) -> dict:
    """Record view the model reasons over: enough to act on, honest about basis, no bulk."""
    keep = ("crd", "family_office_name", "entity_category", "city", "state", "aum_usd",
            "investing_sectors", "investment_thesis", "description", "primary_contact_name",
            "primary_contact_title", "primary_contact_email", "primary_email_grade",
            "secondary_contact_name", "secondary_contact_email", "secondary_email_grade",
            "person_status", "primary_authority_basis", "reachability_tier", "confidence_score",
            "data_asof", "release_basis", "trust_state", "trust_reason", "signals", "fit_score",
            "components", "fit_confidence", "evidence", "caveats", "aum_note")
    return _jsonable({k: rec[k] for k in keep if k in rec and rec[k] not in (None, [], "")})


def t_structured_search(args: dict) -> tuple[dict, list[dict]]:
    from pipeline.rag.retrieve import by_filters

    total, recs = by_filters(state=args.get("state"), min_aum=args.get("min_aum_usd"),
                             max_aum=args.get("max_aum_usd"), sector_term=args.get("sector_term"),
                             limit=min(int(args.get("limit") or 15), 25))
    note = ("sector matching is keyword-based (approximate); state/AUM are exact"
            if args.get("sector_term") else "state/AUM filters are exact")
    return {"total_matching": total, "returned": len(recs), "method_note": note,
            "records": [_slim(r) for r in recs]}, recs


def t_semantic_search(args: dict) -> tuple[dict, list[dict]]:
    from pipeline.rag.retrieve import hybrid

    recs = hybrid(str(args.get("query") or ""), k=min(int(args.get("k") or 5), 10))
    return {"returned": len(recs), "records": [_slim(r) for r in recs]}, recs


def t_fit_rank(args: dict) -> tuple[dict, list[dict]]:
    from pipeline.rag.fit import fit_rank

    out = fit_rank(str(args.get("mandate") or ""),
                   sector_terms=args.get("sector_terms") or [],
                   min_aum=args.get("min_aum_usd"), max_aum=args.get("max_aum_usd"),
                   k=min(int(args.get("k") or 10), 24))
    recs = out["ranked"]
    return {**out, "ranked": [_slim(r) for r in recs]}, recs


def t_get_record(args: dict) -> tuple[dict, list[dict]]:
    from pipeline.rag.retrieve import by_name

    recs = by_name(str(args.get("name") or ""), limit=3)
    return {"returned": len(recs), "records": [_slim(r) for r in recs]}, recs


def t_quarantine_summary(args: dict) -> tuple[dict, list[dict]]:
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, family_office_name, entity_category, release_state, "
                    "release_reasons from gold.records where release_state <> 'qualifying' "
                    "order by family_office_name")
        rows = cur.fetchall()
    items = [{"crd": r[0], "firm": r[1], "category": r[2], "release_state": r[3],
              "reasons": r[4]} for r in rows]
    return {"note": ("firms the system holds but does NOT release: reclassified non-FOs and "
                     "quarantined/unresolved entities. Status and reason only -- their data may "
                     "not be used as evidence and they may not be recommended."),
            "count": len(items), "firms": _jsonable(items)}, []


TOOLS = {
    "structured_search": {
        "fn": t_structured_search, "pickable": True,
        "description": "Exact SQL search over qualifying family-office records by state, AUM band, "
                       "and/or sector keyword. Returns the TRUE total matching count plus records.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string", "description": "2-letter US state code"},
            "min_aum_usd": {"type": "integer"}, "max_aum_usd": {"type": "integer"},
            "sector_term": {"type": "string", "description": "single sector keyword (approximate match)"},
            "limit": {"type": "integer", "default": 15}}, "required": []}},
    "semantic_search": {
        "fn": t_semantic_search, "pickable": True,
        "description": "Hybrid semantic+lexical retrieval over qualifying records for a natural-"
                       "language query. Use for thematic matching beyond exact filters.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "k": {"type": "integer", "default": 5}},
            "required": ["query"]}},
    "fit_rank": {
        "fn": t_fit_rank, "pickable": True,
        "description": "Rank ALL qualifying records for an investor mandate. Deterministic weighted "
                       "scoring with per-record component breakdown, evidence list, caveats, and an "
                       "evidence-based fit_confidence tier (strong/moderate/weak/"
                       "insufficient_evidence). The primary tool for LP-fit goals.",
        "parameters": {"type": "object", "properties": {
            "mandate": {"type": "string", "description": "the investor mandate in plain words"},
            "sector_terms": {"type": "array", "items": {"type": "string"},
                             "description": "sector/strategy keywords to evidence against"},
            "min_aum_usd": {"type": "integer"}, "max_aum_usd": {"type": "integer"},
            "k": {"type": "integer", "default": 10}}, "required": ["mandate"]}},
    "get_record": {
        "fn": t_get_record, "pickable": True,
        "description": "Full record for a named firm (name or domain match).",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                       "required": ["name"]}},
    "quarantine_summary": {
        "fn": t_quarantine_summary, "pickable": False,
        "description": "Status + evidence-based reason for every firm the system holds but does "
                       "not release (reclassified non-FOs, quarantined). Use to report coverage "
                       "honestly; these firms cannot be recommended and carry no contact data.",
        "parameters": {"type": "object", "properties": {}, "required": []}},
}


def openai_tools() -> list[dict]:
    return [{"type": "function",
             "function": {"name": n, "description": t["description"], "parameters": t["parameters"]}}
            for n, t in TOOLS.items()]


def schemas_json() -> str:
    """The tool-interface deliverable: every tool's schema, exactly as the model sees it."""
    return json.dumps(openai_tools(), indent=2)
