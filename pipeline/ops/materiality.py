"""Materiality classification for website changes (day 2 of the operating window; ADR-0027).

A hash flip says a page's TEXT moved; it does not say the FACTS moved. Day-1 cycles proved the
difference empirically: five same-hour `website_change` flags, all almost certainly rotating
content. This module closes that gap. When a cycle sees a changed site it re-fetches the firm's
pages, re-runs the extraction seam, and diffs the extracted facts against what silver currently
believes:

- facts identical  -> COSMETIC: trust event `noted`, nothing else changes; the new page text still
  lands in bronze (append-only history) so the judgment is auditable.
- facts moved      -> MATERIAL: fresh capture persisted to silver through the standard path (which
  preserves email-verification state, per the day-1 fix), trust event `refreshed` whose evidence IS
  the field delta. Gold picks the change up in the same cycle's rebuild phase.
- ratified primary contact missing from the new roster -> additional `decision_maker_gone` event,
  action `flagged`: the machine notices, but re-adjudication stays a human release control
  (ADR-0021) -- an automated demotion would be automation deciding what evidence standards require
  judgment to decide.

Every LLM call is ledgered with tokens + USD; a per-cycle budget caps spend and skips are logged
rather than silent (no silent caps)."""
from __future__ import annotations

import json

from pipeline import db
from pipeline.ops import runlog as rl


def _current_silver(crd: str) -> dict | None:
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select thesis, description, sectors, founded_year from silver.firms "
                    "where crd = %s", (crd,))
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("select name, title, is_principal from silver.people where firm_crd = %s",
                    (crd,))
        people = cur.fetchall()
    return {"thesis": row[0], "description": row[1], "sectors": sorted(row[2] or []),
            "founded_year": row[3],
            "team": {p[0].strip().lower(): (p[1], p[2]) for p in people}}


def _diff_facts(old: dict, ext) -> list[str]:
    """Human-readable field deltas between silver's beliefs and a fresh extraction."""
    deltas: list[str] = []
    if (old["thesis"] or "") != (ext.thesis or ""):
        deltas.append("thesis changed")
    if (old["description"] or "") != (ext.description or ""):
        deltas.append("description changed")
    if old["founded_year"] != ext.founded_year:
        deltas.append(f"founded_year {old['founded_year']} -> {ext.founded_year}")
    new_sectors = sorted(ext.sectors or [])
    if old["sectors"] != new_sectors:
        deltas.append(f"sectors {old['sectors']} -> {new_sectors}")
    new_team = {m.name.strip().lower(): (m.title, m.is_principal) for m in ext.team}
    gone = sorted(set(old["team"]) - set(new_team))
    added = sorted(set(new_team) - set(old["team"]))
    if gone:
        deltas.append(f"people no longer listed: {', '.join(gone[:5])}")
    if added:
        deltas.append(f"people newly listed: {', '.join(added[:5])}")
    for name in set(old["team"]) & set(new_team):
        if (old["team"][name][0] or "") != (new_team[name][0] or ""):
            deltas.append(f"title changed for {name}: {old['team'][name][0]!r} -> {new_team[name][0]!r}")
    return deltas


def classify(firm: dict, *, write: bool, prior_run) -> dict:
    """Re-fetch + re-extract one changed firm and act on the result. Returns a summary dict;
    never raises (a materiality failure must not kill the cycle)."""
    from pipeline.bronze import website as web
    from pipeline.silver import extract as ex
    from pipeline.silver import load as sl

    crd, name, site = firm["crd"], firm.get("family_office_name"), firm.get("website")
    out = {"crd": crd, "verdict": "error", "deltas": []}
    try:
        old = _current_silver(crd)
        if old is None:
            rl.event("observe", "materiality_skip", target=crd, status="skipped",
                     detail={"reason": "no silver baseline for this firm"})
            out["verdict"] = "no_baseline"
            return out

        pages = web.fetch_site(site)
        texted = [p for p in pages if p.text]
        if not texted:
            rl.trust_event(crd, "website_change", None, None,
                           "page text changed per hash, but the re-fetch returned no readable "
                           "text; treated as unresolved, will retry next cycle", "flagged")
            out["verdict"] = "refetch_empty"
            return out
        page_dicts = [{"bronze_id": None, "page_type": p.page_type, "url": p.url,
                       "title": p.title, "text": p.text} for p in texted]
        text, urls, _, home = sl._combine(page_dicts)

        extractor = ex.get_extractor(None)
        result = extractor.extract(text, source_url=home)
        usage = result.usage or {}
        tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        rl.event("observe", "materiality_extract", call_class="model", target=crd,
                 duration_ms=None, tokens_in=tin, tokens_out=tout,
                 usd=rl.usd_for("gpt-4o-mini", tin, tout),
                 detail={"pages": len(texted), "provider": result.provider})

        deltas = _diff_facts(old, result.extraction)
        out["deltas"] = deltas

        # The raw capture is history either way (append-only; identical pages dedupe to 0 rows).
        if write:
            db.insert_captures([web._page_to_bronze_row(crd, name, p) for p in texted])

        since = f"since run {prior_run[2]} ({prior_run[1]:%Y-%m-%d %H:%M}Z)" if prior_run else ""
        if not deltas:
            out["verdict"] = "cosmetic"
            rl.trust_event(crd, "website_change", prior_run[0][:16] if prior_run else None, None,
                           f"home-page text changed {since} but re-extraction found identical facts "
                           "(thesis, description, sectors, roster all unchanged) -- classified "
                           "cosmetic (dynamic page content); no record change", "noted")
            return out

        out["verdict"] = "material"
        if write:
            ids = _bronze_ids_for(crd, urls)
            sl._persist({"crd": crd, "firm_name": name}, result, urls, ids, home)
        rl.trust_event(crd, "website_change", prior_run[0][:16] if prior_run else None, None,
                       f"site facts changed {since}: {'; '.join(deltas[:6])} -- silver refreshed "
                       "through the standard path (verification state preserved); gold rebuilds "
                       "this cycle", "refreshed")

        # A ratified decision-maker disappearing is release-relevant: flag it for human
        # re-adjudication (ADR-0021 keeps that judgment human); never auto-demote here.
        primary = (firm.get("primary_contact_name") or "").strip().lower()
        if primary and primary not in {m.name.strip().lower() for m in result.extraction.team}:
            rl.trust_event(crd, "decision_maker_gone", firm.get("primary_contact_name"), None,
                           f"ratified primary contact {firm.get('primary_contact_name')!r} is not "
                           "on the re-extracted roster -- needs human re-adjudication before the "
                           "record's contact evidence can be trusted (ADR-0021)", "flagged")
            out["primary_contact_gone"] = True
        return out
    except Exception as e:  # one firm's failure must not kill the cycle
        rl.event("observe", "materiality_error", target=crd, status="error",
                 detail={"error": repr(e)})
        rl.trust_event(crd, "website_change", None, None,
                       f"page text changed but materiality classification failed ({type(e).__name__});"
                       " flag stands, will retry next cycle", "flagged")
        return out


def _bronze_ids_for(crd: str, urls: list[str]) -> list[int]:
    """Latest bronze capture id per fetched page URL -- the lineage a fresh persist records."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select distinct on (raw->>'page_url') id from bronze.captures"
            " where source = 'website' and entity_key = %s and raw->>'page_url' = any(%s)"
            " order by raw->>'page_url', id desc",
            (crd, urls))
        return [r[0] for r in cur.fetchall()]
