"""Stage 3 persistence: bronze 'website' captures -> silver.firms + silver.people (ADR-0009).

Bronze holds one append-only row per fetched PAGE. This module does the entity resolution the
silver layer is defined by: it groups a firm's pages by CRD, combines their text into one document,
runs it through the ADR-0008 extraction seam, and writes exactly one silver.firms row per firm plus
one silver.people row per named person. The extraction seam decides the provider (openai | mock);
this module never learns which model produced the answer.

Provenance is preserved end-to-end: every silver.firms row records the source_urls and bronze_ids it
was built from, so any extracted cell traces back to the raw capture it came from (ADR-0003/0006).
The validation-layer columns on silver.people (email_status, email_verification, quality_grade) are
left NULL here -- believed facts only; verification is a later stage.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

from pipeline import db
from pipeline.silver import extract as ex

# Page reading order when we stitch a firm's pages into one extraction document. Home/about/strategy
# carry the thesis + overview; team/contact carry the people. All are included, most-informative
# first, then the whole document is capped so a sprawling site cannot blow up the token bill.
_PAGE_ORDER = {"home": 0, "about": 1, "strategy": 2, "team": 3, "contact": 4}
MAX_DOC_CHARS = 16_000


def _reg_domain(url: str | None) -> str | None:
    if not url:
        return None
    net = urlparse(url).netloc.lower().removeprefix("www.")
    return net or None


def _firms_from_bronze(limit: int | None) -> list[dict]:
    """Group bronze 'website' captures into per-firm bundles (one bundle per CRD)."""
    sql = (
        "select id, entity_key, raw->>'firm_name', raw->>'page_type', raw->>'page_url', "
        "       raw->>'title', raw->>'text' "
        "from bronze.captures where source = 'website' and coalesce(raw->>'text','') <> '' "
        "order by entity_key, id"
    )
    firms: dict[str, dict] = {}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        for bid, crd, name, ptype, url, title, text in cur.fetchall():
            f = firms.setdefault(crd, {"crd": crd, "firm_name": name, "pages": []})
            f["pages"].append({"bronze_id": bid, "page_type": ptype or "home",
                               "url": url, "title": title, "text": text})
    ordered = list(firms.values())
    return ordered[:limit] if limit else ordered


def _combine(pages: list[dict]) -> tuple[str, list[str], list[int], str | None]:
    """Stitch a firm's pages into one document; return (text, source_urls, bronze_ids, home_url)."""
    pages = sorted(pages, key=lambda p: _PAGE_ORDER.get(p["page_type"], 9))
    home = next((p["url"] for p in pages if p["page_type"] == "home"), pages[0]["url"])
    chunks, urls, ids, total = [], [], [], 0
    for p in pages:
        urls.append(p["url"])
        ids.append(p["bronze_id"])
        header = f"\n\n=== [{p['page_type']}] {p.get('title') or ''} ===\n"
        body = p["text"][: MAX_DOC_CHARS - total] if total < MAX_DOC_CHARS else ""
        if body:
            chunks.append(header + body)
            total += len(body)
    return "".join(chunks).strip(), urls, ids, home


def _persist(firm: dict, result: ex.ExtractionResult, urls: list[str], ids: list[int],
             home: str | None) -> int:
    """Upsert one firm and replace its people. Returns the number of people written."""
    e = result.extraction
    by = f"{result.provider}:{result.model}"
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "insert into silver.firms"
            " (crd, firm_name, domain, thesis, description, sectors, founded_year,"
            "  source_urls, bronze_ids, extracted_by, extraction_usage)"
            " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
            " on conflict (crd) do update set"
            "  firm_name=excluded.firm_name, domain=excluded.domain, thesis=excluded.thesis,"
            "  description=excluded.description, sectors=excluded.sectors,"
            "  founded_year=excluded.founded_year, source_urls=excluded.source_urls,"
            "  bronze_ids=excluded.bronze_ids, extracted_by=excluded.extracted_by,"
            "  extraction_usage=excluded.extraction_usage, extracted_at=now()",
            (firm["crd"], firm["firm_name"], _reg_domain(home), e.thesis, e.description,
             e.sectors, e.founded_year, urls, ids, by,
             json.dumps(result.usage, ensure_ascii=False)),
        )
        # People: extraction is the source of truth for the roster, so replace wholesale on re-run.
        cur.execute("delete from silver.people where firm_crd = %s", (firm["crd"],))
        for m in e.team:
            cur.execute(
                "insert into silver.people"
                " (firm_crd, name, title, is_principal, principal_reason, source_url, extracted_by)"
                " values (%s,%s,%s,%s,%s,%s,%s)",
                (firm["crd"], m.name, m.title, m.is_principal, m.principal_reason, home, by),
            )
        c.commit()
    return len(e.team)


def run(provider: str | None = None, *, limit: int | None = None, write: bool = False) -> dict:
    """Build silver from bronze website captures. Extracts always; persists only if write=True."""
    extractor = ex.get_extractor(provider)
    firms = _firms_from_bronze(limit)
    out = {"provider": extractor.name, "written": write, "firms": [],
           "firms_processed": 0, "people": 0, "principals": 0,
           "input_tokens": 0, "output_tokens": 0}

    for firm in firms:
        text, urls, ids, home = _combine(firm["pages"])
        result = extractor.extract(text, source_url=home)
        e = result.extraction
        principals = sum(1 for m in e.team if m.is_principal)
        if write:
            _persist(firm, result, urls, ids, home)

        usage = result.usage or {}
        out["input_tokens"] += usage.get("prompt_tokens", 0)
        out["output_tokens"] += usage.get("completion_tokens", 0)
        out["firms_processed"] += 1
        out["people"] += len(e.team)
        out["principals"] += principals
        out["firms"].append({
            "crd": firm["crd"], "firm_name": firm["firm_name"], "pages": len(firm["pages"]),
            "founded_year": e.founded_year, "sectors": e.sectors,
            "team": len(e.team), "principals": principals,
            "thesis": (e.thesis or "")[:100] + ("…" if e.thesis and len(e.thesis) > 100 else ""),
        })
    return out
