"""Gate review: turn automated affirms into ratified adjudications (ADR-0029's release control).

ADR-0029 measured the gate's affirm precision at ~59% and drew the conclusion in the open: an
affirm is TRIAGE, not release. This module is the other half of that sentence -- the path by which
a triaged candidate becomes a counted record, and the only path there is.

  gate-review   -- assemble, per gate decision, everything that bears on WHAT the entity is, in the
                   ADR-0020 evidence shape (adv_item5 + website spans), alongside the gate's own
                   scored rule trail so the reviewer can see what the machine saw and where it may
                   have been credulous. Writes a sheet with a DRAFT category. A draft is a proposal.
  (human review) -- Ahsan reads the sheet, edits status/category/rationale, sets decided_by.
  gate-ratify   -- load the ratified rows into gold.entity_adjudications (refusing anything without
                   decided_by), then PROMOTE: build silver for exactly those firms and rebuild gold,
                   so a ratified firm enters the product through the standard build path.

The evidence bar is ADR-0020's, unchanged and re-enforced here: affirming needs >=2 independent
evidence classes. A row a human marks 'affirmed' on one class is loaded as 'unresolved' and
reported -- the human release control can override the gate, but not the evidence standard.

Deliberate non-feature: this module never decides. It assembles, refuses, and promotes.
"""
from __future__ import annotations

import json
import os
import re

from pipeline import db
from pipeline.curate import _SELF_DESC, _spans

SHEET = "data/curation/gate_review_sheet.json"
DECISIONS = "data/curation/gate_adjudications.json"

# The gate's three counted categories (ADR-0028) plus the outcomes a reviewer can reach instead.
COUNTED = ("single_family_office", "multi_family_office", "embedded_fo_practice")
REVIEW_CATEGORIES = COUNTED + ("ria_with_fo_practice", "wealth_manager", "not_fo", "unresolved")

_FO_PHRASE = re.compile(r"family[\s-]+office", re.I)


def _adv_evidence(cur, crd: str) -> dict | None:
    """ADR-0020 class 1: the firm's own regulatory filing. Registry-agnostic -- a candidate found
    through the state feed carries the same ADV field shape as one found through the SEC feed."""
    cur.execute("select source, raw from bronze.captures "
                "where source in ('sec_form_adv', 'state_form_adv') and entity_key = %s "
                "order by id desc limit 1", (crd,))
    row = cur.fetchone()
    if not row:
        return None
    source, raw = row
    return {"class": "adv_item5", "source_url": raw.get("source_url"),
            "observed_at": raw.get("latest_filing_date"),
            "detail": {"registry": source,
                       "hnw_clients": raw.get("hnw_clients"),
                       "nonhnw_clients": raw.get("nonhnw_clients"),
                       "hnw_raum": raw.get("hnw_raum"), "raum_total": raw.get("raum_total"),
                       "total_employees": raw.get("total_employees"),
                       "org_form": raw.get("org_form"),
                       "legal_name": raw.get("legal_name"),
                       "business_name": raw.get("business_name")}}


def _website_evidence(cur, crd: str) -> tuple[list[dict], str | None, int]:
    """ADR-0020 class 2: what the firm says it IS, as quoted spans with URL and capture date.

    Returns (evidence, strongest_category_signal, fo_phrase_count). The phrase count is reported
    because the gate's v2 self-description rule scores on it -- the reviewer should see the same
    number the machine scored, not a summary of it.
    """
    cur.execute("select raw->>'page_type', raw->>'page_url', raw->>'text', fetched_at::date "
                "from (select distinct on (raw->>'page_url') * from bronze.captures "
                "      where source = 'website' and entity_key = %s "
                "      order by raw->>'page_url', id desc) latest "
                "order by case raw->>'page_type' when 'home' then 0 when 'about' then 1 else 2 end",
                (crd,))
    ev, draft, phrases = [], None, 0
    for ptype, purl, text, fetched in cur.fetchall():
        phrases += len(_FO_PHRASE.findall(text or ""))
        for cat, pat in _SELF_DESC:
            for span in _spans(text, pat):
                ev.append({"class": "website", "source_url": purl, "observed_at": str(fetched),
                           "detail": {"page_type": ptype, "category_signal": cat, "span": span}})
                draft = draft or cat
    return ev, draft, phrases


