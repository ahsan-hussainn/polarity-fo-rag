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
import re

from pipeline.rag import intent as qi
from pipeline.rag.retrieve import by_filters, by_name, hybrid

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gpt-4o-mini")

# Out-of-scope relevance floor (ADR-0026). If the NEAREST qualifying record is farther than this in
# cosine distance, the query is not about the family-office dataset and we refuse rather than pitch the
# top-k anyway. Pre-registered at the midpoint of the observed separation gap between in-scope queries
# (nearest 0.24-0.50) and out-of-scope queries (nearest 0.79-1.00) -- chosen from the structure of the
# gap, not tuned to the eval. Env-overridable so the floor is a knob, not a magic number in code.
RELEVANCE_FLOOR = float(os.getenv("RAG_RELEVANCE_FLOOR", "0.64"))

# Ascending: best email basis first. PUB (firm-published, proven) outranks A (vendor-deliverable but
# inferred) > B (catch-all) > C (unconfirmed). D/F are quarantined and never reach a source card.
_GRADE_RANK = {"PUB": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}


def _is_fo(h: dict) -> bool:
    return h.get("entity_category") in ("single_family_office", "multi_family_office")


def _grade_key(h: dict) -> tuple:
    """Sort key: affirmed family offices first (policy: non-FOs are kept but never LEAD an answer),
    then email grade ascending (PUB/A first), then retrieval score descending."""
    return (0 if _is_fo(h) else 1, _GRADE_RANK.get(h.get("primary_email_grade"), 9), -h.get("score", 0))


def _aum_words(aum) -> str | None:
    if not aum:
        return None
    return f"${aum / 1e9:.1f}B" if aum >= 1_000_000_000 else f"${aum / 1e6:.0f}M"


# How precisely to describe each email grade to the customer (mandate: narrowest accurate wording).
_EMAIL_SURE = {
    "PUB": "published by the firm for this person",
    "A": "vendor-reported deliverable for an inferred address (not proven to be this person's mailbox)",
    "B": "plausible inference on a catch-all domain, unconfirmable",
}


def best_channel(h: dict) -> dict:
    """Deterministic outreach routing from the email grades. Returns {channel, target, detail} --
    the concrete 'how to reach them'. A published individual address (PUB) is the strongest channel;
    a vendor-deliverable inferred address (A) or catch-all (B) is emailable but honestly qualified."""
    pg, sg = h.get("primary_email_grade"), h.get("secondary_email_grade")
    if pg in ("PUB", "A", "B") and h.get("primary_contact_email"):
        return {"channel": "email", "target": h["primary_contact_email"],
                "detail": f"email {h.get('primary_contact_name')} directly ({_EMAIL_SURE[pg]})"}
    if sg in ("PUB", "A", "B") and h.get("secondary_contact_email"):
        return {"channel": "email", "target": h["secondary_contact_email"],
                "detail": (f"no reachable address for the primary contact -- go through "
                           f"{h.get('secondary_contact_name')} ({h.get('secondary_contact_title')}), "
                           f"whose address is {_EMAIL_SURE[sg]}")}
    if h.get("firm_phone"):
        return {"channel": "phone", "target": h["firm_phone"],
                "detail": "no deliverable email on record -- call the office line"}
    if h.get("corporate_linkedin"):
        return {"channel": "linkedin", "target": h["corporate_linkedin"],
                "detail": "no reachable email or phone -- approach via the firm's LinkedIn"}
    return {"channel": "research", "target": h.get("website"),
            "detail": "no confirmed outreach channel on record"}


