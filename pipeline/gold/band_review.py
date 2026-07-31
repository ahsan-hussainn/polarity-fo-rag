"""Sampled human review of BAND-RELEASED records — the measurement ADR-0034 promised.

ADR-0034 states the obligation plainly: *"sampled human review of released records is mandatory, and
it is the only measurement that can actually falsify the band, because it measures out of sample."*
That matters because the band's headline precision (16/16 counted, 14/16 strict) is measured on the
calibration set its own thresholds were chosen against, which the ADR also says in as many words.
Until a human looks at records the band released on its own, the out-of-sample number does not
exist.

This module assembles the evidence for exactly those records — `release_basis = 'gate_released'`,
the ones no human ratified — and computes the out-of-sample precision once verdicts are recorded.

Two verdicts per record, because the band makes two separable claims and ADR-0034 already reports
them separately:

  counted_ok   Does this belong in the qualifying set at all? (the RELEASE question)
  category_ok  Is the category the band assigned correct?     (the LABELLING question)

A record can be counted_ok=true and category_ok=false — ADR-0034 discloses exactly that case, where
the band calls something multi_family_office and a human calls it an RIA with an FO practice. That
is a real error and it is reported, not smoothed away.

Evidence assembly reuses `review.py`'s helpers deliberately: the reviewer must see the same numbers
and the same quoted spans the machine scored, not a summary of them.
"""
from __future__ import annotations

import json
import os

from pipeline import db
from pipeline.gold.review import _adv_evidence, _latest_gate, _website_evidence

SHEET = "data/curation/band_review_sheet.json"
VERDICTS = "data/curation/band_review_verdicts.json"


def sheet(path: str = SHEET) -> dict:
    """Assemble the review sheet for every band-released record."""
    rows = []
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select crd, family_office_name, entity_category, release_basis_detail, website, "
            "       city, state, aum_usd, investing_sectors, investment_thesis "
            "  from gold.records "
            " where release_state = 'qualifying' and release_basis = 'gate_released' "
            " order by family_office_name")
        released = cur.fetchall()

        for (crd, name, cat, basis, site, city, state, aum, sectors, thesis) in released:
            adv = _adv_evidence(cur, crd)
            web_ev, web_cat, phrases = _website_evidence(cur, crd)
            gate = _latest_gate(cur, f"crd:{crd}")
            mix = (adv or {}).get("detail") or {}
            raum, hnw = mix.get("raum_total") or 0, mix.get("hnw_raum") or 0
            rows.append({
                "crd": crd,
                "firm": name,
                "band_category": cat,
                "band_basis": basis,
                "location": f"{city or '?'}, {state or '?'}",
                "aum_usd": aum,
                "website": site,
                # The two numbers the band actually decided on, shown raw so a reviewer can
                # recompute the share rather than trust a rounded one.
                "client_mix": {
                    "raum_total": raum, "hnw_raum": hnw,
                    "hnw_raum_share": round(hnw / raum, 4) if raum else None,
                    "hnw_clients": mix.get("hnw_clients"),
                    "nonhnw_clients": mix.get("nonhnw_clients"),
                    "total_employees": mix.get("total_employees"),
                },
                "adv_source_url": (adv or {}).get("source_url"),
                "adv_filing_date": (adv or {}).get("observed_at"),
                "gate": {"score": (gate or {}).get("score"),
                         "category": (gate or {}).get("category"),
                         "rules": [h["rule"] for h in ((gate or {}).get("evidence") or [])],
                         "contradictions": [h["rule"] for h in
                                            ((gate or {}).get("contradictions") or [])]},
                "site_fo_phrase_count": phrases,
                "site_self_description": [
                    {"url": e["source_url"], "signal": e["detail"]["category_signal"],
                     "span": e["detail"]["span"]}
                    for e in web_ev[:6]],
                "extracted_sectors": sectors,
                "extracted_thesis": (thesis or "")[:300] or None,
                # Filled by the reviewer.
                "counted_ok": None,
                "category_ok": None,
                "reviewer_note": "",
            })

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"note": ("Sampled human review of band-released records, per ADR-0034. Set "
                            "counted_ok (does it belong in the qualifying set) and category_ok "
                            "(is the band's category right) to true/false, add a note, then run "
                            "`band-review --measure`. Leave a record null to exclude it from the "
                            "sample; partial samples are fine and the measurement says how many "
                            "were reviewed."),
                   "band_released_total": len(rows), "records": rows},
                  fh, indent=2, ensure_ascii=False, default=str)
    return {"path": path, "records": len(rows)}


