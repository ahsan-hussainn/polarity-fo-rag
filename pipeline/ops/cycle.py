"""One operating cycle: the unit of unattended work (assessment Stage 2; ADR-0027).

A cycle is REVISIT -> COMPARE -> ACT -> REBUILD -> ACCOUNT. It observes every held record's
external evidence (website reachability + normalized home-page text hash; the held ADV filing
date; current email grades) into ops.observations, compares each against the most recent
observation from an EARLIER run, and writes ops.trust_events where the evidence moved -- the
cross-run, evidence-based staleness the mandate requires (a later cycle contradicting what an
earlier cycle recorded; never a clock expiry). It then rebuilds gold, re-exports the product CSVs,
refreshes the retrieval index incrementally, and runs the reconcile release control, so the product
surface always serves what the system currently believes -- and closes its ledger row with
tokens/cost/duration so every cycle accounts for itself.

Website changes are classified for MATERIALITY (day-2, pipeline/ops/materiality.py): a hash flip
triggers re-fetch + re-extraction and a field-level diff -- cosmetic changes are noted, material
ones refresh silver through the standard path, and a vanished ratified decision-maker is flagged
for human re-adjudication. Re-extraction is budget-capped per cycle with logged skips. Discovery
tranches enter once the automated inclusion standard exists. A cycle never dies on one record:
per-record failures are logged as events and the cycle continues; a reconcile failure fails the
RUN (a release control that does not control the run's status would be Stage 1's named mistake).
"""
from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline import config, db
from pipeline.ops import runlog as rl

OBSERVE_WORKERS = 8       # bounded pool: one home-page fetch per distinct firm domain
FETCH_TIMEOUT = 15


MAX_RECLASSIFY_PER_CYCLE = 10  # LLM re-extraction budget per cycle; skips are logged, never silent


def _monitored_firms() -> list[dict]:
    """Everything the system holds -- qualifying, reclassified, and quarantined alike. Quarantine
    removes a record from the product, not from monitoring; evidence can rehabilitate or worsen."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, family_office_name, website, release_state, data_asof,"
                    " primary_contact_name, primary_email_grade, secondary_email_grade"
                    " from gold.records order by crd")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _fetch_home(url: str) -> dict:
    """Status + normalized text hash of a firm's home page. Never raises."""
    from pipeline.bronze import website as web

    t0 = time.monotonic()
    normalized = web._normalize(url)
    if not normalized:
        return {"status": None, "hash": None, "error": "bad_url", "duration_ms": 0, "url": url}
    page, _ = web._page(normalized, "home", FETCH_TIMEOUT, config.WEB_UA)
    dur = int((time.monotonic() - t0) * 1000)
    text_hash = hashlib.sha256(page.text.lower().encode("utf-8")).hexdigest() if page.text else None
    return {"status": page.http_status, "hash": text_hash, "error": page.error,
            "duration_ms": dur, "url": page.url}