SYSTEM = (
    "You are a private-markets analyst advising a fund manager on which family offices to approach, "
    "using ONLY the provided records.\n"
    "Shape of every answer (write naturally -- no section headings, no labels):\n"
    "1. Open with one or two sentences that directly answer the question and name the strongest "
    "target and why (e.g. a firm-published or vendor-checked contact + thesis fit). Never open with "
    "a list.\n"
    "2. Then, for each relevant firm (numbered, strongest first), write a short paragraph that ties "
    "its thesis/sectors/AUM to the user's question -- not a recitation of every field -- and ends by "
    "saying exactly how to reach them, following the record's 'Recommended outreach' line and stating "
    "the verification status in plain words. Never present an unverified address as confirmed.\n"
    "3. Close with one concrete, analyst-style next step (whom to start with and why, or a sharper "
    "query the user could ask, e.g. narrowing by state or AUM).\n"
    "- WHY NOW: if a record has a 'Recent signal' line (a dated, sourced event -- a raise, hire, "
    "merger, award), weave it in as the timely reason to reach out now. Never invent a signal; use "
    "only the ones listed.\n"
    "Hard rules:\n"
    "- Use only the records below; never invent a firm, person, email, number, or fact.\n"
    "- ENTITY HONESTY: each record has an 'Entity type'. Lead with affirmed family offices. A record "
    "marked 'wealth manager' or 'RIA with a family-office practice' is NOT a family office -- if you "
    "mention it, say so plainly and never call it a family office. Do not present a non-FO as a "
    "family office to satisfy the question.\n"
    "- If a 'Dataset total' line is present, use THAT number for any count -- the listed records may "
    "be a subset.\n"
    "- If no record matches the criteria exactly, say so plainly, then offer the nearest records as "
    "closest options, clearly labelled as such.\n"
    "- Email honesty (use the record's grade, never the word 'verified' loosely): PUB = an address "
    "the firm itself publishes for this person (the strongest -- say 'firm-published'); A = an "
    "inferred pattern a vendor reported deliverable (say 'vendor-checked, but an inferred address "
    "not confirmed as theirs'); B = inferred on a catch-all domain ('plausible, unconfirmable'); "
    "C = inferred, unconfirmed. Never call a phone, LinkedIn page, or the record itself 'verified'. "
    "Phone numbers come from the firm's SEC filing -- say exactly that.\n"
    "- Each contact was selected as the firm's allocation-authority decision-maker; where the "
    "record's authority basis is 'title_inferred', say the authority is inferred from title.\n"
    "- Write in clear Markdown prose. Substantive, not padded.\n"
    "- Make the signal scannable: **bold** every load-bearing fact -- the firm name at the start of "
    "its item, contact names, email addresses, phone numbers, AUM figures, and city/state. A reader "
    "skimming should be able to pick out whom to contact and how without reading every sentence. "
    "Bold only facts, not whole sentences."
)


# Plain labels for the entity category (ADR-0023: never present a non-FO as a family office).
_CATEGORY_LABEL = {
    "multi_family_office": "multi-family office", "single_family_office": "single-family office",
    "wealth_manager": "wealth manager (NOT a family office)",
    "ria_with_fo_practice": "RIA with a family-office practice (NOT a family office)",
}


def _render_one(i: int, h: dict) -> str:
    loc = ", ".join(x for x in (h.get("city"), h.get("state"), h.get("country")) if x)
    facts = [x for x in (loc or None,
                         f"founded {h['founded_year']}" if h.get("founded_year") else None,
                         f"AUM {_aum_words(h.get('aum_usd'))}" if h.get("aum_usd") else None) if x]
    lines = [f"{i}. {h['family_office_name']} ({' | '.join(facts) or 'details n/a'})"]
    cat = _CATEGORY_LABEL.get(h.get("entity_category"))
    if cat:
        lines.append(f"   Entity type: {cat}")
    if h.get("primary_selection_basis"):
        lines.append(f"   Why this contact: {h['primary_selection_basis']}")
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
    for s in (h.get("signals") or [])[:2]:  # the 'why now' -- dated, sourced recent events
        lines.append(f"   Recent signal ({s['date']}, {s['type']}): {s['description']}")
    return "\n".join(lines)


def _render(hits: list[dict], total: int | None = None, method_note: str | None = None) -> str:
    parts = []
    if total is not None:
        parts.append(f"Dataset total matching the criteria: {total} record(s)."
                     + (f" ({method_note})" if method_note else ""))
    # affirmed family offices lead the record list handed to the model (policy: non-FOs never lead)
    ordered = sorted(hits, key=lambda h: (0 if _is_fo(h) else 1, -h.get("score", 0)))
    parts += [_render_one(i, h) for i, h in enumerate(ordered, 1)]
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
            "entity_category": h.get("entity_category"),
            "is_family_office": h.get("entity_category") in ("single_family_office", "multi_family_office"),
            "selection_basis": h.get("primary_selection_basis"),
            "authority_basis": h.get("primary_authority_basis"),
            "reachability": h.get("reachability_tier"), "confidence": h.get("confidence_score"),
            "signals": (h.get("signals") or [])[:2],
            "matched": h["matched"], "score": h["score"],
        })
    return out


