"""Discovery queue: how the climb to 500 advances across scheduled cycles (ADR-0029).

Candidates from any registry land in ops.candidate_queue; each cycle claims a bounded tranche
(FOR UPDATE SKIP LOCKED -- an interrupted run's claims are simply re-claimable, never duplicated),
walks each candidate through fetch -> extract -> gate, and records every step in the run ledger.

Deliberate boundary: a gated candidate does NOT enter silver or gold. Silver stays the layer of
adjudication-visible entities; a gate AFFIRM is triage that queues the candidate for human review
with its evidence pre-assembled (ADR-0029's measured ~59% affirm precision is why), and only a
ratified adjudication lets the standard build path pick the firm up. Extraction here exists to
give the gate its site evidence and the reviewer a summary -- it is stashed on the queue row, not
persisted as belief.
"""
from __future__ import annotations

import json
import time

from pipeline import db
from pipeline.ops import runlog as rl

TIERS_DEFAULT = ("strong", "medium")


def seed_queue(jsonl_path: str, *, source: str, tiers=TIERS_DEFAULT,
               limit: int | None = None, write: bool = False) -> dict:
    """Load discovery candidates into the queue (and their registry rows into bronze), skipping
    every entity the system already holds or has already judged."""
    bronze_source = {"sec_adv": "sec_form_adv", "state_adv": "state_form_adv"}[source]
    rows = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            if c.get("tier") in tiers and c.get("crd"):
                rows.append(c)
    with db.get_conn() as c_, c_.cursor() as cur:
        cur.execute("select crd from gold.records union select crd from gold.entity_adjudications "
                    "union select crd from gold.excluded_firms")
        held = {r[0] for r in cur.fetchall()}
        cur.execute("select entity_key from ops.candidate_queue")
        queued = {r[0].split(":", 1)[-1] for r in cur.fetchall()}
    fresh = [c for c in rows if c["crd"] not in held and c["crd"] not in queued]
    if limit:
        fresh = fresh[:limit]
    out = {"file": jsonl_path, "source": source, "tiers": list(tiers), "candidates": len(rows),
           "already_held_or_queued": len(rows) - len(fresh), "seeded": len(fresh), "written": write}
    if not write:
        return out
    db.insert_captures([{"source": bronze_source, "source_url": None, "entity_key": c["crd"],
                         "raw": c} for c in fresh])
    with db.get_conn() as c_, c_.cursor() as cur:
        for c in fresh:
            cur.execute(
                "insert into ops.candidate_queue (entity_key, source, firm_name, detail)"
                " values (%s,%s,%s,%s::jsonb) on conflict (entity_key) do nothing",
                (f"crd:{c['crd']}", source, c.get("business_name"),
                 json.dumps({"tier": c.get("tier"), "reasons": c.get("reasons"),
                             "website": c.get("website"), "city": c.get("city"),
                             "state": c.get("state"), "raum_total": c.get("raum_total")})))
        c_.commit()
    return out


def _claim(limit: int) -> list[dict]:
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "update ops.candidate_queue q set status = 'in_progress', claimed_by = %s,"
            " updated_at = now()"
            " where q.entity_key in (select entity_key from ops.candidate_queue"
            "   where stage = 'discovered' and status in ('pending', 'in_progress')"
            "   order by entity_key limit %s for update skip locked)"
            " returning q.entity_key, q.source, q.firm_name, q.detail",
            (rl.current_run(), limit))
        rows = cur.fetchall()
        c.commit()
    return [{"entity_key": r[0], "source": r[1], "firm_name": r[2], "detail": r[3] or {}}
            for r in rows]


def _finish(entity_key: str, *, stage: str, status: str, detail_patch: dict) -> None:
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "update ops.candidate_queue set stage = %s, status = %s, updated_at = now(),"
            " detail = coalesce(detail, '{}'::jsonb) || %s::jsonb where entity_key = %s",
            (stage, status, json.dumps(detail_patch, default=str), entity_key))
        c.commit()


def process_tranche(*, limit: int, write: bool) -> dict:
    """Advance up to `limit` candidates through fetch -> extract -> gate. Never raises."""
    from pipeline.bronze import website as web
    from pipeline.gold import gate
    from pipeline.silver import extract as ex
    from pipeline.silver import load as sl

    stats = {"claimed": 0, "gated": 0, "affirm": 0, "needs_evidence": 0, "exclude": 0,
             "no_website": 0, "fetch_failed": 0, "errors": 0}
    if not write:
        return stats  # claiming mutates the queue; a dry-run cycle skips discovery entirely
    tranche = _claim(limit)
    stats["claimed"] = len(tranche)
    for cand in tranche:
        key = cand["entity_key"]
        try:
            site = (cand["detail"] or {}).get("website")
            extract_summary = None
            if site:
                t0 = time.monotonic()
                pages = web.fetch_site(site)
                texted = [p for p in pages if p.text]
                rl.event("discover", "fetch_candidate_site", call_class="external_api",
                         target=site, status="ok" if texted else "error",
                         duration_ms=int((time.monotonic() - t0) * 1000),
                         detail={"entity_key": key, "pages_with_text": len(texted)})
                if texted:
                    db.insert_captures([web._page_to_bronze_row(key.split(":", 1)[-1],
                                                                cand["firm_name"], p)
                                        for p in texted])
                    page_dicts = [{"bronze_id": None, "page_type": p.page_type, "url": p.url,
                                   "title": p.title, "text": p.text} for p in texted]
                    text, _, _, home = sl._combine(page_dicts)
                    result = ex.get_extractor(None).extract(text, source_url=home)
                    usage = result.usage or {}
                    tin = usage.get("prompt_tokens", 0)
                    tout = usage.get("completion_tokens", 0)
                    rl.event("discover", "extract_candidate", call_class="model", target=key,
                             tokens_in=tin, tokens_out=tout,
                             usd=rl.usd_for("gpt-4o-mini", tin, tout))
                    e = result.extraction
                    extract_summary = {"thesis": (e.thesis or "")[:160],
                                       "sectors": e.sectors, "founded_year": e.founded_year,
                                       "team": [{"name": m.name, "title": m.title,
                                                 "principal": m.is_principal} for m in e.team[:12]]}
                else:
                    stats["fetch_failed"] += 1
            else:
                stats["no_website"] += 1

            verdict = gate.run_gate([key], write=True)[0]
            stats["gated"] += 1
            stats[verdict["decision"]] += 1
            _finish(key, stage="gated", status="done",
                    detail_patch={"extracted": extract_summary,
                                  "gate": {"decision": verdict["decision"],
                                           "category": verdict["category"],
                                           "score": verdict["score"]}})
        except Exception as e:  # one candidate must not kill the tranche
            stats["errors"] += 1
            rl.event("discover", "candidate_error", target=key, status="error",
                     detail={"error": repr(e)})
            _finish(key, stage="discovered", status="failed", detail_patch={"error": repr(e)})
    return stats