def _latest_gate(cur, entity_key: str) -> dict | None:
    cur.execute("select gate_version, decision, category, score, evidence, contradictions, "
                "decided_at, run_id from gold.entity_gate where entity_key = %s "
                "order by decided_at desc limit 1", (entity_key,))
    r = cur.fetchone()
    if not r:
        return None
    return {"gate_version": r[0], "decision": r[1], "category": r[2], "score": r[3],
            "evidence": r[4], "contradictions": r[5], "decided_at": str(r[6]), "run_id": r[7]}


def _draft(gate: dict, web_cat: str | None, adv: dict | None, phrases: int) -> tuple[str, str]:
    """The DRAFT proposal put in front of the reviewer, plus the note that says where to look hard.

    The note's job is adversarial: it names the specific way THIS row could be the gate's ~41%
    false-affirm case, so the reviewer reads toward the weakness rather than nodding along.
    """
    cat = gate.get("category") or "unresolved"
    d = (adv or {}).get("detail") or {}
    hnw = int(d.get("hnw_clients") or 0)
    nonhnw = int(d.get("nonhnw_clients") or 0)
    total = hnw + nonhnw
    rules = {h["rule"] for h in (gate.get("evidence") or [])}
    notes = [f"gate {gate['decision']} at {gate['score']} on rules {sorted(rules)}"]

    if not gate.get("evidence"):
        notes.append("NO scored rules -- nothing affirmative was found")
    if rules == {"name_fo_strong"} or (rules <= {"name_fo_strong", "structural_fo_shape"}):
        notes.append("NAME-ONLY RISK: the affirmative evidence is essentially the firm's name; "
                     "ADR-0028 calls a marketing label without a practice non-counting")
    if not web_cat and phrases == 0:
        notes.append("no website self-description span captured -- one evidence class only, "
                     "so ADR-0020 cannot affirm this row as it stands")
    if web_cat and cat in ("multi_family_office", "single_family_office") and web_cat == "ria_with_fo_practice":
        notes.append(f"CONTRADICTION: gate says {cat}, site language says a service line "
                     "-- if it is a practice, the counted category is embedded_fo_practice")
    if cat == "multi_family_office" and total > 100:
        notes.append(f"ADV reports {total} individual clients -- retail-scale book contradicts MFO")
    if cat == "single_family_office" and total > 5:
        notes.append(f"ADV reports {total} individual clients -- contradicts a one-family claim")
    if cat == "embedded_fo_practice":
        notes.append("category 3 bar: a NAMED practice substantiated by the firm's own materials "
                     "AND a second source -- a tagline is not a practice (ADR-0028)")
    for c in gate.get("contradictions") or []:
        notes.append(f"gate contradiction {c['rule']}: {c['detail']}")
    return cat, " | ".join(notes)


