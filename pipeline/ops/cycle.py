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

import contextvars
import hashlib
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline import config, db
from pipeline.ops import runlog as rl

OBSERVE_WORKERS = 8       # bounded pool: one home-page fetch per distinct firm domain
FETCH_TIMEOUT = 15
RECLASSIFY_WORKERS = int(os.getenv("OPS_RECLASSIFY_WORKERS", "6"))
DISCOVER_PER_CYCLE = int(os.getenv("OPS_DISCOVER_PER_CYCLE", "15"))
RESOLVE_PER_CYCLE = int(os.getenv("OPS_RESOLVE_PER_CYCLE", "40"))
# Promotion re-extracts each promoted firm into silver (one model call each), so it is budgeted
# like discovery rather than left unbounded (ADR-0034).
PROMOTE_PER_CYCLE = int(os.getenv("OPS_PROMOTE_PER_CYCLE", "25"))
# One government API rather than N independent hosts, so the polite ceiling is well below the
# website sweep's worker count (ADR-0036).
REGISTRY_WORKERS = int(os.getenv("OPS_REGISTRY_WORKERS", "4"))


def reclassify_budget(monitored: int) -> int:
    """Per-cycle re-extraction budget, scaled to the size of the set being kept current.

    This was a flat 10, which was the system's FIRST hard bottleneck and a near one: the measured
    home-page change rate is ~11.4% per cycle, so a flat 10 starts refusing work at ~88 records
    (0.114 x N > 10). Run 15 hit 9 changed against the cap of 10 with only 50 records held.

    Worse than a delay, a flat cap does not converge. A skipped record keeps its old hash, so it
    re-counts as changed on the next cycle: at 500 records ~57 change per cycle against a budget of
    10, and the backlog grows without bound. The mandate's second half -- "keep all 500 current" --
    is not satisfiable under a constant budget, whatever the constant is.

    So the budget scales with the set (30%, floor 25), which covers the measured change rate ~2.6x
    over. It stays a budget rather than becoming unbounded: an unattended loop that will spend
    arbitrarily much on one cycle is its own hazard, and skips remain logged, never silent.
    """
    return max(25, math.ceil(0.30 * monitored))


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


def _fetch_registry(crd: str) -> dict:
    """One firm's current IAPD registration record, timed and ledgered (ADR-0036)."""
    from pipeline.bronze import iapd

    t0 = time.monotonic()
    snap = iapd.fetch_firm(crd, timeout=FETCH_TIMEOUT)
    rl.event("observe", "fetch_registry", call_class="external_api", target=crd,
             status="ok" if snap.get("found") else "error",
             duration_ms=int((time.monotonic() - t0) * 1000),
             detail={"crd": crd, "found": snap.get("found"), "scope": snap.get("ia_scope"),
                     "filing_date": snap.get("adv_filing_date")})
    return snap


