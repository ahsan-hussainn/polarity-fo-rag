"""Run ledger + evidence store for the operating layer (assessment Stage 2; ADR-0027).

Every run (scheduled cycle, goal session, eval pass) opens a row in ops.runs; every discrete
action -- model call, external fetch, retrieval, decision -- writes ops.run_events; per-record
evidence lands in ops.observations; trust decisions in ops.trust_events; every serving query in
ops.query_log. These tables ARE the operating record the stage is judged on: raw, uncurated, and
the source the architecture notes' cost/latency claims are computed from.

Instrumentation is contextual: event()/observe()/trust_event() are silent no-ops unless a run is
active (start_run sets a ContextVar), so library code can log unconditionally and only real runs
accumulate history. log_query() is the exception -- serving queries are logged with or without a
run, and NEVER raise into the answer path.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from contextvars import ContextVar

from pipeline import db

# USD per 1M tokens (input, output). Pinned here so every cost row in the ledger is computed the
# same way; update alongside any model change.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
}

_run_id: ContextVar[int | None] = ContextVar("ops_run_id", default=None)
_log = logging.getLogger("ops.runlog")


def current_run() -> int | None:
    return _run_id.get()


def usd_for(model: str, tokens_in: int = 0, tokens_out: int = 0) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return (tokens_in * pin + tokens_out * pout) / 1_000_000


def _git_sha() -> str | None:
    sha = os.getenv("GITHUB_SHA")  # present on Actions runners; local falls back to git
    if sha:
        return sha[:12]
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def reap_abandoned(older_than_hours: int = 4) -> int:
    """Close out runs that died without calling finish_run, and say so.

    A process killed mid-cycle (a runner timeout, a cancelled job, a crash) leaves ops.runs.status
    stuck at 'running' forever with its cost columns at zero, while its real spend sits in
    run_events. Any total read from ops.runs then silently undercounts. This marks such runs
    'abandoned' and rolls up the usage they did record -- bookkeeping, not history rewriting: the
    events are untouched and the status change is itself visible in the export.
    """
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "update ops.runs set status = 'abandoned', finished_at = now(),"
            " error = coalesce(error, 'run ended without finish_run (process died); closed out by "
            "the next run''s reaper'),"
            " tokens_in  = coalesce((select sum(tokens_in)  from ops.run_events e where e.run_id = ops.runs.run_id), 0),"
            " tokens_out = coalesce((select sum(tokens_out) from ops.run_events e where e.run_id = ops.runs.run_id), 0),"
            " usd_est    = coalesce((select sum(usd_est)    from ops.run_events e where e.run_id = ops.runs.run_id), 0)"
            " where status = 'running' and started_at < now() - make_interval(hours => %s)",
            (older_than_hours,))
        return cur.rowcount or 0


def start_run(kind: str, trigger: str, config: dict | None = None) -> int:
    try:
        reap_abandoned()
    except Exception:
        pass  # bookkeeping must never stop a run from starting
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "insert into ops.runs (kind, trigger, git_sha, config) "
            "values (%s, %s, %s, %s::jsonb) returning run_id",
            (kind, trigger, _git_sha(), json.dumps(config or {})))
        rid = cur.fetchone()[0]
    _run_id.set(rid)
    return rid


def finish_run(status: str = "ok", *, error: str | None = None, summary: dict | None = None) -> None:
    rid = _run_id.get()
    if rid is None:
        return
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "update ops.runs set finished_at = now(), status = %s, error = %s, summary = %s::jsonb,"
            " tokens_in  = coalesce((select sum(tokens_in)  from ops.run_events where run_id = %s), 0),"
            " tokens_out = coalesce((select sum(tokens_out) from ops.run_events where run_id = %s), 0),"
            " usd_est    = coalesce((select sum(usd_est)    from ops.run_events where run_id = %s), 0)"
            " where run_id = %s",
            (status, error, json.dumps(summary or {}, default=str), rid, rid, rid, rid))
    _run_id.set(None)


def event(phase: str, name: str, *, call_class: str | None = None, target: str | None = None,
          status: str = "ok", duration_ms: int | None = None, tokens_in: int | None = None,
          tokens_out: int | None = None, usd: float | None = None,
          detail: dict | None = None) -> None:
    rid = _run_id.get()
    if rid is None:
        return
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "insert into ops.run_events (run_id, phase, event, call_class, target, status,"
            " duration_ms, tokens_in, tokens_out, usd_est, detail)"
            " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (rid, phase, name, call_class, target, status, duration_ms, tokens_in, tokens_out,
             usd, json.dumps(detail or {}, default=str)))


def observe(crd: str, kind: str, value: str | None, *, url: str | None = None,
            detail: dict | None = None) -> None:
    rid = _run_id.get()
    if rid is None:
        return
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "insert into ops.observations (run_id, crd, kind, value, url, detail)"
            " values (%s,%s,%s,%s,%s,%s::jsonb)",
            (rid, crd, kind, value, url, json.dumps(detail or {}, default=str)))


def save_messages(messages: list[dict], *, phase: str = "session", start_seq: int = 0) -> int:
    """Persist an agent session's message trace verbatim (ADR-0038). Returns rows written.

    Verbatim matters: this is the artifact a reviewer reads to see what the system actually did,
    so tool results are stored as returned rather than summarised, and the repair turn is stored
    under its own phase so a retry is visible AS a retry.
    """
    rid = _run_id.get()
    if rid is None or not messages:
        return 0
    rows = []
    for i, m in enumerate(messages):
        tc = m.get("tool_calls")
        rows.append((rid, start_seq + i, m.get("role") or "?", m.get("content"),
                     json.dumps(tc, default=str) if tc else None, phase))
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.executemany(
            "insert into ops.agent_messages (run_id, seq, role, content, tool_calls, phase)"
            " values (%s,%s,%s,%s,%s::jsonb,%s) on conflict (run_id, seq) do nothing", rows)
    return len(rows)


def latest_observation(crd: str, kind: str, *, exclude_run: int | None = None):
    """Most recent observation for (crd, kind) from an EARLIER run -- the comparison baseline.

    Returns (value, observed_at, run_id) or None. exclude_run keeps a run from comparing against
    its own writes (cross-run means cross-run)."""
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "select value, observed_at, run_id from ops.observations"
            " where crd = %s and kind = %s and (%s::bigint is null or run_id <> %s)"
            " order by observed_at desc limit 1",
            (crd, kind, exclude_run, exclude_run))
        return cur.fetchone()


def observation_history(crd: str, kind: str, *, limit: int = 6, exclude_run: int | None = None):
    """The last `limit` observations for (crd, kind), oldest first.

    Comparing only against the previous run cannot tell a change from an oscillation: a value that
    was superseded and has now returned looks identical to a new value that reproduced. Telling
    those apart needs the sequence, not the last element.
    """
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "select value, observed_at, run_id from ops.observations"
            " where crd = %s and kind = %s and (%s::bigint is null or run_id <> %s)"
            " order by observed_at desc limit %s",
            (crd, kind, exclude_run, exclude_run, limit))
        return list(reversed(cur.fetchall()))


def trust_event(crd: str, check_type: str, prior: str | None, current: str | None,
                evidence: str, action: str) -> None:
    rid = _run_id.get()
    if rid is None:
        return
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute(
            "insert into ops.trust_events (run_id, crd, check_type, prior, current, evidence, action)"
            " values (%s,%s,%s,%s,%s,%s,%s)",
            (rid, crd, check_type, prior, current, evidence, action))


def log_query(*, source: str, query: str, intent: str | None = None,
              nearest_distance: float | None = None, outcome: str,
              verification: dict | None = None, latency_ms: int | None = None) -> None:
    """ADR-0026 Layer 3. Always attempted (run or no run); NEVER raises into the answer path."""
    try:
        with db.get_pool().connection() as c, c.cursor() as cur:
            cur.execute(
                "insert into ops.query_log (source, query, intent, nearest_distance, outcome,"
                " verification, latency_ms, run_id) values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (source, query, intent, nearest_distance, outcome,
                 json.dumps(verification or {}, default=str), latency_ms, _run_id.get()))
    except Exception:
        _log.warning("query_log write failed (answer path unaffected)", exc_info=True)
