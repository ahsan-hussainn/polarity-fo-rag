"""Grounded answer generation (ADR-0013). The honesty the dataset earns must survive the last mile:
the model answers ONLY from the retrieved gold records, cites firms by name, states each email's
verification grade, and says "not in the dataset" rather than inventing a firm, contact, or address.
"""
from __future__ import annotations

import os

from pipeline.rag.retrieve import hybrid

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gpt-4o-mini")

_GRADE = {"A": "verified deliverable", "B": "catch-all domain, plausible but unconfirmable",
          "C": "inferred, unconfirmed", "D": "inferred address invalid", "F": "no mail server"}

SYSTEM = (
    "You answer questions about family offices using ONLY the provided records. Rules:\n"
    "- Use only the records below. If they do not contain the answer, say so plainly. Never invent a "
    "firm, person, email, or fact.\n"
    "- Cite the family offices you use by name.\n"
    "- When you give a contact's email, state its verification grade in plain words so the reader "
    "knows the confidence (e.g. 'verified' vs 'inferred, unconfirmed'). Do not present an unverified "
    "email as confirmed.\n"
    "- Be concise."
)


def _render(hits: list[dict]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        loc = ", ".join(x for x in (h.get("city"), h.get("state")) if x)
        secs = ", ".join(h.get("investing_sectors") or [])
        email = h.get("primary_contact_email")
        grade = h.get("primary_email_grade")
        contact = "—"
        if h.get("primary_contact_name"):
            contact = f"{h['primary_contact_name']} ({h.get('primary_contact_title') or 'principal'})"
            if email:
                contact += f", {email} [{grade}: {_GRADE.get(grade, 'unknown')}]"
        lines.append(
            f"{i}. {h['family_office_name']} — {loc or 'location n/a'}"
            f"{'; founded ' + str(h['founded_year']) if h.get('founded_year') else ''}\n"
            f"   Sectors: {secs or 'n/a'}\n"
            f"   Thesis: {h.get('investment_thesis') or 'n/a'}\n"
            f"   Primary contact: {contact}")
    return "\n".join(lines)


def answer(query: str, k: int = 5) -> dict:
    """Retrieve, then ground an answer with citations. Returns {answer, sources}."""
    hits = hybrid(query, k=k)
    if not hits:
        return {"answer": "No matching family office is in the dataset for that query.",
                "sources": [], "query": query}
    from openai import OpenAI

    user = (f"Question: {query}\n\nRecords:\n{_render(hits)}\n\n"
            "Answer the question using only these records, citing firms by name.")
    resp = OpenAI().chat.completions.create(
        model=ANSWER_MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    return {
        "answer": resp.choices[0].message.content,
        "query": query,
        "sources": [{"firm": h["family_office_name"], "crd": h["crd"],
                     "contact": h.get("primary_contact_name"),
                     "email": h.get("primary_contact_email"),
                     "email_grade": h.get("primary_email_grade"),
                     "matched": h["matched"], "score": h["score"]} for h in hits],
    }
