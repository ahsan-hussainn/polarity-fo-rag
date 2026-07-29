"""Export the operating ledger in full — the submission's "complete run logs" deliverable.

The brief asks for "the complete run logs for the entire operating window, not only the three
goals: everything the system did while it ran," in a format "raw enough that we can see what the
system actually did, not a narrative of what the final answer claimed."

So this is deliberately a dump, not a report. Every row of every ops table, in JSONL, with no
filtering, no summarising, and no exclusion of runs that failed or were dry — a curated log would
answer a different question than the one being asked. The only thing this file does beyond
`select *` is write a manifest recording what was exported and when, so a reader can tell at a
glance whether they have the whole window.

JSONL rather than CSV because `run_events.detail`, `agent_messages.content` and `runs.summary` are
nested or long, and flattening them into cells is exactly the lossy step the brief warns against.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal

from pipeline import db

# Every table in the operating ledger, with a stable ordering so two exports of the same window
# produce byte-identical files (a diffable artifact is a checkable artifact).
TABLES = {
    "runs": "select * from ops.runs order by run_id",
    "run_events": "select * from ops.run_events order by id",
    "observations": "select * from ops.observations order by id",
    "trust_events": "select * from ops.trust_events order by id",
    "query_log": "select * from ops.query_log order by id",
    "agent_messages": "select * from ops.agent_messages order by run_id, seq",
}


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, memoryview):
        return v.hex()
    return v


def run(out_dir: str = "data/ops_export") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    manifest: dict = {"exported_at": datetime.now().astimezone().isoformat(),
                      "out_dir": out_dir, "tables": {}}

    with db.get_pool().connection() as c:
        for name, sql in TABLES.items():
            path = os.path.join(out_dir, f"{name}.jsonl")
            n = 0
            with c.cursor() as cur, open(path, "w", encoding="utf-8", newline="\n") as fh:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                for row in cur:
                    fh.write(json.dumps({k: _jsonable(v) for k, v in zip(cols, row)},
                                        ensure_ascii=False, default=str) + "\n")
                    n += 1
            manifest["tables"][name] = {"rows": n, "file": f"{name}.jsonl"}

        # Window shape, so a reader can check coverage without parsing every line. Scheduled runs
        # are called out because they are the ones the mandate's window conditions are about.
        with c.cursor() as cur:
            cur.execute("select min(started_at), max(coalesce(finished_at, started_at)), count(*) "
                        "from ops.runs")
            first, last, total = cur.fetchone()
            cur.execute("select trigger, status, count(*) from ops.runs group by 1,2 order by 1,2")
            by_trigger = [{"trigger": a, "status": b, "runs": n} for a, b, n in cur.fetchall()]
    manifest["window"] = {
        "first_run_started": _jsonable(first), "last_run_finished": _jsonable(last),
        "runs_total": total, "runs_by_trigger_and_status": by_trigger,
        "note": ("uncurated: failed runs, dry runs and manual dispatches are all included. Runs "
                 "with trigger='schedule' are the platform-fired cycles."),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest
