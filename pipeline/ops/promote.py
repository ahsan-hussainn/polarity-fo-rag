"""Promotion: moving a gate-affirmed candidate from the discovery queue into the product path.

ADR-0034. Discovery deliberately stops at the queue -- a gated candidate holds bronze captures and
a gate verdict, but no silver row, so `gold.build` cannot see it. That boundary was right when
every affirm needed a human ratification to advance. With a measured auto-release band, the
candidates that clear it need a way through, and this is it: the ONLY way a record enters the
product without a human, and it runs inside scheduled cycles.

What promotion does NOT do is invent a decision-maker. The band establishes the ENTITY; nothing in
it proves who allocates. A promoted record therefore ships with person_status='not_established'
and no contact -- counting on entity evidence under ADR-0028's field-permissive standard, and
saying plainly that the decision-maker is not established. Presenting an extracted-but-unratified
name as the proven decision-maker is exactly the claim-stronger-than-evidence failure the Bridge
Mandate corrected, and volume is not a reason to reopen it.
"""
from __future__ import annotations

from pipeline import db
from pipeline.gold import gate, release_band
from pipeline.ops import runlog as rl


def _pending_affirms() -> list[str]:
    """Gate affirms with no human adjudication and no silver row yet, newest decision first."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select distinct g.entity_key from gold.entity_gate g "
            " where g.decision = 'affirm' "
            "   and not exists (select 1 from gold.entity_adjudications e "
            "                   where e.crd = replace(g.entity_key, 'crd:', '')) "
            "   and not exists (select 1 from silver.firms f "
            "                   where f.crd = replace(g.entity_key, 'crd:', ''))")
        return [r[0] for r in cur.fetchall()]


def run(*, limit: int = 25, write: bool = True) -> dict:
    """Evaluate pending gate affirms against the band and promote those that clear it.

    Promotion = build the silver row from bronze website captures already on file, so the standard
    gold build picks the firm up on this same cycle. Extraction re-runs here rather than reusing
    discovery's stashed summary, because silver is the layer of persisted belief and belief must
    come from the documented extraction path, not a queue scratchpad.
    """
    from pipeline.silver import load as sl

    out = {"considered": 0, "released": 0, "held": 0, "promoted": 0, "errors": 0,
           "band_version": release_band.BAND_VERSION, "held_reasons": []}
    keys = _pending_affirms()[:limit]
    out["considered"] = len(keys)
    to_promote: list[str] = []

    for key in keys:
        try:
            ev = gate.assemble(key)
            verdict = gate.evaluate(ev)
            band = release_band.evaluate(ev, verdict)
            crd = key.split(":", 1)[-1]
            rl.event("promote", "band_decision", call_class="decision", target=key,
                     detail={"released": band["released"], "basis": band["basis"],
                             "gate_score": verdict["score"], "category": verdict["category"],
                             "band_version": release_band.BAND_VERSION})
            if band["released"]:
                out["released"] += 1
                to_promote.append(crd)
            else:
                out["held"] += 1
                out["held_reasons"].append({"entity_key": key, "reason": band["basis"]})
        except Exception as e:  # one candidate must never kill the phase
            out["errors"] += 1
            rl.event("promote", "band_error", target=key, status="error",
                     detail={"error": repr(e)})

    if to_promote and write:
        try:
            res = sl.run(limit=None, write=True, crds=set(to_promote))
            out["promoted"] = res.get("firms_processed", 0)
            rl.event("promote", "silver_promote", call_class="model",
                     tokens_in=res.get("input_tokens", 0), tokens_out=res.get("output_tokens", 0),
                     usd=rl.usd_for("gpt-4o-mini", res.get("input_tokens", 0),
                                    res.get("output_tokens", 0)),
                     detail={"crds": to_promote, "people": res.get("people")})
        except Exception as e:
            out["errors"] += 1
            rl.event("promote", "silver_promote", status="error", detail={"error": repr(e)})
    return out
