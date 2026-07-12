"""The extraction seam (ADR-0008): one interface, swappable implementations.

Stage 3 (bronze -> silver) turns a family office's unstructured website text into structured
fields. The *pipeline* calls `get_extractor().extract(text)` and never learns which model produced
the answer; everything provider-specific lives behind the `Extractor` protocol below. Swapping
OpenAI -> Claude -> Gemini is a new class here, not a change upstream.

What the LLM does and does NOT do (ADR-0003/0005 principles, enforced by the system prompt):
  - Extracts only what the text states. Missing field -> null / empty list, never a guess. An honest
    blank beats a fabricated cell.
  - Judges is_principal (investment/decision authority) vs staff, with a short reason, because that
    judgment is where we beat FO-MAX (their Walton contact was an Accounting Manager).
  - It does NOT verify emails (SMTP probe) or assign the final quality grade (validation layer).
Provenance (`source_url`) is set by US, not the model, so it can't be hallucinated.
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import Protocol

from pydantic import BaseModel

try:  # load OPENAI_API_KEY / EXTRACT_* from gitignored .env if present
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


# --- The provider-neutral output shape (mirrors FO-MAX, verifiability-first) -----------------

class TeamMember(BaseModel):
    name: str
    title: str | None
    is_principal: bool
    principal_reason: str | None  # why classified this way -- auditable, not a black box


class Extraction(BaseModel):
    thesis: str | None
    description: str | None
    sectors: list[str]
    founded_year: int | None
    team: list[TeamMember]


@dataclass
class ExtractionResult:
    """The validated extraction plus OUR bookkeeping (provenance, model, cost)."""
    source_url: str | None
    provider: str
    model: str
    extraction: Extraction
    usage: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        d["extraction"] = self.extraction.model_dump()
        return d


SYSTEM_PROMPT = """You extract structured facts from a family office's website text.

Rules:
- Extract ONLY what the text explicitly states. If a field is not present, return null (or an empty
  list). Never guess, infer, or fabricate. An honest blank is required; a made-up value is worse.
- sectors: a clean, de-duplicated list of the asset classes / industries the firm invests in.
- founded_year: a 4-digit year only if stated; else null.
- team: every named person with their stated title.
- is_principal: true ONLY for people with investment decision-making authority or firm ownership --
  founders, principals, owners, partners, managing partners/directors, CIO, CEO, president, chairman.
  false for administrative, operational, finance-operations (controller, accountant, bookkeeper),
  communications, IT, or support roles. Give a short principal_reason for each person.
"""


# --- The seam: any implementation with this shape is a drop-in extractor ----------------------

class Extractor(Protocol):
    name: str

    def extract(self, text: str, *, source_url: str | None = None) -> ExtractionResult: ...


class OpenAIExtractor:
    """Behind the seam: OpenAI gpt-4o-mini with Structured Outputs (ADR-0008)."""

    def __init__(self, model: str | None = None):
        from openai import OpenAI  # lazy: mock path works without openai installed

        self.model = model or os.getenv("EXTRACT_MODEL", "gpt-4o-mini")
        self.name = f"openai:{self.model}"
        self._client = OpenAI()  # reads OPENAI_API_KEY from env/.env

    def extract(self, text: str, *, source_url: str | None = None) -> ExtractionResult:
        # SDK version tolerance: prefer the GA parse helper, fall back to the beta one.
        parse = getattr(self._client.chat.completions, "parse", None) or \
            self._client.beta.chat.completions.parse
        completion = parse(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=Extraction,
        )
        parsed = completion.choices[0].message.parsed
        usage = completion.usage.model_dump() if completion.usage else {}
        return ExtractionResult(source_url, "openai", self.model, parsed, usage)


# Deterministic, offline, zero-cost double -- proves the seam plumbing without an API key.
_TITLES = (
    "Managing Partner", "Managing Director", "Chief Investment Officer", "CIO", "Founder",
    "Co-Founder", "President", "Chairman", "Partner", "Principal", "CEO",
    "Controller", "Office Manager", "Accountant", "Bookkeeper", "Analyst", "Manager",
)
_PRINCIPAL = {
    "managing partner", "managing director", "chief investment officer", "cio", "founder",
    "co-founder", "president", "chairman", "partner", "principal", "ceo",
}
_KNOWN_SECTORS = (
    "real estate", "healthcare", "technology", "private equity", "venture", "energy",
    "consumer", "financial", "industrials", "biotech", "infrastructure", "hospitality",
)
_TITLE_RE = re.compile(r"\b(" + "|".join(_TITLES) + r")\s+([A-Z][a-z]+ [A-Z][a-z]+)")


class MockExtractor:
    """No network, deterministic. For tests and demoing the seam without spending tokens."""

    name = "mock"

    def extract(self, text: str, *, source_url: str | None = None) -> ExtractionResult:
        low = text.lower()
        year = re.search(r"\b(19|20)\d{2}\b", text)
        team = [
            TeamMember(
                name=name, title=title, is_principal=title.lower() in _PRINCIPAL,
                principal_reason=("decision-making/ownership title" if title.lower() in _PRINCIPAL
                                  else "non-investment / support role"),
            )
            for title, name in _TITLE_RE.findall(text)
        ]
        extraction = Extraction(
            thesis=None,
            description=None,
            sectors=[s for s in _KNOWN_SECTORS if s in low],
            founded_year=int(year.group(0)) if year else None,
            team=team,
        )
        return ExtractionResult(source_url, "mock", "heuristic", extraction, usage={})


def get_extractor(provider: str | None = None) -> Extractor:
    """Pick an implementation behind the seam. Default from EXTRACT_PROVIDER, else openai."""
    provider = (provider or os.getenv("EXTRACT_PROVIDER", "openai")).lower()
    if provider == "openai":
        return OpenAIExtractor()
    if provider == "mock":
        return MockExtractor()
    raise ValueError(f"unknown extractor provider: {provider!r} (want 'openai' or 'mock')")


# A self-contained sample so `extract-test` runs with no inputs. Note the Walton-style trap:
# a Controller and an Office Manager that a naive extractor would wrongly flag as the contact.
SAMPLE_TEXT = (
    "Founded in 2004, Sequoia Heritage manages the assets of the Thompson family across three "
    "generations. We take a long-term, concentrated approach to direct investments in healthcare "
    "technology and sustainable real estate, alongside a curated portfolio of external managers. "
    "The firm is led by Managing Partner Sarah Thompson, who oversees all investment decisions. "
    "Our operations are supported by Controller James Rees and Office Manager Diane Kohl."
)
