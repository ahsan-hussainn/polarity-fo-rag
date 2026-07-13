"""Query understanding for the RAG (ADR-0016): classify intent + extract typed filters.

Users ask three shapes of question and top-k retrieval only serves one of them well:
  - discovery  ("which FOs invest in real estate?")     -> hybrid top-k, filters as WHERE
  - lookup     ("who runs Wellspring?")                 -> name match first, small k
  - aggregate  ("how many FOs in Texas?")               -> SQL over gold.records, exact counts

Top-k retrieval CANNOT answer an aggregate honestly: the model sees 5 records and reports "there
are 2 in Texas" while gold holds 7 -- grounded in the retrieved set, wrong about the dataset. This
step routes those to SQL. Filters are extracted only for TYPED columns (state, AUM): sectors are
uncontrolled vocabulary, so sector matching stays semantic/lexical where fuzziness is honest, and
is keyword-based (and labelled as such) only in the aggregate path.

Fail-open: any classifier error degrades to plain discovery with no filters -- the behavior the
system had before this layer existed. A broken classifier must never take retrieval down with it.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

from pydantic import BaseModel

INTENT_MODEL = os.getenv("INTENT_MODEL", "gpt-4o-mini")


class QueryIntent(BaseModel):
    intent: Literal["discovery", "lookup", "aggregate"]
    firm_name: Optional[str]      # only if a specific firm is named (lookup)
    state: Optional[str]          # USPS 2-letter code, only if the user constrains location
    sector_term: Optional[str]    # short sector keyword, only if the user constrains sector
    min_aum_usd: Optional[int]    # only if the user constrains AUM
    max_aum_usd: Optional[int]


_SYSTEM = """Classify a question asked over a dataset of family office records and extract filters.

intent:
- "lookup": the question names one specific firm (who runs X, tell me about X, can I email X).
- "aggregate": the answer is a count, a total, a ranking, or "the largest/smallest/how many".
- "discovery": everything else -- finding/recommending firms by criteria.

Extraction rules (be conservative -- null unless the user EXPLICITLY constrains it):
- firm_name: the firm's name as written, only for lookup.
- state: USPS 2-letter code (California -> CA, Texas -> TX). null if no US-state constraint.
- sector_term: ONE short keyword/phrase for a sector/asset-class constraint (e.g. "real estate",
  "private equity"). null if none.
- min_aum_usd / max_aum_usd: integers in US dollars ("above $1B" -> min 1000000000). null if none.
Do not invent constraints the user did not state."""


def classify(query: str) -> QueryIntent:
    """Classify + extract, failing open to unfiltered discovery on any error."""
    try:
        from openai import OpenAI

        parse = getattr(OpenAI().chat.completions, "parse", None) or \
            OpenAI().beta.chat.completions.parse
        completion = parse(
            model=INTENT_MODEL, temperature=0,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": query}],
            response_format=QueryIntent,
        )
        return completion.choices[0].message.parsed
    except Exception:
        return QueryIntent(intent="discovery", firm_name=None, state=None,
                           sector_term=None, min_aum_usd=None, max_aum_usd=None)
