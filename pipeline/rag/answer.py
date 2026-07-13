"""Grounded answer generation (ADR-0013, ADR-0016). The honesty the dataset earns must survive the
last mile -- and it must come out as intelligence, not a fact dump. The brief's own definition of an
actionable record is the answer template: WHOM to contact, WHY them, and HOW to reach them.

Routing (intent.py): lookups match the named firm directly (small k); aggregates run exact SQL over
gold.records so counts are true of the DATASET, not of a top-5 sample; discovery runs hybrid retrieval
with typed filters (state, AUM) as hard WHERE clauses. Outreach channel routing is computed HERE, in
Python, from the email grades -- deterministic, not left to the model: a D-grade email is routing
information (use the phone / the A-grade secondary / LinkedIn), not just bad news to report.
"""
from __future__ import annotations

import os

from pipeline.rag import intent as qi
from pipeline.rag.retrieve import by_filters, by_name, hybrid

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gpt-4o-mini")

_GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}  # ascending: best (verified) first


def _grade_key(h: dict) -> tuple:
    """Sort key: email grade ascending (A first), then retrieval score descending."""
    return (_GRADE_RANK.get(h.get("primary_email_grade"), 9), -h.get("score", 0))


def _aum_words(aum) -> str | None:
    if not aum:
        return None
    return f"${aum / 1e9:.1f}B" if aum >= 1_000_000_000 else f"${aum / 1e6:.0f}M"


def best_channel(h: dict) -> dict:
    """Deterministic outreach routing from the verification grades. Returns
    {channel, target, detail} -- the concrete 'how to reach them' for this record."""
    pg, sg = h.get("primary_email_grade"), h.get("secondary_email_grade")
    if pg in ("A", "B") and h.get("primary_contact_email"):
        sure = "verified" if pg == "A" else "plausible (catch-all domain, unconfirmable)"
        return {"channel": "email", "target": h["primary_contact_email"],
                "detail": f"email {h.get('primary_contact_name')} directly ({sure})"}
    if sg in ("A", "B") and h.get("secondary_contact_email"):
        sure = "verified" if sg == "A" else "plausible"
        return {"channel": "email", "target": h["secondary_contact_email"],
                "detail": (f"primary contact's email could not be verified -- go through "
                           f"{h.get('secondary_contact_name')} ({h.get('secondary_contact_title')}), "
                           f"whose address is {sure}")}
    if h.get("firm_phone"):
        return {"channel": "phone", "target": h["firm_phone"],
                "detail": "no deliverable email on record -- call the office line"}
    if h.get("corporate_linkedin"):
        return {"channel": "linkedin", "target": h["corporate_linkedin"],
                "detail": "no verified email or phone -- approach via the firm's LinkedIn"}
    return {"channel": "research", "target": h.get("website"),
            "detail": "no verified outreach channel on record"}


SYSTEM = (
    "You are a private-markets analyst advising a fund manager on which family offices to approach, "
    "using ONLY the provided records.\n"
    "Shape of every answer (write naturally -- no section headings, no labels):\n"
    "1. Open with one or two sentences that directly answer the question and name the strongest "
    "target and why (e.g. verified contact + thesis fit). Never open with a list.\n"
    "2. Then, for each relevant firm (numbered, strongest first), write a short paragraph that ties "
    "its thesis/sectors/AUM to the user's question -- not a recitation of every field -- and ends by "
    "saying exactly how to reach them, following the record's 'Recommended outreach' line and stating "
    "the verification status in plain words. Never present an unverified address as confirmed.\n"
    "3. Close with one concrete, analyst-style next step (whom to start with and why, or a sharper "
    "query the user could ask, e.g. narrowing by state or AUM).\n"
    "Hard rules:\n"
    "- Use only the records below; never invent a firm, person, email, number, or fact.\n"
    "- If a 'Dataset total' line is present, use THAT number for any count -- the listed records may "
    "be a subset.\n"
    "- If no record matches the criteria exactly, say so plainly, then offer the nearest records as "
    "closest options, clearly labelled as such.\n"
    "- Write in clear Markdown prose. Substantive, not padded."
)