def _observe_phase(firms: list[dict], workers: int, *, write: bool) -> dict:
    stats = {"monitored": len(firms), "fetched": 0, "fetch_errors": 0,
             "baselined": 0, "changed": 0, "dark": 0, "adv_filing_moved": 0,
             "registration_inactive": 0, "registry_name_changed": 0, "registry_missing": 0,
             "registry_checked": 0, "registry_errors": 0,
             "material": 0, "cosmetic": 0, "unconfirmed": 0, "reclassify_skipped": 0,
             "reclassify_budget": reclassify_budget(len(firms))}
    rid = rl.current_run()
    changed: list[tuple] = []

    # A dry run must not write into the chain that scheduled runs compare against: observations
    # and trust events from a laptop would become some future cycle's "previous run" baseline, and
    # cross-run evidence would be measuring a local test. Reads still happen; only writes are held.
    def observe(*a, **kw):
        if write:
            rl.observe(*a, **kw)

    def trust_event(*a, **kw):
        if write:
            rl.trust_event(*a, **kw)

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

    # The regulator's current record for every held CRD (ADR-0036). Fewer workers than the website
    # sweep on purpose: this is one government API rather than N independent hosts, so the polite
    # concurrency ceiling is much lower.
    registry: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=REGISTRY_WORKERS) as pool:
        futs = {pool.submit(_fetch_registry, f["crd"]): f["crd"] for f in firms}
        for fut in as_completed(futs):
            crd = futs[fut]
            try:
                snap = fut.result()
            except Exception as e:
                stats["registry_errors"] += 1
                rl.event("observe", "fetch_registry", call_class="external_api", target=crd,
                         status="error", detail={"crd": crd, "error": repr(e)})
                continue
            stats["registry_checked"] += 1
            registry[crd] = snap

    for f in firms:
        crd = f["crd"]

        # The registry detector compares the REGULATOR'S current record against what we hold
        # (ADR-0036). It previously compared our held filing date against our own previous
        # observation of that same held value -- which nothing in the cycle updates, so it could
        # not fire, and did not: 772 observations, zero events.
        reg = registry.get(crd)
        if reg is not None and reg.get("found"):
            live_filed = reg.get("adv_filing_date")
            held_filed = str(f["data_asof"]) if f.get("data_asof") else None
            if live_filed:
                observe(crd, "adv_filing_date_live", live_filed)
                if held_filed and live_filed > held_filed:
                    stats["adv_filing_moved"] += 1
                    trust_event(crd, "adv_filing", held_filed, live_filed,
                                   f"the adviser's current IAPD record shows a filing dated "
                                   f"{live_filed}; the record we hold was built from the "
                                   f"{held_filed} filing, so ADV-derived cells (AUM, address, "
                                   f"phone, client mix) may be superseded", "flagged")
            scope = reg.get("ia_scope")
            if scope:
                prior_scope = rl.latest_observation(crd, "adv_registration_scope", exclude_run=rid)
                observe(crd, "adv_registration_scope", scope)
                # Stronger than a filing bump: a firm that is no longer a registered adviser
                # invalidates the BASIS of every ADV-derived cell, not just their currency.
                if scope != "ACTIVE":
                    stats["registration_inactive"] += 1
                    if not prior_scope or prior_scope[0] == "ACTIVE":
                        trust_event(crd, "adv_registration_lapsed",
                                       (prior_scope[0] if prior_scope else "ACTIVE"), scope,
                                       f"IAPD now reports this adviser's registration as {scope}; "
                                       "ADV-derived cells rest on a registration that is no longer "
                                       "current", "flagged")
            live_name = (reg.get("firm_name") or "").strip()
            held_name = (f.get("family_office_name") or "").strip()
            if live_name and held_name and live_name.upper() != held_name.upper():
                stats["registry_name_changed"] += 1
                observe(crd, "adv_firm_name", live_name)
                trust_event(crd, "adv_name_changed", held_name, live_name,
                               "the adviser's registered name at IAPD differs from the name on "
                               "the held record; this is an identity event, not a cosmetic one",
                               "flagged")
        elif reg is not None and reg.get("found") is False:
            stats["registry_missing"] += 1
            prior_seen = rl.latest_observation(crd, "adv_registration_scope", exclude_run=rid)
            observe(crd, "adv_registration_scope", "not_found")
            if prior_seen and prior_seen[0] != "not_found":
                trust_event(crd, "adv_registration_gone", prior_seen[0], "not_found",
                               "this CRD no longer resolves to a firm record at IAPD; the "
                               "regulatory basis for the held record cannot be re-checked",
                               "flagged")
        observe(crd, "email_grades",
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
        observe(crd, "website_http_status",
                   str(r["status"]) if r["status"] is not None else f"error:{r['error']}",
                   url=r["url"])
        if r["hash"]:
            observe(crd, "website_home_hash", r["hash"], url=r["url"])

        # Cross-run comparison -- the evidence-based staleness the mandate's condition 3 requires.
        now_desc = f"HTTP {r['status']}" if r["status"] is not None else (r["error"] or "unreachable")
        if prior_status and prior_status[0] == "200" and r["status"] != 200:
            stats["dark"] += 1
            trust_event(crd, "website_dark", prior_status[0], now_desc,
                           f"home page was reachable (HTTP 200) at run {prior_status[2]} "
                           f"({prior_status[1]:%Y-%m-%d %H:%M}Z) and now returns {now_desc}; the "
                           "source may have gone dark -- trust reduced pending next cycle's re-check",
                           "flagged")
        elif prior_hash and r["hash"] and prior_hash[0] != r["hash"]:
            stats["changed"] += 1
            if not write:
                trust_event(crd, "website_change", prior_hash[0][:16], r["hash"][:16],
                               "home-page text changed (dry-run: materiality not classified)",
                               "flagged")
            else:
                changed.append((f, prior_hash, r["hash"]))
        elif not prior_hash and r["hash"]:
            stats["baselined"] += 1

    if write and changed:
        _classify_changed(changed, stats, workers=RECLASSIFY_WORKERS,
                          budget=reclassify_budget(len(firms)))
    return stats


def _last_classified(crds: list[str]) -> dict[str, object]:
    """When each firm was last materiality-classified, from the fact fingerprints classification
    writes. Drives fairness: without it, a budget always spends itself on whichever records the
    query happened to order first, and the same tail starves every cycle."""
    if not crds:
        return {}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, max(observed_at) from ops.observations "
                    "where kind = 'fact_fingerprint' and crd = any(%s) group by crd", (crds,))
        return {r[0]: r[1] for r in cur.fetchall()}


