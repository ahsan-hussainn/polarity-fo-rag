"""FastAPI service for the Micro-RAG (ADR-0014).

One app serves both halves from the same origin: GET / returns the single-page UI, POST /query runs the
grounded retrieval. No separate frontend, no CORS, no build step -- one deployable Python unit. State
lives in Supabase (already deployed); this service is stateless compute. Run locally with
`uvicorn pipeline.rag.app:app --reload`; deployed the same way on Render (see render.yaml).
"""
from __future__ import annotations

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
    except Exception as e:  # never leak a stack trace to the browser, but keep the root cause
        detail = f"{type(e).__name__}: {e}"
        cause = e.__cause__ or e.__context__
        if cause is not None:
            detail += f" | cause: {type(cause).__name__}: {cause}"
        return JSONResponse({"error": detail}, status_code=500)
