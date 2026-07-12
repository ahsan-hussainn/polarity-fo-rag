"""API email verification behind a provider-agnostic seam (ADR-0005 fallback, ADR-0010).

SMTP RCPT from a single host cannot confirm mailboxes on anti-harvesting providers (M365 rejects every
external probe -- see docs/findings/validation-layer.md). A verification API runs warmed IP pools and
provider-specific logic that get truthful answers, which is how a real product (incl. FO-MAX, whose
schema exposes a validation code + explanation + quality grade) confirms emails. This module wraps such
a service behind one interface so the vendor is swappable, exactly like the extraction seam (ADR-0008).

Default provider: MillionVerifier (generous free tier, simple single-email endpoint). A MockVerifier
gives a deterministic offline double so the pipeline and grading can be tested with no key and no spend.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

try:  # load MILLIONVERIFIER_API_KEY / EMAIL_VERIFIER from gitignored .env if present
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass
class Verdict:
    """Normalized verification result. `result` is the provider-neutral verdict our grading keys on."""
    email: str
    result: str            # 'ok' | 'catch_all' | 'unknown' | 'disposable' | 'invalid' | 'error'
    quality: str | None    # provider's own summary (e.g. good/risky/bad), if any
    raw: dict = field(default_factory=dict)


class Verifier(Protocol):
    name: str

    def verify(self, email: str, *, timeout: int = 15) -> Verdict: ...


# MillionVerifier v3 result strings we pass through; anything else collapses to 'unknown'/'error'.
_MV_RESULTS = {"ok", "catch_all", "unknown", "disposable", "invalid", "error"}


class MillionVerifier:
    """MillionVerifier single-email API (https://developer.millionverifier.com). One GET per address."""

    name = "millionverifier"
    ENDPOINT = "https://api.millionverifier.com/api/v3/"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("MILLIONVERIFIER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "MILLIONVERIFIER_API_KEY is not set. Add it to .env (get a free key at "
                "millionverifier.com -> API), or use --verifier mock for an offline dry run."
            )

    def verify(self, email: str, *, timeout: int = 15) -> Verdict:
        qs = urllib.parse.urlencode({"api": self.api_key, "email": email, "timeout": timeout})
        req = urllib.request.Request(self.ENDPOINT + "?" + qs,
                                     headers={"User-Agent": "polarity-fo-rag/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # network / decode / quota -> honest 'error', never a crash
            return Verdict(email, "error", None, {"exception": f"{type(e).__name__}: {e}"})
        result = str(data.get("result", "")).lower()
        if result not in _MV_RESULTS:
            result = "error" if data.get("error") else "unknown"
        return Verdict(email, result, data.get("quality"), data)


class MockVerifier:
    """Deterministic offline double. Encodes the grade paths without a key or network:
    a 'first.last' localpart -> ok; a domain containing 'catchall' -> catch_all; else invalid."""

    name = "mock"

    def verify(self, email: str, *, timeout: int = 15) -> Verdict:
        local, _, domain = email.partition("@")
        if "catchall" in domain:
            return Verdict(email, "catch_all", "risky", {"mock": True})
        if "." in local and not local.endswith("."):
            return Verdict(email, "ok", "good", {"mock": True})
        return Verdict(email, "invalid", "bad", {"mock": True})


def get_verifier(provider: str | None = None) -> Verifier:
    """Pick a verifier behind the seam. Default from EMAIL_VERIFIER, else millionverifier."""
    provider = (provider or os.getenv("EMAIL_VERIFIER", "millionverifier")).lower()
    if provider == "millionverifier":
        return MillionVerifier()
    if provider == "mock":
        return MockVerifier()
    raise ValueError(f"unknown verifier provider: {provider!r} (want 'millionverifier' or 'mock')")
