"""13F discovery: the source class that reaches the family offices Form ADV structurally cannot.

Both ADV channels (SEC feed, state feed) are ONE registry wearing two hats, and its blind spot is
not incidental -- it is definitional. A true single-family office manages one family's own money,
which is exactly the condition for exemption from adviser registration, so **the purest family
offices are the ones Form ADV can never see.** Measured on our own data: zero single-family offices
across 341 ADV-sourced candidates.

Section 13(f) has no such exemption. Any institutional manager with over $100M in 13(f) securities
files a 13F-HR, family office or not. That makes the 13F filer list a structurally different lens
on the same market -- and it works: Duquesne Family Office (Stanley Druckenmiller's) files 13F and
appears in no ADV feed we hold.

What this source can and cannot establish, stated because ADR-0004 requires each source be used for
what it actually supports:

  CAN: that a legal entity exists, its exact registered name, its CIK, and that it manages
       institutional-scale securities. That is enough to SURFACE a candidate.
  CANNOT: what the firm is (the filing carries no client mix, no self-description, no AUM breakdown
       and no website), who runs it, or whether "family office" in the name is accurate. Every
       13F candidate therefore enters the queue with no website and must earn its domain through
       the ADR-0032 resolver before the gate can read anything the firm says about itself.

Consequence for release: a 13F candidate has no ADV client mix, so ADR-0034's client-mix route is
unavailable to it by construction. It can only auto-release through the concordant-published-
evidence route, which is the conservative outcome and the correct one -- we know less about these
firms, so more of them stay in human review.
"""
from __future__ import annotations

import io
import re
import urllib.request

from pipeline import config

# The SEC asks automated clients to identify themselves; an anonymous scraper is the kind of
# "source blocks the scraper" failure we would rather not induce on purpose.
UA = "PolarityIQ FO Research (ahsanhussain17999@gmail.com)"
FORM_INDEX = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{qtr}/form.idx"
_ROW = re.compile(r"^13F-HR(?:/A)?\s+(.{1,62}?)\s{2,}(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)")


def fetch_form_index(year: int, qtr: int, *, timeout: int = 90) -> str:
    req = urllib.request.Request(FORM_INDEX.format(year=year, qtr=qtr), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return io.TextIOWrapper(r, encoding="utf-8", errors="replace").read()


def parse_filers(index_text: str) -> dict[str, dict]:
    """CIK -> {name, cik, latest_filing_date, filing_path}. One entry per filer; amendments and
    repeat filings collapse to the most recent, so a manager filing quarterly is one candidate."""
    out: dict[str, dict] = {}
    for line in index_text.splitlines():
        if not line.startswith("13F-HR"):
            continue
        m = _ROW.match(line)
        if not m:
            continue
        name, cik, filed, path = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
        prev = out.get(cik)
        if prev is None or filed > prev["latest_filing_date"]:
            out[cik] = {"cik": cik, "business_name": name, "latest_filing_date": filed,
                        "filing_path": path}
    return out


def classify(filers: dict[str, dict]) -> list[dict]:
    """Tier by name signal only -- the filing carries nothing else to judge on.

    Deliberately NOT the ADV tier vocabulary's full range: there is no free text and no client mix
    here, so 'strong' means the registered name states family office and 'medium' means it carries
    family-capital naming. Anything weaker is not a candidate, because with no website and no
    registry description there would be nothing for the gate to read.
    """
    out = []
    for f in filers.values():
        name = f["business_name"]
        if any(p.search(name) for p in config.STRONG_NAME_PATTERNS):
            tier, reason = "strong", "13F filer name states family office"
        elif any(p.search(name) for p in config.MEDIUM_NAME_PATTERNS):
            tier, reason = "medium", "13F filer name carries family-capital naming"
        else:
            continue
        out.append({**f, "tier": tier, "reasons": [reason], "source": "13f",
                    "website": None,  # 13F carries no website: every candidate starts stranded
                    "filing_url": f"https://www.sec.gov/Archives/{f['filing_path']}"})
    out.sort(key=lambda c: (c["tier"] != "strong", c["business_name"]))
    return out


_HDR_BLOCK = re.compile(r"BUSINESS ADDRESS:(.*?)(?:MAIL ADDRESS:|</SEC-HEADER>)", re.S)
_HDR_FIELD = {"street1": r"STREET 1:\s*(.+)", "city": r"CITY:\s*(.+)", "state": r"STATE:\s*(.+)",
              "zip": r"ZIP:\s*(.+)", "phone": r"BUSINESS PHONE:\s*(.+)"}
_EIN = re.compile(r"EIN:\s*(\d+)")


def fetch_filer_profile(filing_path: str, *, timeout: int = 45) -> dict:
    """Pull the filer's business address and phone from a 13F submission header.

    This is what makes the channel usable rather than decorative. Measured first: with a name
    alone, the ADR-0032 resolver proved 0 of 6 candidate domains, because its proof standard
    requires an INDEPENDENT corroborator for any partial-stem domain and a 13F name supplies none.
    The submission header carries the filer's street address and phone -- the same corroborator
    class the ADV path already uses -- so fetching it turns an unprovable candidate into a
    provable one without weakening the proof standard, which is the part that must not move.
    """
    url = f"https://www.sec.gov/Archives/{filing_path}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        # The header sits at the top; the holdings table can run to megabytes and is not needed.
        head = r.read(20_000).decode("utf-8", errors="replace")
    out: dict = {}
    m = _HDR_BLOCK.search(head)
    if m:
        block = m.group(1)
        for key, pat in _HDR_FIELD.items():
            f = re.search(pat, block)
            if f:
                out[key] = f.group(1).strip()
    e = _EIN.search(head)
    if e:
        out["ein"] = e.group(1)
    return out


def enrich_profiles(candidates: list[dict], *, delay: float = 0.4) -> list[dict]:
    """Attach filer profiles in place. Sequential and paced: the SEC publishes a fair-access rate
    limit, and this runs over tens of candidates, not thousands -- politeness costs nothing here
    and a 429 from the SEC would be a self-inflicted failure."""
    import time

    for c in candidates:
        try:
            c["profile"] = fetch_filer_profile(c["filing_path"])
        except Exception as exc:  # a header we cannot read is a candidate with no corroborator
            c["profile"] = {}
            c["profile_error"] = repr(exc)
        time.sleep(delay)
    return candidates


def discover(year: int, qtr: int) -> dict:
    """Fetch one quarter's form index and return the family-office-signalling 13F filers."""
    text = fetch_form_index(year, qtr)
    filers = parse_filers(text)
    candidates = classify(filers)
    return {"year": year, "quarter": qtr, "index_bytes": len(text),
            "filers_13f": len(filers), "candidates": candidates,
            "by_tier": {t: sum(1 for c in candidates if c["tier"] == t)
                        for t in ("strong", "medium")}}
