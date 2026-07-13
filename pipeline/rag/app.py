"""FastAPI service for the Micro-RAG (ADR-0014).

One app serves both halves from the same origin: GET / returns the single-page UI, POST /query runs the
grounded retrieval. No separate frontend, no CORS, no build step -- one deployable Python unit. State
lives in Supabase (already deployed); this service is stateless compute. Run locally with
`uvicorn pipeline.rag.app:app --reload`; deployed the same way on Render (see render.yaml).
"""
from __future__ import annotations

import logging
import pathlib

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from pipeline.rag.answer import answer

app = FastAPI(title="PolarityIQ Micro-RAG", description="Grounded Q&A over a decision-grade FO dataset")
_HTML = (pathlib.Path(__file__).parent / "index.html").read_text(encoding="utf-8")


class Query(BaseModel):
    question: str
    k: int = 5


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
        return answer(q.question, k=min(max(q.k, 1), 10))
    except Exception:
        # Log the full traceback server-side (Render logs); never echo error internals to the browser
        # -- an exception message can contain secrets (e.g. an auth header), so keep it off the wire.
        logging.getLogger("uvicorn.error").exception("query failed")
        return JSONResponse({"error": "The service hit an internal error answering that query."},
                            status_code=500)
