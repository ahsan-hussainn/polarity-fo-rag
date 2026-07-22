"""Entity adjudication machinery (ADR-0020): assemble evidence, draft proposals, apply decisions.

Three-step flow, deliberately separated so the human judgment is a real release control (the
mandate: "a review checklist is not evidence of review; the completed decisions are the evidence"):

  evidence-sheet  -- assemble, per gold firm, everything the pipeline already holds that bears on
                     WHAT the entity is: SEC ADV Item 5 client mix (regulatory, dated) and the
                     firm's own website text (span + URL + fetched_at). Writes a review sheet with
                     a DRAFT category proposal per firm. The draft is a proposal, never a decision.
  (human review)  -- Ahsan reviews/edits the sheet; every row he ratifies gets decided_by set.
  entity-apply    -- load the ratified sheet into gold.entity_adjudications, then rebuild gold so
                     release_state reflects the judgments.

Evidence classes (>=2 required to affirm, per ADR-0020):
  adv_item5   -- client counts/mix from the firm's own regulatory filing. An adviser reporting a
                 handful of HNW clients is consistent with a family office; hundreds of
                 (non-)HNW individuals is a wealth-management book, whatever the name says.
  website     -- what the firm says it IS (not services it mentions), as a quoted span with URL
                 and capture date. "We are a multi-family office" affirms; "family office
                 services" alone does not (the mandate: a span must support the MEANING).
  third_party -- press/directory corroboration, gathered manually where the first two conflict.

Scale note: at 50 firms the review is complete (mandate: full review of the originals); the same
sheet format is the stratified-review substrate for the Stage 2 additions.
"""
from __future__ import annotations

import csv
import json
import os
import re

from pipeline import db

SHEET = "data/curation/entity_adjudication_sheet.json"
DECISIONS = "data/curation/entity_adjudications.json"
CONTACT_DECISIONS = "data/curation/contact_adjudications.json"

# Phrases that speak to what the firm IS. Order matters: first match wins the draft proposal.
_SELF_DESC = [
    ("single_family_office", re.compile(r"\b(single[- ]family office|serv\w+ (one|a single) family)\b", re.I)),
    ("multi_family_office", re.compile(r"\bmulti[- ]family office\b", re.I)),
    ("ria_with_fo_practice", re.compile(r"\bfamily office (services|practice|group|division)\b", re.I)),
    ("wealth_manager", re.compile(r"\b(wealth management firm|registered investment advis[oe]r|investment management firm)\b", re.I)),
]


