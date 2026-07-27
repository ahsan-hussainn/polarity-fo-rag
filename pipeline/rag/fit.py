"""fit_rank: mandate-fit ranked retrieval with per-record confidence (ADR-0030).

The Stage 2 retrieval extension. Stage 1 retrieval answers "which records match this query"
(lookup / exact filters / hybrid top-k). fit_rank answers a different, paid-tier question: "rank
the WHOLE qualifying dataset for this investor mandate, and tell me how much to trust each fit."

Deterministic by design: the only model call is the mandate embedding (already the seam every
query uses). Every rank is a weighted sum of named, inspectable components -- semantic affinity
(pgvector distance to the record document), stated-sector evidence (keyword overlap, labeled
approximate), record confidence and reachability (the ADR-0025 KPIs), and signal recency (the
'why now'). Weights are pre-registered here, not tuned per query; every component ships in the
output, and a record with no mandate evidence says so instead of borrowing credibility from its
neighbours -- the per-record confidence tier is a function of EVIDENCE PRESENCE, not of score
magnitude, which is what lets the agent abstain honestly on thin records (Goal 2's actual test).
"""
from __future__ import annotations

import re
from datetime import date

from pipeline import db
from pipeline.rag.embed import embed_query
from pipeline.rag.retrieve import RECORD_COLUMNS, _attach_signals

# Pre-registered weights (sum 1.0). Chosen from component meaning before any goal was run:
# semantic affinity carries the mandate's own words; sector evidence is the strongest STATED
# signal; confidence/reachability are record-quality (ADR-0025); signals are recency color.
WEIGHTS = {"semantic": 0.35, "sector": 0.25, "confidence": 0.15, "reachability": 0.15,
           "signals": 0.10}
_WORD = re.compile(r"[a-z]{3,}")


# Tokens that appear in virtually every wealth-management blurb. Matching them is manufacturing
# evidence: "services" hit 15+ records on the first Goal-2 session and upgraded generic firms to
# "strong fit" for a HEALTHCARE mandate -- exactly the evidence-laundering the brief warns about.
_GENERIC = {"services", "service", "fund", "funds", "investment", "investments", "management",
            "capital", "partners", "group", "firm", "market", "markets", "sector", "sectors",
            "industry", "company", "companies", "business", "wealth", "asset", "assets",
            "equity", "strategies", "strategy", "office", "family"}


def _informative(term: str) -> list[str]:
    """The words in a mandate term that can actually evidence a fit ('healthcare services' ->
    ['healthcare']; 'services' -> [])."""
    return [w for w in _WORD.findall(term.lower()) if w not in _GENERIC]


def _sector_evidence(terms: list[str], rec: dict) -> tuple[float, bool, list[str]]:
    """Keyword overlap between mandate terms and the record's stated sectors/thesis/description.
    Returns (score, stated_sector_hit, evidence). Generic tokens never count; labeled approximate
    everywhere it surfaces (same honesty rule as the aggregate path)."""
    if not terms:
        return 0.0, False, []
    hay_sectors = " ".join(rec.get("investing_sectors") or []).lower()
    hay_prose = f"{rec.get('investment_thesis') or ''} {rec.get('description') or ''}".lower()
    hits, stated, where = 0.0, False, []
    informative_terms = 0
    for t in terms:
        words = _informative(t)
        if not words:
            continue  # a purely generic term can neither help nor hurt
        informative_terms += 1
        if any(w in hay_sectors for w in words):
            hits += 1.0
            stated = True
            where.append(f"stated sector matches '{' '.join(words)}'")
        elif any(w in hay_prose for w in words):
            hits += 0.5
            where.append(f"thesis/description mentions '{' '.join(words)}'")
    if informative_terms == 0:
        return 0.0, False, []
    return min(1.0, hits / informative_terms), stated, where


def _signal_recency(rec: dict) -> tuple[float, str | None]:
    sigs = rec.get("signals") or []
    if not sigs:
        return 0.0, None
    newest = max((s.get("signal_date") or "") for s in sigs)
    if not newest:
        return 0.0, None
    try:
        months = (date.today().year - int(newest[:4])) * 12 + date.today().month - int(newest[5:7])
    except (ValueError, IndexError):
        return 0.0, None
    if months <= 12:
        return 1.0, f"dated signal within 12 months ({newest})"
    if months <= 24:
        return 0.5, f"most recent signal {newest}"
    return 0.0, None


