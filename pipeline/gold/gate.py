"""Automated inclusion gate: the ADR-0028 tiered standard as enforced code (ADR-0029).

Per-firm human ratification qualified the original records; it cannot scale to 500. This gate
makes the entity decision automatically, deterministically, and auditably: every candidate gets a
scored evidence list (each point traceable to a named rule over a named input), a decision
(affirm / needs_evidence / exclude), and -- when affirmed -- one of the three counted categories.
No LLM sits in the decision path: extraction produced the raw text upstream, but the rules that
control release are plain code, per the same objection that shaped ADR-0023.

Precedence is fixed: a ratified human adjudication (gold.entity_adjudications) OUTRANKS the gate
wherever both exist. The gate covers the mass; humans review a defensible sample of gate-only
decisions (Bridge operating standard) and can override any of them.

Rules are pre-registered as GATE_VERSION before mass discovery runs. The 59 human-labeled entities
(50 adjudicated + 9 curation-gate exclusions) are the CALIBRATION set: `retro()` measures
gate-vs-human agreement and reports the confusion honestly -- including the expected failure mode
where a marketing-only "family office" name affirms falsely, which is exactly what the sampled
human review layer exists to catch, at a sampling rate the measured precision justifies.
"""
from __future__ import annotations

import json
import re

from pipeline import config, db
from pipeline.ops import runlog as rl

GATE_VERSION = ("gate-v2 (2026-07-27; v1 pre-registered, v2 adds the site self-description rule "
                "after calibration on the 59 labeled entities; FROZEN before mass discovery -- "
                "further changes require an ADR)")

# Decision thresholds -- part of the pre-registered version above, not tunables.
AFFIRM_MIN = 60          # SFO/MFO: net score at or above this affirms
EMBEDDED_MIN = 40        # embedded practice: lower bar but BOTH independent sources required
NEEDS_EVIDENCE_MIN = 30  # below this: exclude

_SITE_PRACTICE = re.compile(
    r"family[\s-]+office\s+(services?|practice|group|division|team|solutions)", re.I)
_SITE_FO_PHRASE = re.compile(r"family[\s-]+office", re.I)
_SINGLE_FAMILY = re.compile(r"\bsingle[\s-]?family\b|\bone\s+family\b", re.I)
_SILVER_FO = re.compile(r"\bfamil(y|ies)\b", re.I)
_MAX_SITE_TEXT = 60_000


def assemble(entity_key: str) -> dict:
    """Gather every evidence input the rules read, from bronze + silver. Pure data, no judgment."""
    crd = entity_key.split(":", 1)[-1]
    ev: dict = {"entity_key": entity_key}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select raw from bronze.captures where source = 'sec_form_adv' and entity_key = %s "
            "order by id desc limit 1", (crd,))
        row = cur.fetchone()
        ev["adv"] = row[0] if row else None
        cur.execute(
            "select coalesce(string_agg(text, ' '), '') from ("
            "  select distinct on (raw->>'page_url') raw->>'text' as text,"
            "         raw->>'page_url' as page_url"
            "  from bronze.captures where source = 'website' and entity_key = %s"
            "  order by raw->>'page_url', id desc) latest", (crd,))
        ev["site_text"] = (cur.fetchone()[0] or "")[:_MAX_SITE_TEXT]
        cur.execute(
            "select coalesce(bool_or(raw->>'page_url' ilike '%%family-office%%'), false) "
            "from bronze.captures where source = 'website' and entity_key = %s", (crd,))
        ev["fo_page_url"] = cur.fetchone()[0]
        cur.execute("select domain, thesis, description from silver.firms where crd = %s", (crd,))
        s = cur.fetchone()
        ev["silver"] = {"domain": s[0], "thesis": s[1], "description": s[2]} if s else None
    return ev


