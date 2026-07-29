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


def t_record_history(args: dict) -> tuple[dict, list[dict]]:
    """What the operating layer has observed about one firm across cycles (ADR-0038).

    The only tool that reads ops.*, and the reason Goal 3 is answerable at all: every other tool
    describes the CURRENT state, so a question about what changed, when, and what should no longer
    be trusted had no code path. Returns evidence and timestamps only -- no contact data -- so it
    cannot become a side channel around release policy.
    """
    name = str(args.get("name") or "").strip()
    crd = str(args.get("crd") or "").strip()
    with db.get_pool().connection() as c, c.cursor() as cur:
        # No firm named: report the whole set's change picture. Without this the agent had no way
        # to DISCOVER which records changed -- record_history could only confirm a firm you already
        # suspected -- so it answered "what should I re-check?" from quarantine_summary instead,
        # conflating never-released candidates with released records whose evidence moved.
        if not crd and not name:
            cur.execute(
                "select crd, family_office_name, entity_category, trust_reason, last_checked_at "
                "  from gold.records where release_state = 'qualifying' and trust_state = 'flagged'"
                " order by last_checked_at desc nulls last")
            flagged = [{"crd": a, "firm": b, "category": c_, "why": d,
                        "last_checked": str(e) if e else None}
                       for a, b, c_, d, e in cur.fetchall()]
            cur.execute("select count(*) from gold.records where release_state = 'qualifying'")
            total = cur.fetchone()[0]
            return {"scope": "all qualifying records",
                    "qualifying_total": total, "flagged_count": len(flagged),
                    "flagged_records": flagged,
                    "note": ("RELEASED records whose evidence moved since the system recorded them "
                             "-- these are in the product and need re-checking. This is NOT the "
                             "quarantined/unresolved set, which was never released at all. Call "
                             "again with a firm name for that firm's full cross-cycle history.")}, []
        if not crd:
            cur.execute("select crd, family_office_name from gold.records "
                        "where family_office_name ilike %s order by family_office_name limit 1",
                        (f"%{name}%",))
            row = cur.fetchone()
            if row is None:
                return {"found": False,
                        "note": f"no held record matches {name!r}; the system cannot report "
                                f"history for a firm it does not hold"}, []
            crd, firm = row
        else:
            cur.execute("select family_office_name from gold.records where crd = %s", (crd,))
            r = cur.fetchone()
            firm = r[0] if r else None
            if firm is None:
                return {"found": False, "note": f"no held record with CRD {crd}"}, []

        cur.execute("select trust_state, trust_reason, last_checked_at, data_asof, release_basis "
                    "from gold.records where crd = %s", (crd,))
        st = cur.fetchone()
        cur.execute(
            "select te.check_type, te.prior, te.current, te.evidence, te.action, te.created_at, "
            "       te.run_id from ops.trust_events te join ops.runs r using (run_id) "
            " where te.crd = %s and coalesce(r.config->>'write','false') = 'true' "
            " order by te.created_at desc limit 20", (crd,))
        events = [{"check": a, "was": b, "now": d, "evidence": e, "action": f,
                   "observed_at": str(g), "run_id": h}
                  for a, b, d, e, f, g, h in cur.fetchall()]
        cur.execute(
            "select kind, count(*), min(observed_at), max(observed_at) from ops.observations "
            " where crd = %s group by kind order by kind", (crd,))
        coverage = [{"observed": a, "times": b, "first": str(c_), "latest": str(d)}
                    for a, b, c_, d in cur.fetchall()]

    return {"found": True, "crd": crd, "firm": firm,
            "current_trust_state": st[0] if st else None,
            "current_trust_reason": st[1] if st else None,
            "last_checked_at": str(st[2]) if st and st[2] else None,
            "source_document_date": str(st[3]) if st and st[3] else None,
            "release_basis": st[4] if st else None,
            "trust_events": events, "observation_coverage": coverage,
            "note": ("cross-cycle history from the operating ledger: what the system observed, "
                     "when, and why trust changed. Evidence only -- no contact data.")}, []


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
            "min_aum_usd": {
                "type": "integer",
                "description": "ONLY when the goal constrains the size of the FAMILY OFFICE itself "
                               "('family offices over $1B'). Never derive this from a fund's market "
                               "segment: 'lower-middle-market' or 'small-cap' describes the FUND's "
                               "deals, not its investors. A $5B family office writing an LP cheque "
                               "into a lower-middle-market fund is a fit, not a mismatch. Omit if "
                               "unsure -- a wrong band makes good matches look unsuitable."},
            "max_aum_usd": {
                "type": "integer",
                "description": "Same rule as min_aum_usd: the TARGET FIRM's size only, never the "
                               "fund's deal size. Omit if unsure."},
            "k": {"type": "integer", "default": 10}}, "required": ["mandate"]}},
    "get_record": {
        "fn": t_get_record, "pickable": True,
        "description": "Full record for a named firm (name or domain match).",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                       "required": ["name"]}},
    "record_history": {
        "fn": t_record_history, "pickable": False,
        "description": "Cross-cycle history from the operating ledger -- the ONLY tool that sees "
                       "anything but the current state. Call with NO arguments to list every "
                       "RELEASED record whose evidence has moved and now needs re-checking (use "
                       "this for 'what changed / what should I not trust / what went stale' -- "
                       "NOT quarantine_summary, which is the never-released set). Call with a "
                       "firm name for that firm's full run-by-run history. Evidence and "
                       "timestamps only, never contact data.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "firm name (partial match)"},
            "crd": {"type": "string", "description": "CRD if known; takes precedence over name"}},
            "required": []}},
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