def fit_rank(mandate: str, *, sector_terms: list[str] | None = None,
             min_aum: int | None = None, max_aum: int | None = None, k: int = 10) -> dict:
    """Rank every qualifying record for an investor mandate. Returns ranked records, each with
    its component scores, evidence list, caveats, and an evidence-based confidence tier."""
    qvec = embed_query(mandate)
    lit = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            f"select {RECORD_COLUMNS}, r.reachability_score, r.is_stale, "
            "(d.embedding <=> %s::vector) as dist "
            "from gold.records r join gold.rag_docs d using (crd) "
            "where r.release_state = 'qualifying' and d.embedding is not null",
            (lit,))
        cols = [d[0] for d in cur.description]
        recs = [dict(zip(cols, row)) for row in cur.fetchall()]
        _attach_signals(cur, recs)

    ranked = []
    for r in recs:
        semantic = max(0.0, 1.0 - float(r.pop("dist")))
        sector, stated_hit, sector_ev = _sector_evidence(sector_terms or [], r)
        conf = (r.get("confidence_score") or 0) / 100.0
        reach = (r.get("reachability_score") or 0) / 100.0
        sig, sig_ev = _signal_recency(r)
        score = (WEIGHTS["semantic"] * semantic + WEIGHTS["sector"] * sector
                 + WEIGHTS["confidence"] * conf + WEIGHTS["reachability"] * reach
                 + WEIGHTS["signals"] * sig)

        evidence, caveats = list(sector_ev), []
        if sig_ev:
            evidence.append(sig_ev)
        aum = r.get("aum_usd")
        aum_note = None
        if min_aum or max_aum:
            if aum is None:
                caveats.append("AUM not stated in the record; size fit unknown")
            elif (min_aum and aum < min_aum) or (max_aum and aum > max_aum):
                aum_note = "outside the stated size band"
                caveats.append(f"AUM ${aum/1e6:,.0f}M is outside the requested band")
            else:
                evidence.append(f"AUM ${aum/1e6:,.0f}M within the requested band")

        # Confidence tier from EVIDENCE PRESENCE, not score magnitude: a high semantic score with
        # nothing stated is still a guess, and gets labeled like one. 'strong' requires a STATED
        # sector match -- a prose mention caps at moderate (measured: prose-token matching alone
        # laundered generic firms into strong healthcare fits on the first Goal-2 session).
        has_stated = bool(sector_ev) or bool(r.get("investment_thesis"))
        if stated_hit and (r.get("confidence_score") or 0) >= 90:
            tier = "strong"
        elif sector_ev:
            tier = "moderate"
        elif has_stated and semantic >= 0.45:
            tier = "weak"
            caveats.append("no mandate-specific evidence in the record; plausible on document "
                           "similarity only")
        else:
            tier = "insufficient_evidence"
            caveats.append("no stated sectors or thesis in the record -- fit cannot be evidenced; "
                           "ranking rests on document similarity alone")

        ranked.append({**{k_: r.get(k_) for k_ in (
            "crd", "family_office_name", "entity_category", "city", "state", "aum_usd",
            "investing_sectors", "investment_thesis", "primary_contact_name",
            "primary_contact_title", "primary_contact_email", "primary_email_grade",
            "reachability_tier", "confidence_score", "data_asof", "is_stale")},
            "signals": (r.get("signals") or [])[:2],
            "fit_score": round(score, 4),
            "components": {"semantic": round(semantic, 3), "sector": round(sector, 3),
                           "confidence": round(conf, 3), "reachability": round(reach, 3),
                           "signals": sig},
            "fit_confidence": tier, "evidence": evidence, "caveats": caveats,
            "aum_note": aum_note})
    ranked.sort(key=lambda x: -x["fit_score"])
    return {"mandate": mandate, "sector_terms": sector_terms or [],
            "weights": WEIGHTS, "considered": len(ranked), "ranked": ranked[:k],
            "method_note": ("deterministic weighted ranking over ALL qualifying records; sector "
                            "matching is keyword-based (approximate); confidence tier reflects "
                            "evidence presence, not score size")}