def evaluate(ev: dict) -> dict:
    """Pure rules over an evidence bundle. Returns {decision, category, score, evidence,
    contradictions}. Deterministic: same bundle, same verdict, forever."""
    adv = ev.get("adv") or {}
    name = adv.get("business_name") or ""
    site = ev.get("site_text") or ""
    silver = ev.get("silver") or {}
    hits: list[dict] = []
    cons: list[dict] = []

    def rule(name_, points, detail):
        hits.append({"rule": name_, "points": points, "detail": detail})

    def con(name_, points, detail):
        cons.append({"rule": name_, "points": points, "detail": detail})

    name_fo = any(p.search(name) for p in config.STRONG_NAME_PATTERNS)
    if name_fo:
        rule("name_fo_strong", 40, f"firm name {name!r} states family office")
    m = _SITE_PRACTICE.search(site)
    site_fo = bool(m) or ev.get("fo_page_url")
    if site_fo:
        rule("site_fo_practice", 25,
             f"site names an FO practice: {m.group(0)!r}" if m else "dedicated family-office page URL")
    # v2 (calibration finding): affirmed FOs self-describe as "a (multi-)family office" on their
    # sites without the suffix words the practice rule looks for -- Wellspring's site says the
    # phrase 12 times, PointOne's 20, and v1 scored both zero for it. Repeated self-description
    # is its own evidence class: the firm publicly presents AS a family office.
    fo_phrases = len(_SITE_FO_PHRASE.findall(site))
    site_selfdesc = fo_phrases >= 2
    if site_selfdesc:
        rule("site_fo_selfdesc", 20, f"site text states 'family office' {fo_phrases} times")
    freetext_fo = bool(config.FREE_TEXT_MARKER.search(adv.get("other_text") or ""))
    if freetext_fo:
        rule("adv_freetext_fo", 15, "ADV Item 5.G other-services text states family office")
    raum = adv.get("raum_total") or 0
    hnw_raum = adv.get("hnw_raum") or 0
    clients = (adv.get("hnw_clients") or 0) + (adv.get("nonhnw_clients") or 0)
    share = (hnw_raum / raum) if raum else 0.0
    structural = raum and share >= config.CLIENT_MIX_HNW_RAUM_SHARE and 0 < clients <= config.CLIENT_MIX_MAX_CLIENTS
    if structural:
        rule("structural_fo_shape", 20, f"HNW RAUM share {share:.2f}, {clients} clients")
    domain = (silver.get("domain") or "")
    if "familyoffice" in domain.replace("-", ""):
        rule("domain_fo", 10, f"domain {domain!r}")
    desc = f"{silver.get('thesis') or ''} {silver.get('description') or ''}"
    if _SILVER_FO.search(desc) and (site_fo or name_fo or freetext_fo):
        rule("silver_fo_desc", 10, "extracted profile describes serving families")

    employees = adv.get("total_employees") or 0
    if raum > 15_000_000_000 or employees > 150:
        con("institutional_scale", -40,
            f"RAUM ${raum/1e9:.0f}B, {employees} employees -- institutional-manager scale")
    retail = (adv.get("nonhnw_clients") or 0) > 100
    if retail:
        con("retail_scale", -25, f"{adv.get('nonhnw_clients')} non-HNW clients -- retail RIA shape")

    core_fo_evidence = name_fo or site_fo or freetext_fo or site_selfdesc
    score = sum(h["points"] for h in hits) + sum(c["points"] for c in cons)

    # Category and decision. Embedded practice has its own bar: BOTH independent sources
    # (site-named practice AND ADV free-text), institutional scale still disqualifies, but a
    # retail client base does NOT -- an RIA with retail clients and a real FO practice is
    # exactly what category 3 is for (ADR-0028).
    decision, category = "exclude", None
    inst = any(c["rule"] == "institutional_scale" for c in cons)
    if not core_fo_evidence:
        # Census-measured: structural shape alone runs 10-20% precision. Never affirm on it.
        decision = "needs_evidence" if score >= NEEDS_EVIDENCE_MIN else "exclude"
    elif not name_fo and site_fo and freetext_fo and not inst \
            and (score - sum(c["points"] for c in cons if c["rule"] == "retail_scale")) >= EMBEDDED_MIN:
        decision, category = "affirm", "embedded_fo_practice"
    elif score >= AFFIRM_MIN:
        decision = "affirm"
        single = _SINGLE_FAMILY.search(name) or (name_fo and 0 < clients <= 2 and not retail)
        category = "single_family_office" if single else "multi_family_office"
    elif score >= NEEDS_EVIDENCE_MIN:
        decision = "needs_evidence"

    return {"decision": decision, "category": category, "score": score,
            "evidence": hits, "contradictions": cons}


