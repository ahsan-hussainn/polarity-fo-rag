"""One shared OpenAI client per process (ADR-0017).

Profiling showed each RAG query paid up to three fresh TLS handshakes to OpenAI because
intent.py, embed.py, and answer.py each constructed their own OpenAI() inside the function.
The SDK client holds a keep-alive HTTP connection pool and is thread-safe -- build it once,
reuse it everywhere.
"""
from __future__ import annotations

_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI()
    return _client