def _route(query: str, k: int) -> tuple:
    """Classify -> relevance-gate -> retrieve. Returns (intent, hits, total, method_note, out_of_scope).

    The classify call and the query embedding are independent network round-trips (~2s + ~1s), so
    they run CONCURRENTLY (ADR-0017): the embedding is computed speculatively while classification
    decides the route. The embedding is now ALWAYS used -- for the out-of-scope relevance floor
    (ADR-0026) that runs on every path before routing -- and again for discovery retrieval.

    Out-of-scope floor: before routing, we ask whether the query is about the family-office dataset at
    all (nearest_distance over ALL qualifying records). If the nearest record is beyond RELEVANCE_FLOOR
    (or the index is empty), we return out_of_scope=True with no hits, so the answer layer refuses
    instead of pitching the top-k. This closes the hole where 'discovery' was a catch-all that returned
    firms for any query, and where an out-of-scope COUNT ('how many countries in Africa') would be
    answered off the dataset total via the aggregate path."""
    from concurrent.futures import ThreadPoolExecutor

    from pipeline.rag.embed import embed_query
    from pipeline.rag.retrieve import nearest_distance

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_vec = ex.submit(embed_query, query)     # used for the floor AND (on discovery) retrieval
        q = qi.classify(query)
        qvec = f_vec.result()
        total = method_note = None

        nd = nearest_distance(qvec)
        if nd is None or nd > RELEVANCE_FLOOR:     # not about the dataset -> refuse, don't improvise
            return q, [], None, None, True

        if q.intent == "lookup" and q.firm_name:
            hits = by_name(q.firm_name) or hybrid(query, k=min(k, 3), qvec=qvec)
        elif q.intent == "aggregate":
            total, hits = by_filters(state=q.state, min_aum=q.min_aum_usd, max_aum=q.max_aum_usd,
                                     sector_term=q.sector_term, limit=15)
            if q.sector_term:
                method_note = (f"sector matched by keyword '{q.sector_term}' over sectors/thesis/"
                               "description -- approximate, unlike the exact state/AUM filters")
        else:
            hits = hybrid(query, k=k, state=q.state, min_aum=q.min_aum_usd, max_aum=q.max_aum_usd,
                          qvec=qvec)
            if not hits and (q.state or q.min_aum_usd or q.max_aum_usd):
                # Honest fallback: nothing passes the hard filters -> retrieve unfiltered and tell
                # the model these are nearest matches, so the user gets options, clearly labelled.
                hits = hybrid(query, k=k, qvec=qvec)
                method_note = ("no record passed the exact filters; records below are nearest "
                               "matches only")
    return q, hits, total, method_note, False