def run_gate(entity_keys: list[str], *, write: bool = False) -> list[dict]:
    """Evaluate candidates and persist decisions (append-only). One row per evaluation."""
    out = []
    for key in entity_keys:
        verdict = evaluate(assemble(key))
        verdict["entity_key"] = key
        out.append(verdict)
        if write:
            with db.get_conn() as c, c.cursor() as cur:
                cur.execute(
                    "insert into gold.entity_gate (entity_key, gate_version, decision, category,"
                    " score, evidence, contradictions, run_id)"
                    " values (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)",
                    (key, GATE_VERSION, verdict["decision"], verdict["category"], verdict["score"],
                     json.dumps(verdict["evidence"]), json.dumps(verdict["contradictions"]),
                     rl.current_run()))
                c.commit()
        rl.event("discover", "gate_decision", call_class="decision", target=key,
                 detail={"decision": verdict["decision"], "category": verdict["category"],
                         "score": verdict["score"]})
    return out


def retro(write: bool = False) -> dict:
    """Calibration: run the gate over every human-labeled entity and report agreement honestly.

    Labels: gold.entity_adjudications (50: affirmed FO / reclassified / quarantined) +
    gold.excluded_firms (9 curation-gate rejections). The gate never overrides these -- human
    adjudication outranks it -- so every disagreement is measurement, not a release change."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, category, status from gold.entity_adjudications")
        adjudicated = {r[0]: {"category": r[1], "status": r[2]} for r in cur.fetchall()}
        cur.execute("select crd from gold.excluded_firms")
        excluded = [r[0] for r in cur.fetchall()]

    results = run_gate(list(adjudicated) + excluded, write=write)
    by_key = {r["entity_key"]: r for r in results}

    def bucket(crd):
        if crd in excluded:
            return "human_excluded"
        h = adjudicated[crd]
        if h["status"] == "affirmed" and h["category"] in ("single_family_office", "multi_family_office"):
            return "human_affirmed_fo"
        if h["category"] == "ria_with_fo_practice":
            return "human_ria_fo_practice"
        if h["category"] == "wealth_manager":
            return "human_wealth_manager"
        return "human_quarantined"

    report: dict = {"gate_version": GATE_VERSION, "labeled": len(results), "buckets": {}}
    misses: list[dict] = []
    for crd in list(adjudicated) + excluded:
        b = bucket(crd)
        g = by_key[crd]
        cell = report["buckets"].setdefault(b, {"n": 0, "gate": {}})
        cell["n"] += 1
        gk = f"{g['decision']}:{g['category'] or '-'}"
        cell["gate"][gk] = cell["gate"].get(gk, 0) + 1
        wrong = (b == "human_affirmed_fo" and g["decision"] != "affirm") or \
                (b in ("human_excluded", "human_wealth_manager") and g["decision"] == "affirm"
                 and g["category"] != "embedded_fo_practice")
        if wrong:
            misses.append({"crd": crd, "human": b, "gate": gk, "score": g["score"]})
    report["disagreements"] = misses
    if adjudicated:
        fo = report["buckets"].get("human_affirmed_fo", {"n": 0, "gate": {}})
        affirmed = sum(v for k, v in fo["gate"].items() if k.startswith("affirm"))
        report["recall_on_human_affirmed_fo"] = f"{affirmed}/{fo['n']}"
    return report