def render(sheet_path: str = SHEET, out_path: str = "data/curation/band_review.md") -> dict:
    """A readable sheet. One record per section, evidence first, verdict lines at the end."""
    with open(sheet_path, encoding="utf-8") as fh:
        data = json.load(fh)
    L: list[str] = [
        "# Band-released records — sampled review (ADR-0034)",
        "",
        f"{data['band_released_total']} records released by the auto-release band with **no human "
        "ratification**. The band's 16/16 counted precision is measured on the calibration set its "
        "own thresholds were chosen against; this review is the only out-of-sample measurement.",
        "",
        "For each: does it belong in the qualifying set (`counted_ok`), and is the band's category "
        "right (`category_ok`)? Record answers in "
        "`data/curation/band_review_verdicts.json`, then run "
        "`python -m pipeline.cli band-review --measure`.",
        "",
    ]
    for r in data["records"]:
        m = r["client_mix"]
        share = f"{m['hnw_raum_share']:.0%}" if m["hnw_raum_share"] is not None else "n/a"
        L += [
            f"## {r['firm']}  ·  CRD {r['crd']}",
            "",
            f"- **Band assigned:** `{r['band_category']}`",
            f"- **Released because:** {r['band_basis']}",
            f"- **Location / AUM:** {r['location']} · "
            f"{('$%.0fM' % (r['aum_usd'] / 1e6)) if r['aum_usd'] else 'AUM not stated'}",
            f"- **Client mix:** HNW RAUM share **{share}** "
            f"({m['hnw_raum']:,} of {m['raum_total']:,}) · "
            f"{m['hnw_clients'] or 0} HNW clients · **{m['nonhnw_clients'] or 0} non-HNW** · "
            f"{m['total_employees'] or '?'} employees",
            f"- **Gate:** score {r['gate']['score']} → `{r['gate']['category']}` "
            f"[{', '.join(r['gate']['rules']) or 'none'}]"
            + (f" · contradictions: {', '.join(r['gate']['contradictions'])}"
               if r['gate']['contradictions'] else ""),
            f"- **Website:** {r['website'] or 'none held'} · "
            f"says \"family office\" {r['site_fo_phrase_count']}×",
            f"- **ADV filing:** {r['adv_filing_date'] or '?'} · {r['adv_source_url'] or 'no URL'}",
        ]
        if r["extracted_sectors"]:
            L.append(f"- **Stated sectors:** {', '.join(r['extracted_sectors'][:8])}")
        if r["site_self_description"]:
            L += ["", "**What the firm publishes about itself:**", ""]
            for s in r["site_self_description"]:
                L.append(f"  - _{s['signal']}_ — \"{s['span'].strip()}\"  \n    <{s['url']}>")
        L += ["", "```", f"counted_ok  : ?    # is this a qualifying record at all?",
              f"category_ok : ?    # is `{r['band_category']}` the right label?",
              "note        : ", "```", ""]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return {"path": out_path, "records": len(data["records"])}


def measure(verdicts_path: str = VERDICTS) -> dict:
    """Out-of-sample precision from recorded verdicts. Reports the sample size honestly: a
    measurement over 4 of 11 records is a measurement over 4, and says so."""
    with open(verdicts_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    records = raw["records"] if isinstance(raw, dict) else raw
    reviewed = [r for r in records if r.get("counted_ok") is not None]
    counted_ok = [r for r in reviewed if r["counted_ok"]]
    cat_reviewed = [r for r in reviewed if r.get("category_ok") is not None]
    cat_ok = [r for r in cat_reviewed if r["category_ok"]]
    n, cn = len(reviewed), len(cat_reviewed)
    out = {
        "band_released_total": len(records),
        "reviewed": n,
        "counted_precision": f"{len(counted_ok)}/{n}" if n else "0/0",
        "counted_precision_pct": round(100.0 * len(counted_ok) / n, 1) if n else None,
        "category_precision": f"{len(cat_ok)}/{cn}" if cn else "0/0",
        "category_precision_pct": round(100.0 * len(cat_ok) / cn, 1) if cn else None,
        "failures": [{"crd": r["crd"], "firm": r["firm"],
                      "counted_ok": r["counted_ok"], "category_ok": r.get("category_ok"),
                      "note": r.get("reviewer_note", "")}
                     for r in reviewed if not r["counted_ok"] or r.get("category_ok") is False],
        "note": ("OUT-OF-SAMPLE, unlike release_band.measure(), which scores the calibration set "
                 "the thresholds were chosen against. ADR-0034: if counted precision here falls "
                 "below ~85%, the band freezes and released records revert to the review queue."),
    }
    return out