def _messages(query: str, hits: list[dict], total, method_note, repair: list[str] | None = None) -> list[dict]:
    user = (f"Question: {query}\n\nRecords:\n{_render(hits, total, method_note)}\n\n"
            "Answer as specified: verdict first, then the picks with outreach routing, then one "
            "next step.")
    if repair:  # second attempt: name the exact grounding failures the first answer must not repeat
        allowed = ", ".join(sorted({e for h in hits for e in
                                    (h.get("primary_contact_email"), h.get("secondary_contact_email")) if e})) or "none"
        user += ("\n\nYour previous answer FAILED an independent grounding check: "
                 + "; ".join(repair)
                 + f".\nThe ONLY email addresses you may write are: {allowed}. Do not state any other "
                 "address. Do not name any firm not listed above. Rewrite the answer within these limits.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


_NO_MATCH = "No matching family office is in the dataset for that query."

# Out-of-scope refusal (ADR-0026): the query is not about the family-office dataset. Say what the
# system does answer, so the refusal is useful, not a dead end. Narrowest accurate wording (mandate #7).
_OUT_OF_SCOPE = (
    "That question is outside what this dataset covers, so I don't have grounded records to answer it. "
    "I answer questions about the family offices in this dataset -- which firms to approach, who the "
    "decision-maker is, and how to reach them. Try asking about a firm, a location, an AUM range, or a "
    "sector."
)


def _compose(query: str, hits: list[dict], total, method_note) -> tuple[str, dict]:
    """Generate -> independently check -> repair-once-or-refuse (ADR-0023). Returns
    (released_text, verification). The final text is one the deterministic check passed, or a safe
    grounded fallback -- never an answer that failed the check. Logs the verdict so the control is
    visible in real runs."""
    import logging

    from pipeline.rag import checkanswer
    from pipeline.rag.oai import client

    log = logging.getLogger("rag.answer")
    text = client().chat.completions.create(
        model=ANSWER_MODEL, temperature=0,
        messages=_messages(query, hits, total, method_note)).choices[0].message.content or ""
    v = checkanswer.check(text, hits, total)
    verification = {"passed": v.ok, "failures": v.failures, "warnings": v.warnings, "repaired": False}
    if not v.ok:
        log.warning("grounding check FAILED for %r: %s -- repairing", query, v.failures)
        text2 = client().chat.completions.create(
            model=ANSWER_MODEL, temperature=0,
            messages=_messages(query, hits, total, method_note, repair=v.failures)
        ).choices[0].message.content or ""
        v2 = checkanswer.check(text2, hits, total)
        verification = {"passed": v2.ok, "failures": v2.failures, "warnings": v2.warnings, "repaired": True}
        if v2.ok:
            text = text2
        else:  # still ungrounded -> refuse rather than ship it (a check must control release)
            log.error("grounding check FAILED after repair for %r: %s -- refusing", query, v2.failures)
            names = ", ".join(f"**{h['family_office_name']}**" for h in hits[:5])
            text = ("I can't produce a fully grounded answer for that from the dataset without risking "
                    f"an unsupported detail. The records retrieved were: {names}. Please narrow the "
                    "query, or ask about one of these firms directly.")
    else:
        log.info("grounding check passed for %r (%d warnings)", query, len(v.warnings))
    return text, verification


def answer(query: str, k: int = 5) -> dict:
    """Classify -> route -> retrieve -> ground -> INDEPENDENTLY CHECK before release (ADR-0023).
    Returns {answer, sources, query, intent, verification}. Non-streaming; CLI/API/eval use this."""
    q, hits, total, method_note, oos = _route(query, k)
    if oos:
        return {"answer": _OUT_OF_SCOPE, "sources": [], "query": query, "intent": q.model_dump(),
                "verification": {"passed": True, "failures": [], "warnings": [], "repaired": False}}
    if not hits:
        return {"answer": _NO_MATCH, "sources": [], "query": query, "intent": q.model_dump(),
                "verification": {"passed": True, "failures": [], "warnings": [], "repaired": False}}
    text, verification = _compose(query, hits, total, method_note)
    return {"answer": text, "query": query, "intent": q.model_dump(),
            "sources": _sources(hits), "verification": verification}


def answer_stream(query: str, k: int = 5):
    """Streaming variant (ADR-0017/0023): yields NDJSON events. Order: {"type":"meta"} ships intent +
    sources as soon as retrieval finishes (the coverage cards render immediately), then the answer is
    composed AND passed through the independent grounding check BEFORE any text is released, then
    {"type":"delta"} chunks stream the CHECKED text, then {"type":"done"} carries the verification
    verdict. Grounding is enforced before release, not merely prompted (correction #5); the cost is
    that first-text paint waits for the check rather than for the first generated token."""
    q, hits, total, method_note, oos = _route(query, k)
    if oos or not hits:
        yield {"type": "meta", "query": query, "intent": q.model_dump(), "sources": []}
        yield {"type": "delta", "text": _OUT_OF_SCOPE if oos else _NO_MATCH}
        yield {"type": "done", "verification": {"passed": True, "failures": [], "warnings": [], "repaired": False}}
        return
    yield {"type": "meta", "query": query, "intent": q.model_dump(), "sources": _sources(hits)}
    text, verification = _compose(query, hits, total, method_note)
    for para in re.split(r"(?<=\n)", text):  # stream the released text in natural chunks
        if para:
            yield {"type": "delta", "text": para}
    yield {"type": "done", "verification": verification}