def sheet(path: str = SHEET, *, decisions: tuple[str, ...] = ("affirm",),
          limit: int | None = None) -> dict:
    """Assemble the review sheet for candidates the gate has decided. Only queue rows that reached
    a gate decision appear; a candidate still pending is not review-ready."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd from gold.entity_adjudications")
        already = {r[0] for r in cur.fetchall()}
        cur.execute(
            "select entity_key, source, firm_name, detail from ops.candidate_queue "
            "where stage = 'gated' and status = 'done' order by entity_key")
        candidates = cur.fetchall()
        for entity_key, source, firm_name, detail in candidates:
            crd = entity_key.split(":", 1)[-1]
            if crd in already:
                continue
            gate = _latest_gate(cur, entity_key)
            if not gate or gate["decision"] not in decisions:
                continue
            detail = detail or {}
            adv = _adv_evidence(cur, crd)
            web_ev, web_cat, phrases = _website_evidence(cur, crd)
            draft_cat, note = _draft(gate, web_cat, adv, phrases)
            evidence = ([adv] if adv else []) + web_ev
            rows.append({
                "entity_key": entity_key, "crd": crd, "firm_name": firm_name, "source": source,
                "website": detail.get("website"), "city": detail.get("city"),
                "state": detail.get("state"),
                "gate": gate,
                "site_fo_phrase_count": phrases,
                "extracted": detail.get("extracted"),
                "evidence_classes": sorted({e["class"] for e in evidence}),
                "evidence": evidence,
                "draft_category": draft_cat, "draft_note": note,
                # what the human fills in; ratify() refuses rows without decided_by
                "category": draft_cat, "status": "unresolved", "duplicate_of": None,
                "rationale": "", "decided_by": None,
            })
    if limit:
        rows = rows[:limit]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, default=str)
    one_class = sum(1 for r in rows if len(r["evidence_classes"]) < 2)
    return {"path": path, "decisions": list(decisions), "rows": len(rows),
            "already_adjudicated": len(already),
            "cannot_affirm_on_current_evidence": one_class,
            "draft_categories": {c: sum(1 for r in rows if r["draft_category"] == c)
                                 for c in sorted({r["draft_category"] for r in rows})}}


def ratify(path: str = DECISIONS, *, write: bool = False, promote: bool = True) -> dict:
    """Load ratified gate reviews into gold.entity_adjudications, then promote the affirmed firms
    into the product through the standard build path.

    Refuses rows without decided_by. Affirmed rows carrying <2 evidence classes are loaded as
    'unresolved' and counted -- the human outranks the gate, never the evidence standard.
    """
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {"file": path, "rows": len(rows), "applied": 0, "skipped_unratified": 0,
           "demoted_single_class": 0, "affirmed": 0, "written": write, "promoted": None}
    to_promote: list[str] = []
    with db.get_conn() as c, c.cursor() as cur:
        for r in rows:
            if not r.get("decided_by"):
                out["skipped_unratified"] += 1
                continue
            status, cat = r["status"], r.get("category")
            if cat not in REVIEW_CATEGORIES:
                raise ValueError(f"{r['crd']}: category {cat!r} is not one of {REVIEW_CATEGORIES}")
            if not (r.get("rationale") or "").strip():
                raise ValueError(f"{r['crd']}: a ratified row needs a rationale in plain words")
            classes = {e["class"] for e in r.get("evidence", [])}
            if status == "affirmed" and len(classes) < 2:
                status, cat = "unresolved", "unresolved"
                out["demoted_single_class"] += 1
            if status == "affirmed":
                out["affirmed"] += 1
                to_promote.append(r["crd"])
            if write:
                cur.execute(
                    "insert into gold.entity_adjudications "
                    "(crd, firm_name, category, status, duplicate_of, evidence, rationale, decided_by) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (crd) do update set "
                    "category=excluded.category, status=excluded.status, "
                    "duplicate_of=excluded.duplicate_of, evidence=excluded.evidence, "
                    "rationale=excluded.rationale, decided_by=excluded.decided_by, decided_at=now()",
                    (r["crd"], r["firm_name"], cat, status, r.get("duplicate_of"),
                     json.dumps(r.get("evidence", []), default=str), r["rationale"],
                     r["decided_by"]))
            out["applied"] += 1
        if write:
            c.commit()
    if write and promote and to_promote:
        out["promoted"] = promote_firms(to_promote, write=True)
    return out


def promote_firms(crds: list[str], *, write: bool = True) -> dict:
    """Move ratified firms into the product: extract them into silver, then rebuild gold.

    Scoped to exactly the ratified CRDs. A blanket silver rebuild would re-extract all 50 held
    records too -- extraction is not deterministic, so that would silently reword shipped cells
    (measured: a full-corpus re-extract redrafted thesis/sector text on records nobody reviewed).
    """
    from pipeline.gold import build as gb
    from pipeline.silver import load as sl

    s = sl.run(limit=None, write=write, crds=set(crds))
    g = gb.build(write=write)
    return {"requested": len(crds), "silver_firms": s["firms_processed"],
            "silver_people": s["people"], "silver_principals": s["principals"],
            "gold_firms": g.get("firms"), "written": write}
