"""FastAPI service for the Micro-RAG (ADR-0014).

One app serves both halves from the same origin: GET / returns the single-page UI, POST /query runs the
grounded retrieval. No separate frontend, no CORS, no build step -- one deployable Python unit. State
lives in Supabase (already deployed); this service is stateless compute. Run locally with
`uvicorn pipeline.rag.app:app --reload`; deployed the same way on Render (see render.yaml).
"""
from __future__ import annotations

import json
import logging
import pathlib

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from pipeline.rag.answer import answer, answer_stream

app = FastAPI(title="PolarityIQ Micro-RAG", description="Grounded Q&A over a decision-grade FO dataset")
_HTML = (pathlib.Path(__file__).parent / "index.html").read_text(encoding="utf-8")
_AGENT_HTML = (pathlib.Path(__file__).parent / "agent.html").read_text(encoding="utf-8")


class Query(BaseModel):
    question: str
    k: int = 5


class Goal(BaseModel):
    goal: str


class FitQuery(BaseModel):
    mandate: str
    sector_terms: list[str] | None = None
    min_aum_usd: int | None = None
    max_aum_usd: int | None = None
    k: int = 10


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _HTML


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query")
def query(q: Query):
    if not q.question.strip():
        return JSONResponse({"error": "empty question"}, status_code=400)
    try:
        return answer(q.question, k=min(max(q.k, 1), 10), source="api")
    except Exception:
        # Log the full traceback server-side (Render logs); never echo error internals to the browser
        # -- an exception message can contain secrets (e.g. an auth header), so keep it off the wire.
        logging.getLogger("uvicorn.error").exception("query failed")
        return JSONResponse({"error": "The service hit an internal error answering that query."},
                            status_code=500)


@app.post("/fit")
def fit(q: FitQuery):
    """The Stage 2 retrieval extension (ADR-0030), served directly: rank every qualifying record
    for an investor mandate, with per-record component scores, evidence, caveats, and an
    evidence-based confidence tier. Same capability the agent calls as a tool; this route is the
    manual-retrieval path the goal artifacts compare against."""
    if not q.mandate.strip():
        return JSONResponse({"error": "empty mandate"}, status_code=400)
    try:
        from pipeline.rag.fit import fit_rank

        return fit_rank(q.mandate, sector_terms=q.sector_terms or [],
                        min_aum=q.min_aum_usd, max_aum=q.max_aum_usd,
                        k=min(max(q.k, 1), 24))
    except Exception:
        logging.getLogger("uvicorn.error").exception("fit failed")
        return JSONResponse({"error": "The service hit an internal error ranking that mandate."},
                            status_code=500)


@app.get("/stats")
def stats():
    """Live release-state counts, regenerated from the dataset on every call. The UI reads its
    coverage number from here so no surface ever hand-carries a count that can drift."""
    from pipeline import db

    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute("select release_state, count(*) from gold.records group by release_state")
        counts = {row[0]: row[1] for row in cur.fetchall()}
    return {"qualifying": counts.get("qualifying", 0), "by_release_state": counts}


@app.get("/agent", response_class=HTMLResponse)
def agent_page() -> str:
    return _AGENT_HTML


@app.get("/agent/tools")
def agent_tools():
    """The agent's tool interfaces, live -- the schema deliverable, served from the running code."""
    from pipeline.agent.tools import openai_tools

    return {"tools": openai_tools()}


@app.post("/agent/goal")
def agent_goal(g: Goal):
    """Run one goal session (ADR-0031). Synchronous: a session is a few tool-calling model turns
    (~15-60s). The response carries the structured answer, the release-check verdict, and the
    run_id whose ops.run_events rows are the raw, unedited session log."""
    if not g.goal.strip():
        return JSONResponse({"error": "empty goal"}, status_code=400)
    try:
        from pipeline.agent.loop import run_goal

        return run_goal(g.goal, trigger="api")
    except Exception:
        logging.getLogger("uvicorn.error").exception("agent goal failed")
        return JSONResponse({"error": "The agent hit an internal error on that goal."},
                            status_code=500)


@app.post("/query/stream")
def query_stream(q: Query):
    """Streaming twin of /query (ADR-0017): NDJSON events -- one 'meta' line (intent + sources,
    sent the moment retrieval finishes, so the UI renders coverage immediately), then 'delta'
    lines as the grounded answer generates, then 'done'. The UI reads this; /query stays the
    plain request/response contract for the CLI and API clients."""
    if not q.question.strip():
        return JSONResponse({"error": "empty question"}, status_code=400)

    def gen():
        try:
            for event in answer_stream(q.question, k=min(max(q.k, 1), 10), source="ui"):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception:
            logging.getLogger("uvicorn.error").exception("stream query failed")
            yield json.dumps({"type": "error",
                              "error": "The service hit an internal error answering that query."}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