def _classify_changed(changed: list[tuple], stats: dict, *, workers: int, budget: int) -> None:
    """Classify changed firms concurrently, oldest-unchecked first, within the cycle's budget.

    Two things this must not get wrong:

    - **Fairness.** Ordered by least-recently-classified (never-classified first), so a record
      cannot be perpetually deferred by a busy cycle. Under the old serial code the order was
      whatever `gold.records order by crd` produced, which starves the tail of the alphabet.
    - **Run context.** `runlog` resolves the current run from a ContextVar, and ContextVars do NOT
      propagate into ThreadPoolExecutor workers. Submitting classify() naively would leave every
      trust_event and observation inside it silently no-opping -- the cycle would look healthy and
      produce no staleness evidence at all, which is the one thing window-condition 3 rests on. So
      each task runs inside a copy of the submitting context. The copy must be made PER TASK: a
      Context cannot be entered by two threads at once, and sharing one raises "cannot enter
      context: ... is already entered" on every task but the first. Measured, not theorised --
      run 16 classified 1 of 3 changed records that way before this was fixed.
    """
    from pipeline.ops import materiality

    last = _last_classified([f["crd"] for f, _, _ in changed])
    EPOCH = __import__("datetime").datetime.min.replace(tzinfo=__import__("datetime").timezone.utc)
    ordered = sorted(changed, key=lambda t: last.get(t[0]["crd"]) or EPOCH)
    doing, deferred = ordered[:budget], ordered[budget:]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(contextvars.copy_context().run,
                            materiality.classify, f, write=True, prior_run=prior): f["crd"]
                for f, prior, _ in doing}
        for fut in as_completed(futs):
            try:
                verdict = fut.result()
            except Exception as e:  # classify() already swallows per-firm errors; belt-and-braces
                rl.event("observe", "materiality_error", target=futs[fut], status="error",
                         detail={"error": repr(e)})
                continue
            v = verdict.get("verdict")
            if v == "material":
                stats["material"] += 1
            elif v == "cosmetic":
                stats["cosmetic"] += 1
            elif v == "unconfirmed":
                stats["unconfirmed"] = stats.get("unconfirmed", 0) + 1

    for f, prior_hash, new_hash in deferred:
        stats["reclassify_skipped"] += 1
        rl.event("observe", "materiality_skip", target=f["crd"], status="skipped",
                 detail={"reason": f"per-cycle re-extraction budget ({budget}) reached",
                         "last_classified": str(last.get(f["crd"]) or "never")})
        rl.trust_event(f["crd"], "website_change", prior_hash[0][:16], new_hash[:16],
                       f"home-page text changed but this cycle's re-extraction budget ({budget}) "
                       "is spent; this record is first in line next cycle (oldest-unchecked "
                       "ordering); flag stands", "flagged")


def _rebuild_phase(write: bool) -> dict:
    from pipeline import reconcile as rec
    from pipeline.gold import build as gb
    from pipeline.rag import embed

    out: dict = {}

    t0 = time.monotonic()
    g = gb.build(write=write)
    rl.event("rebuild", "build_gold", call_class="db", duration_ms=int((time.monotonic() - t0) * 1000),
             detail={"firms": g.get("firms"), "with_primary": g.get("with_primary"),
                     "by_release": g.get("by_release")})
    out["gold_firms"] = g.get("firms")
    out["by_release"] = g.get("by_release")

    if write:
        # PRE-PUBLICATION GATE. The database-only checks run BEFORE the CSVs and the retrieval
        # index are written, so an inconsistent state is prevented rather than reported. On
        # scheduled run 20 the post-hoc version correctly failed the run -- 37 minutes after
        # shipping the inconsistent export to the live surface, which is the wrong half of the job.
        # The full check still runs after publication (below), because surface-vs-CSV agreement
        # cannot be tested until the CSVs exist.
        t0 = time.monotonic()
        pre = rec.run(db_only=True)
        rl.event("rebuild", "reconcile_pre", call_class="db",
                 status="ok" if pre["all_agree"] else "error",
                 duration_ms=int((time.monotonic() - t0) * 1000),
                 detail={"passed": pre["passed"], "checks": pre["checks"],
                         "failures": pre["failures"]})
        out["reconcile_pre"] = f"{pre['passed']}/{pre['checks']}"
        if not pre["all_agree"]:
            raise RuntimeError(
                f"pre-publication release control failed, nothing was exported: {pre['failures']}")

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
        # Resolve before discovering: a candidate whose domain is recovered this cycle is
        # re-queued, so the discovery tranche below can pick it up with the site evidence the
        # registry never carried, instead of gating it blind and excluding it on thin evidence.
        from pipeline.ops import resolve
        out["resolve"] = resolve.run(limit=RESOLVE_PER_CYCLE, write=write)

        from pipeline.ops import discovery
        out["discover"] = discovery.process_tranche(limit=DISCOVER_PER_CYCLE, write=write)
        # Promote AFTER discovery so affirms gated this cycle can release on this same cycle, and
        # BEFORE rebuild so the promoted silver rows are picked up by the build below (ADR-0034).
        from pipeline.ops import promote
        out["promote"] = promote.run(limit=PROMOTE_PER_CYCLE, write=write)
        out["rebuild"] = _rebuild_phase(write)
        out["status"] = "ok"
    except Exception as e:
        out["status"] = "failed"
        out["error"] = repr(e)
    out["duration_s"] = round(time.monotonic() - t0, 1)
    rl.finish_run(out["status"], error=out.get("error"), summary=out)
    return out