def _render_one(i: int, h: dict) -> str:
    loc = ", ".join(x for x in (h.get("city"), h.get("state"), h.get("country")) if x)
    facts = [x for x in (loc or None,
                         f"founded {h['founded_year']}" if h.get("founded_year") else None,
                         f"AUM {_aum_words(h.get('aum_usd'))}" if h.get("aum_usd") else None) if x]
    lines = [f"{i}. {h['family_office_name']} ({' | '.join(facts) or 'details n/a'})"]
    if h.get("description"):
        lines.append(f"   About: {h['description']}")
    if h.get("investment_thesis"):
        lines.append(f"   Thesis: {h['investment_thesis']}")
    if h.get("investing_sectors"):
        lines.append(f"   Sectors: {', '.join(h['investing_sectors'])}")
    for role in ("primary", "secondary"):
        name = h.get(f"{role}_contact_name")
        if not name:
            continue
        line = f"   {role.capitalize()} contact: {name} ({h.get(f'{role}_contact_title') or 'principal'})"
        email, grade = h.get(f"{role}_contact_email"), h.get(f"{role}_email_grade")
        if email:
            line += f" -- {email} [grade {grade}: {h.get(f'{role}_email_explanation') or 'ungraded'}]"
        lines.append(line)
    extras = [x for x in (f"phone {h['firm_phone']}" if h.get("firm_phone") else None,
                          "corporate LinkedIn on file" if h.get("corporate_linkedin") else None,
                          h.get("website")) if x]
    if extras:
        lines.append(f"   Also on record: {'; '.join(extras)}")
    ch = best_channel(h)
    lines.append(f"   Recommended outreach: {ch['detail']}" +
                 (f" -> {ch['target']}" if ch.get("target") else ""))
    return "\n".join(lines)


def _render(hits: list[dict], total: int | None = None, method_note: str | None = None) -> str:
    parts = []
    if total is not None:
        parts.append(f"Dataset total matching the criteria: {total} record(s)."
                     + (f" ({method_note})" if method_note else ""))
    parts += [_render_one(i, h) for i, h in enumerate(hits, 1)]
    return "\n".join(parts)


def _sources(hits: list[dict]) -> list[dict]:
    out = []
    for h in sorted(hits, key=_grade_key):  # A-grade contacts first
        ch = best_channel(h)
        out.append({
            "firm": h["family_office_name"], "crd": h["crd"],
            "location": ", ".join(x for x in (h.get("city"), h.get("state")) if x) or None,
            "aum": _aum_words(h.get("aum_usd")),
            "contact": h.get("primary_contact_name"), "title": h.get("primary_contact_title"),
            "email": h.get("primary_contact_email"), "email_grade": h.get("primary_email_grade"),
            "secondary_contact": h.get("secondary_contact_name"),
            "secondary_email": h.get("secondary_contact_email"),
            "secondary_email_grade": h.get("secondary_email_grade"),
            "phone": h.get("firm_phone"), "linkedin": h.get("corporate_linkedin"),
            "website": h.get("website"), "adv_filing_url": h.get("adv_filing_url"),
            "best_channel": ch["channel"], "best_channel_target": ch.get("target"),
            "matched": h["matched"], "score": h["score"],
        })
    return out


def answer(query: str, k: int = 5) -> dict:
    """Classify -> route -> retrieve -> ground an analyst-shaped answer. Returns
    {answer, sources, query, intent}."""
    q = qi.classify(query)
    total = method_note = None

    if q.intent == "lookup" and q.firm_name:
        hits = by_name(q.firm_name) or hybrid(query, k=min(k, 3))
    elif q.intent == "aggregate":
        total, hits = by_filters(state=q.state, min_aum=q.min_aum_usd, max_aum=q.max_aum_usd,
                                 sector_term=q.sector_term, limit=15)
        if q.sector_term:
            method_note = (f"sector matched by keyword '{q.sector_term}' over sectors/thesis/"
                           "description -- approximate, unlike the exact state/AUM filters")
    else:
        hits = hybrid(query, k=k, state=q.state, min_aum=q.min_aum_usd, max_aum=q.max_aum_usd)
        if not hits and (q.state or q.min_aum_usd or q.max_aum_usd):
            # Honest fallback: nothing passes the hard filters -> retrieve unfiltered and tell the
            # model these are nearest matches, so the user gets options, clearly labelled.
            hits = hybrid(query, k=k)
            method_note = "no record passed the exact filters; records below are nearest matches only"

    if not hits:
        return {"answer": "No matching family office is in the dataset for that query.",
                "sources": [], "query": query, "intent": q.model_dump()}

    from openai import OpenAI

    user = (f"Question: {query}\n\nRecords:\n{_render(hits, total, method_note)}\n\n"
            "Answer as specified: verdict first, then the picks with outreach routing, then one "
            "next step.")
    resp = OpenAI().chat.completions.create(
        model=ANSWER_MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    return {"answer": resp.choices[0].message.content, "query": query,
            "intent": q.model_dump(), "sources": _sources(hits)}