def _observe_phase(firms: list[dict], workers: int, *, write: bool) -> dict:
    stats = {"monitored": len(firms), "fetched": 0, "fetch_errors": 0,
             "baselined": 0, "changed": 0, "dark": 0, "adv_filing_moved": 0,
             "material": 0, "cosmetic": 0, "reclassify_skipped": 0}
    rid = rl.current_run()
    reclassified = 0

    with_sites = [f for f in firms if f.get("website")]
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_fetch_home, f["website"]): f["crd"] for f in with_sites}
        for fut in as_completed(futs):
            crd = futs[fut]
            try:
                results[crd] = fut.result()
            except Exception as e:  # _fetch_home shouldn't raise; belt-and-braces per record
                results[crd] = {"status": None, "hash": None, "error": repr(e),
                                "duration_ms": None, "url": None}

    for f in firms:
        crd = f["crd"]

        # Non-fetch baselines: the held ADV filing date (detector: new/amended SEC filing) and the
        # current email grades (detector: vendor re-verification flips, day-2+).
        if f.get("data_asof"):
            held = str(f["data_asof"])
            prior = rl.latest_observation(crd, "adv_filing_date", exclude_run=rid)
            rl.observe(crd, "adv_filing_date", held)
            if prior and prior[0] != held:
                stats["adv_filing_moved"] += 1
                rl.trust_event(crd, "adv_filing", prior[0], held,
                               f"SEC ADV latest filing date moved since run {prior[2]}: "
                               f"{prior[0]} -> {held} (a new or amended filing reached bronze); "
                               "held firm facts may be superseded", "flagged")
        rl.observe(crd, "email_grades",
                   f"{f.get('primary_email_grade') or '-'}/{f.get('secondary_email_grade') or '-'}")

        r = results.get(crd)
        if r is None:
            continue
        stats["fetched"] += 1
        rl.event("observe", "fetch_home", call_class="external_api", target=r["url"] or f.get("website"),
                 status="ok" if r["error"] is None else "error", duration_ms=r["duration_ms"],
                 detail={"crd": crd, "http_status": r["status"], "error": r["error"]})
        if r["error"] is not None:
            stats["fetch_errors"] += 1

        prior_status = rl.latest_observation(crd, "website_http_status", exclude_run=rid)
        prior_hash = rl.latest_observation(crd, "website_home_hash", exclude_run=rid)
        rl.observe(crd, "website_http_status",
                   str(r["status"]) if r["status"] is not None else f"error:{r['error']}",
                   url=r["url"])
        if r["hash"]:
            rl.observe(crd, "website_home_hash", r["hash"], url=r["url"])

        # Cross-run comparison -- the evidence-based staleness the mandate's condition 3 requires.
        now_desc = f"HTTP {r['status']}" if r["status"] is not None else (r["error"] or "unreachable")
        if prior_status and prior_status[0] == "200" and r["status"] != 200:
            stats["dark"] += 1
            rl.trust_event(crd, "website_dark", prior_status[0], now_desc,
                           f"home page was reachable (HTTP 200) at run {prior_status[2]} "
                           f"({prior_status[1]:%Y-%m-%d %H:%M}Z) and now returns {now_desc}; the "
                           "source may have gone dark -- trust reduced pending next cycle's re-check",
                           "flagged")
        elif prior_hash and r["hash"] and prior_hash[0] != r["hash"]:
            stats["changed"] += 1
            if not write:
                rl.trust_event(crd, "website_change", prior_hash[0][:16], r["hash"][:16],
                               "home-page text changed (dry-run: materiality not classified)",
                               "flagged")
            elif reclassified >= MAX_RECLASSIFY_PER_CYCLE:
                stats["reclassify_skipped"] += 1
                rl.event("observe", "materiality_skip", target=crd, status="skipped",
                         detail={"reason": f"per-cycle re-extraction budget "
                                           f"({MAX_RECLASSIFY_PER_CYCLE}) reached"})
                rl.trust_event(crd, "website_change", prior_hash[0][:16], r["hash"][:16],
                               "home-page text changed but this cycle's re-extraction budget is "
                               "spent; flag stands, classification next cycle", "flagged")
            else:
                reclassified += 1
                from pipeline.ops import materiality
                verdict = materiality.classify(f, write=write, prior_run=prior_hash)
                if verdict["verdict"] == "material":
                    stats["material"] += 1
                elif verdict["verdict"] == "cosmetic":
                    stats["cosmetic"] += 1
        elif not prior_hash and r["hash"]:
            stats["baselined"] += 1
    return stats


def _rebuild_phase(write: bool) -> dict:
    from pipeline import reconcile as rec
    from pipeline.gold import build as gb
    from pipeline.rag import embed

    out: dict = {}

    t0 = time.monotonic()
    g = gb.build(write=write)
    rl.event("rebuild", "build_gold", call_class="db", duration_ms=int((time.monotonic() - t0) * 1000),
             detail={"firms": g.get("firms"), "with_primary": g.get("with_primary")})
    out["gold_firms"] = g.get("firms")

    if write:
        t0 = time.monotonic()
        exp = gb.export()
        rl.event("rebuild", "gold_export", call_class="db",
                 duration_ms=int((time.monotonic() - t0) * 1000), detail=exp)

        t0 = time.monotonic()
        idx = embed.build_index(write=True, incremental=True)
        tokens = idx.get("tokens", 0)
        rl.event("rebuild", "rag_index", call_class="model", status="ok",
                 duration_ms=int((time.monotonic() - t0) * 1000),
                 tokens_in=tokens, tokens_out=0, usd=rl.usd_for(embed.EMBED_MODEL, tokens),
                 detail={"documents": idx.get("documents"), "embedded": idx.get("embedded"),
                         "removed_stale_docs": idx.get("removed_stale_docs")})
        out["index"] = {"embedded": idx.get("embedded"), "of": idx.get("documents")}

        t0 = time.monotonic()
        r = rec.run()
        rl.event("rebuild", "reconcile", call_class="db",
                 status="ok" if r["all_agree"] else "error",
                 duration_ms=int((time.monotonic() - t0) * 1000),
                 detail={"passed": r["passed"], "checks": r["checks"], "failures": r["failures"]})
        out["reconcile"] = f"{r['passed']}/{r['checks']}"
        if not r["all_agree"]:
            raise RuntimeError(f"reconcile release control failed: {r['failures']}")
    return out


def run_cycle(*, write: bool = True, trigger: str = "local",
              workers: int = OBSERVE_WORKERS) -> dict:
    """Run one cycle. Never raises: failures land in the ledger and in the returned status, so the
    scheduler's exit code (and run history) reflects them without losing the run record."""
    rid = rl.start_run("cycle", trigger, config={"write": write, "workers": workers})
    out: dict = {"run_id": rid, "trigger": trigger, "write": write}
    t0 = time.monotonic()
    try:
        firms = _monitored_firms()
        out["observe"] = _observe_phase(firms, workers, write=write)
        out["rebuild"] = _rebuild_phase(write)
        out["status"] = "ok"
    except Exception as e:
        out["status"] = "failed"
        out["error"] = repr(e)
    out["duration_s"] = round(time.monotonic() - t0, 1)
    rl.finish_run(out["status"], error=out.get("error"), summary=out)
    return out
