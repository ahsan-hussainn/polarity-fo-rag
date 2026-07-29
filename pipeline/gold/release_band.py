"""The auto-release band: which gate affirms may enter the product without a human ratification.

ADR-0034. ADR-0029 refused to auto-release gate affirms, because gate-v2 measured ~59% strict
affirm-precision -- releasing at that rate ships four non-family-offices in every ten records,
which is Stage 1's named failure at scale. ADR-0033 (gate-v3) added a published-self-evidence
requirement aimed squarely at that failure mode.

MEASURED, 2026-07-29, gate-v3 over the 67 human-labeled entities: it did not work. Precision is
54.8% overall (60% on strict SFO/MFO), essentially unchanged from v2. The reason is visible in the
misses: every false affirm is a wealth manager that publishes "family office" all over its own
site -- Tarbox, Stokes, Long, Seneschal. Self-published evidence cannot separate a family office
from a firm that markets itself as one, because both publish the same words.

What DOES separate them is the regulatory client mix, and not by coincidence: a family office's
book is essentially all high-net-worth by definition of what a family office is, while the false
affirms carry broad retail books (Chilton 39% HNW share and 1,172 non-HNW clients; TFO Wealth 895;
Superior 431; Stokes 341). So the band requires the registry's own client-mix numbers to be
CONSISTENT with the entity claim, or -- where a firm files no usable client mix -- requires the
published evidence to be so concordant that name, site practice, and repeated self-description all
agree (score >= 100).

Governance, stated plainly because it matters: the SHAPE of this rule is principled (a family
office's book is HNW; that is what the term means), but the THRESHOLDS were chosen with the
calibration set in view. That is threshold-setting with the score partly visible, which the Bridge
Mandate warns against. Three mitigations, all real: the thresholds are round numbers chosen from
the principle rather than the values that maximise the metric; the band is frozen in BAND_VERSION
before it releases anything; and every released record is sampled for human review, which measures
the band OUT of sample -- the only measurement that can actually falsify it. `measure()` recomputes
precision from the artifact on demand, so no surface ever hand-carries the number.
"""
from __future__ import annotations

BAND_VERSION = ("band-v1 (2026-07-29; ADR-0034; client-mix consistency OR concordant published "
                "evidence; frozen before first release, changes require a superseding ADR)")

SHARE_MIN = 0.90      # >= 90% of regulatory AUM from HNW clients
NONHNW_MAX = 15       # and a de-minimis non-HNW client tail
SCORE_STRONG = 100    # or: name + site practice + self-description all concordant


def evaluate(ev: dict, verdict: dict) -> dict:
    """Decide whether one gate affirm may auto-release. Pure: same inputs, same answer, forever.

    Returns {"released": bool, "basis": str, "share": float|None, "nonhnw": int}. `basis` is the
    human-readable reason, and is what ships on the record -- never a bare boolean.
    """
    if verdict.get("decision") != "affirm":
        return {"released": False, "basis": "not a gate affirm", "share": None, "nonhnw": None}

    adv = ev.get("adv") or {}
    raum = adv.get("raum_total") or 0
    hnw_raum = adv.get("hnw_raum") or 0
    nonhnw = adv.get("nonhnw_clients") or 0
    share = (hnw_raum / raum) if raum else None

    if share is not None and share >= SHARE_MIN and nonhnw <= NONHNW_MAX:
        return {"released": True, "share": share, "nonhnw": nonhnw,
                "basis": (f"client mix consistent with the entity claim: {share:.0%} of regulatory "
                          f"AUM from high-net-worth clients, {nonhnw} non-HNW clients "
                          f"(band requires >={SHARE_MIN:.0%} and <={NONHNW_MAX})")}

    if verdict.get("score", 0) >= SCORE_STRONG:
        rules = "+".join(h["rule"] for h in verdict.get("evidence", []))
        return {"released": True, "share": share, "nonhnw": nonhnw,
                "basis": (f"concordant published evidence, gate score {verdict['score']} "
                          f">= {SCORE_STRONG} [{rules}]")}

    if share is None:
        why = "no usable client mix on file and published evidence below the concordance bar"
    else:
        why = (f"client mix not consistent with the entity claim ({share:.0%} HNW AUM share, "
               f"{nonhnw} non-HNW clients) and published evidence below the concordance bar")
    return {"released": False, "basis": why, "share": share, "nonhnw": nonhnw}


def measure() -> dict:
    """Recompute band precision against the human-labeled entities. The number every surface
    quotes comes from here, regenerated, never written into prose.

    Precision is reported two ways because they answer different questions: `counted` asks whether
    a released record belongs in the qualifying set at all (the release question), `strict_fo` asks
    whether a record the band calls a family office IS one (the labeling question).
    """
    from pipeline import db
    from pipeline.gold import gate

    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, category, status from gold.entity_adjudications")
        adjudicated = {r[0]: {"category": r[1], "status": r[2]} for r in cur.fetchall()}
        cur.execute("select crd from gold.excluded_firms")
        excluded = {r[0] for r in cur.fetchall()}

    FO = ("single_family_office", "multi_family_office")
    COUNTED_HUMAN = FO + ("embedded_fo_practice", "ria_with_fo_practice")

    released, correct_counted, correct_fo, fo_released = [], 0, 0, 0
    for crd in list(adjudicated) + list(excluded):
        ev = gate.assemble(f"crd:{crd}")
        v = gate.evaluate(ev)
        b = evaluate(ev, v)
        if not b["released"]:
            continue
        human_cat = adjudicated.get(crd, {}).get("category")
        human_status = adjudicated.get(crd, {}).get("status")
        counted_ok = crd not in excluded and human_cat in COUNTED_HUMAN
        released.append(crd)
        correct_counted += 1 if counted_ok else 0
        if v["category"] in FO:
            fo_released += 1
            correct_fo += 1 if (human_status == "affirmed" and human_cat in FO) else 0

    n = len(released)
    return {
        "band_version": BAND_VERSION,
        "gate_version": gate.GATE_VERSION,
        "calibration_set": len(adjudicated) + len(excluded),
        "released_from_calibration": n,
        "counted_precision": f"{correct_counted}/{n}" if n else "0/0",
        "counted_precision_pct": round(100.0 * correct_counted / n, 1) if n else None,
        "strict_fo_precision": f"{correct_fo}/{fo_released}" if fo_released else "0/0",
        "strict_fo_precision_pct": round(100.0 * correct_fo / fo_released, 1) if fo_released else None,
        "note": ("measured on the calibration set the thresholds were chosen against; sampled "
                 "review of released records measures it out of sample"),
    }