def _spans(text: str, pat: re.Pattern, width: int = 160) -> list[str]:
    """Quoted evidence spans around each match -- what the reviewer reads, what the record cites."""
    out = []
    for m in pat.finditer(text or ""):
        a, b = max(0, m.start() - width // 2), min(len(text), m.end() + width // 2)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
    return out[:3]


def _adv_evidence(cur, crd: str) -> dict | None:
    cur.execute("select raw->>'hnw_clients', raw->>'nonhnw_clients', raw->>'hnw_raum', "
                "raw->>'raum_total', raw->>'total_employees', raw->>'org_form', "
                "raw->>'latest_filing_date', source_url "
                "from bronze.captures where source='sec_form_adv' and entity_key=%s limit 1", (crd,))
    r = cur.fetchone()
    if not r:
        return None
    hnw, nonhnw, hnw_raum, raum, emp, org, filed, url = r
    return {"class": "adv_item5", "source_url": url, "observed_at": filed,
            "detail": {"hnw_clients": hnw, "nonhnw_clients": nonhnw, "hnw_raum": hnw_raum,
                       "raum_total": raum, "total_employees": emp, "org_form": org}}


def _website_evidence(cur, crd: str) -> tuple[list[dict], str | None]:
    """All self-description spans found in the firm's captured pages + the draft category the
    strongest span suggests. Home/about pages are read first (most identity-bearing)."""
    cur.execute("select raw->>'page_type', raw->>'page_url', raw->>'text', fetched_at::date "
                "from bronze.captures where source='website' and entity_key=%s "
                "order by case raw->>'page_type' when 'home' then 0 when 'about' then 1 else 2 end",
                (crd,))
    ev, draft = [], None
    for ptype, purl, text, fetched in cur.fetchall():
        for cat, pat in _SELF_DESC:
            for span in _spans(text, pat):
                ev.append({"class": "website", "source_url": purl, "observed_at": str(fetched),
                           "detail": {"page_type": ptype, "category_signal": cat, "span": span}})
                draft = draft or cat
    return ev, draft


def _draft(adv: dict | None, web_cat: str | None) -> tuple[str, str]:
    """Combine the two evidence classes into a DRAFT (category, note). Client-mix sharpens or
    contradicts the self-description; contradictions are surfaced, not resolved silently."""
    hnw = int(adv["detail"]["hnw_clients"] or 0) if adv else 0
    nonhnw = int(adv["detail"]["nonhnw_clients"] or 0) if adv else 0
    total = hnw + nonhnw
    if web_cat == "single_family_office":
        return web_cat, "self-described SFO" + (f"; ADV reports {total} individual clients (check: >5 contradicts one-family claim)" if total > 5 else "; client count consistent")
    if web_cat == "multi_family_office":
        if total > 100:
            return "wealth_manager", f"self-described MFO but ADV reports {total} individual clients -- a retail-scale book; propose wealth_manager, review the spans"
        return web_cat, f"self-described MFO; ADV individual clients={total}"
    if web_cat in ("ria_with_fo_practice", "wealth_manager"):
        return web_cat, f"website signals {web_cat}; ADV individual clients={total}"
    # no self-description found: propose from client mix alone (single evidence class -> unresolved)
    if total and total <= 10 and hnw >= nonhnw:
        return "unresolved", f"no self-description span; ADV client mix ({hnw} HNW / {nonhnw} non-HNW) is FO-consistent but one evidence class cannot affirm"
    return "unresolved", f"no self-description span; ADV individual clients={total}"


def evidence_sheet(path: str = SHEET) -> dict:
    """Assemble the per-firm evidence + draft proposals for human review. Duplicate domains are
    flagged for identity resolution (two records for one entity are one record)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, family_office_name, domain from gold.records order by family_office_name")
        firms = cur.fetchall()
        by_domain: dict[str, list[str]] = {}
        for crd, _, dom in firms:
            if dom:
                by_domain.setdefault(dom.lower(), []).append(crd)
        for crd, name, dom in firms:
            adv = _adv_evidence(cur, crd)
            web_ev, web_cat = _website_evidence(cur, crd)
            cat, note = _draft(adv, web_cat)
            dupes = [x for x in by_domain.get((dom or "").lower(), []) if x != crd]
            if dupes:
                note += f" | DOMAIN SHARED with CRD {','.join(dupes)}: resolve identity (ADR-0020)"
            rows.append({
                "crd": crd, "firm_name": name, "domain": dom,
                "draft_category": cat, "draft_note": note,
                "evidence": ([adv] if adv else []) + web_ev,
                # fields the human review fills in; apply() refuses rows without decided_by
                "category": cat, "status": "unresolved", "duplicate_of": None,
                "rationale": "", "decided_by": None,
            })
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, default=str)
    return {"firms": len(rows), "path": path,
            "draft_categories": {c: sum(1 for r in rows if r["draft_category"] == c)
                                 for c in {r["draft_category"] for r in rows}}}


def apply(path: str = DECISIONS, write: bool = False) -> dict:
    """Load ratified decisions into gold.entity_adjudications. Refuses rows without decided_by --
    an unratified proposal must not become a release decision. Affirmed rows need >=2 evidence
    classes (ADR-0020); rows failing that are loaded as 'unresolved' and reported."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {"applied": 0, "skipped_unratified": 0, "demoted_single_class": 0, "written": write}
    with db.get_conn() as c, c.cursor() as cur:
        for r in rows:
            if not r.get("decided_by"):
                out["skipped_unratified"] += 1
                continue
            status, cat = r["status"], r.get("category")
            classes = {e["class"] for e in r.get("evidence", [])}
            if status == "affirmed" and len(classes) < 2:
                status, cat = "unresolved", "unresolved"
                out["demoted_single_class"] += 1
            if write:
                cur.execute(
                    "insert into gold.entity_adjudications "
                    "(crd, firm_name, category, status, duplicate_of, evidence, rationale, decided_by) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (crd) do update set "
                    "category=excluded.category, status=excluded.status, "
                    "duplicate_of=excluded.duplicate_of, evidence=excluded.evidence, "
                    "rationale=excluded.rationale, decided_by=excluded.decided_by, decided_at=now()",
                    (r["crd"], r["firm_name"], cat, status, r.get("duplicate_of"),
                     json.dumps(r.get("evidence", []), default=str), r["rationale"], r["decided_by"]))
            out["applied"] += 1
        if write:
            c.commit()
    return out


def apply_contacts(path: str = CONTACT_DECISIONS, write: bool = False) -> dict:
    """Load ratified contact adjudications (ADR-0021/0022) into gold.contact_adjudications. Refuses
    rows without decided_by. build.py reads this to select the product's primary/secondary contact,
    label authority, and gate qualification."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {"applied": 0, "skipped_unratified": 0, "with_published_email": 0, "written": write}
    with db.get_conn() as c, c.cursor() as cur:
        for r in rows:
            if not r.get("decided_by"):
                out["skipped_unratified"] += 1
                continue
            if r.get("published_email"):
                out["with_published_email"] += 1
            if write:
                cur.execute(
                    "insert into gold.contact_adjudications "
                    "(crd, contact_role, name, title, selection_basis, authority_basis, "
                    " affiliation_asof, published_email, evidence, decided_by) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "on conflict (crd, contact_role) do update set "
                    "name=excluded.name, title=excluded.title, selection_basis=excluded.selection_basis, "
                    "authority_basis=excluded.authority_basis, affiliation_asof=excluded.affiliation_asof, "
                    "published_email=excluded.published_email, evidence=excluded.evidence, "
                    "decided_by=excluded.decided_by, decided_at=now()",
                    (r["crd"], r["contact_role"], r["name"], r["title"], r["selection_basis"],
                     r["authority_basis"], r["affiliation_asof"], r.get("published_email"),
                     json.dumps(r.get("evidence", []), default=str), r["decided_by"]))
            out["applied"] += 1
        if write:
            c.commit()
    return out


def verify_contacts(write: bool = False, limit: int | None = None) -> dict:
    """WS3b (ADR-0021/0010): for each ratified contact WITHOUT a published address, infer the pattern
    for that proven person against the firm's domain and verify it via the email API. Stores the
    honest grade so build.py can offer a reachable-but-precisely-labeled email. Published-address
    contacts are skipped (already proven). D/F verdicts are recorded but never released."""
    from pipeline.verify.api import get_verifier
    from pipeline.verify.email import resolve_via_api

    verifier = get_verifier()
    out = {"checked": 0, "graded": {}, "written": write}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select ca.crd, ca.contact_role, ca.name, r.domain "
                    "from gold.contact_adjudications ca join gold.records r using (crd) "
                    "where ca.published_email is null and ca.inferred_grade is null "
                    "and ca.name is not null and r.domain is not null "
                    "order by ca.crd, ca.contact_role" + (f" limit {int(limit)}" if limit else ""))
        todo = cur.fetchall()
        for crd, role, name, domain in todo:
            res = resolve_via_api(name, domain, verifier)
            out["checked"] += 1
            out["graded"][res.grade] = out["graded"].get(res.grade, 0) + 1
            if write:
                cur.execute(
                    "update gold.contact_adjudications set inferred_email=%s, inferred_grade=%s, "
                    "inferred_code=%s, inferred_explanation=%s, inferred_evidence=%s "
                    "where crd=%s and contact_role=%s",
                    (res.email, res.grade, res.code, res.explanation,
                     json.dumps(res.evidence, default=str), crd, role))
        if write:
            c.commit()
    return out


SIGNAL_DECISIONS = "data/curation/record_signals.json"


def apply_signals(path: str = SIGNAL_DECISIONS, write: bool = False) -> dict:
    """Load ratified time-sensitive signals (correction #6) into gold.record_signals. Refuses rows
    without decided_by; each signal must carry a date and a source_url (the basis)."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {"applied": 0, "skipped": 0, "firms_with_signals": 0, "written": write}
    seen_firms = set()
    with db.get_conn() as c, c.cursor() as cur:
        if write:
            cur.execute("truncate gold.record_signals")  # full re-population from the ratified file
        for r in rows:
            if not r.get("decided_by") or not r.get("signal_date") or not r.get("source_url"):
                out["skipped"] += 1
                continue
            seen_firms.add(r["crd"])
            if write:
                cur.execute(
                    "insert into gold.record_signals (crd, signal_type, description, signal_date, "
                    "source_url, decided_by) values (%s,%s,%s,%s,%s,%s) "
                    "on conflict (crd, description) do nothing",
                    (r["crd"], r["signal_type"], r["description"], r["signal_date"],
                     r["source_url"], r["decided_by"]))
            out["applied"] += 1
        if write:
            c.commit()
    out["firms_with_signals"] = len(seen_firms)
    return out
