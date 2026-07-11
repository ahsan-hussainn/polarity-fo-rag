"""Stage 1 (part): discover family-office candidates from the SEC Form ADV firm feed.

Flow: read the manifest -> download the current SEC firm feed (gzipped XML) -> stream-parse each
<Firm> -> extract firm-level fields -> classify as a family-office candidate by name / free-text /
client-mix. Firm data only; principal names are NOT in this feed (ADR-0004) and come later.

The feed is ~81 MB uncompressed / ~23.5k firms, so we stream with lxml.iterparse and clear as we go.
"""
from __future__ import annotations
import gzip
import json
import os
import time
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Iterator, Optional

from lxml import etree

from pipeline import config


# --------------------------------------------------------------------------- download

def current_feed_filename(ua: str = config.SEC_UA) -> str:
    """Read the SEC manifest and return the current SEC-registered firm feed filename."""
    req = urllib.request.Request(config.ADV_MANIFEST_URL, headers={"User-Agent": ua})
    manifest = json.loads(urllib.request.urlopen(req, timeout=60).read())
    for f in manifest.get("files", []):
        if f.get("name", "").startswith(config.ADV_FEED_PREFIX):
            return f["name"]
    raise RuntimeError("No SEC firm feed found in ADV manifest")


def download_feed(ua: str = config.SEC_UA, cache_dir: str = config.DATA_RAW) -> str:
    """Download (and cache) the current firm feed, returning the path to the uncompressed XML."""
    os.makedirs(cache_dir, exist_ok=True)
    fn = current_feed_filename(ua)
    xml_path = os.path.join(cache_dir, fn.replace(".xml.gz", ".xml"))
    if os.path.exists(xml_path) and os.path.getsize(xml_path) > 1_000_000:
        return xml_path  # already cached
    req = urllib.request.Request(config.ADV_FEED_BASE + fn, headers={"User-Agent": ua})
    raw = urllib.request.urlopen(req, timeout=180).read()
    xml_bytes = gzip.decompress(raw)
    with open(xml_path, "wb") as fh:
        fh.write(xml_bytes)
    return xml_path


# --------------------------------------------------------------------------- parse

@dataclass
class FirmRecord:
    crd: Optional[str]
    sec_number: Optional[str]
    business_name: Optional[str]
    legal_name: Optional[str]
    org_form: Optional[str]
    website: Optional[str]
    street1: Optional[str]
    street2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
    phone: Optional[str]
    total_employees: Optional[int]
    raum_total: Optional[int]            # Item 5.F total regulatory AUM (USD)
    hnw_clients: Optional[int]           # Item 5.D HNW individual client count
    hnw_raum: Optional[int]              # Item 5.D HNW individual RAUM
    nonhnw_clients: Optional[int]        # Item 5.D non-HNW individual client count
    registration_type: Optional[str]
    latest_filing_date: Optional[str]
    other_text: str = ""                 # concatenated "Other" free-text, for marker scanning

    # provenance (bronze discipline)
    source: str = "sec_form_adv"
    source_url: str = ""


def _int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def iter_firms(xml_path: str) -> Iterator[FirmRecord]:
    """Stream every <Firm> in the feed as a FirmRecord, clearing memory as we go."""
    context = etree.iterparse(xml_path, events=("end",), tag="Firm", recover=True)
    for _, firm in context:
        info = firm.find("Info")
        addr = firm.find("MainAddr")
        rgstn = firm.find("Rgstn")
        filing = firm.find("Filing")
        p1a = firm.find("./FormInfo/Part1A")

        def a(el, key):
            return el.get(key) if el is not None else None

        web_el = firm.find(".//Item1/WebAddrs/WebAddr")
        website = web_el.text.strip() if web_el is not None and web_el.text else None

        item5a = p1a.find("Item5A") if p1a is not None else None
        item5d = p1a.find("Item5D") if p1a is not None else None
        item5f = p1a.find("Item5F") if p1a is not None else None
        item3a = p1a.find("Item3A") if p1a is not None else None

        # scan every attribute value in the subtree for "Oth" free-text fields
        other_bits = []
        for el in firm.iter():
            for k, v in el.attrib.items():
                if k.endswith("Oth") and v:
                    other_bits.append(v)
        other_text = " | ".join(other_bits)

        crd = a(info, "FirmCrdNb")
        rec = FirmRecord(
            crd=crd,
            sec_number=a(info, "SECNb"),
            business_name=a(info, "BusNm"),
            legal_name=a(info, "LegalNm"),
            org_form=a(item3a, "OrgFormNm"),
            website=website,
            street1=a(addr, "Strt1"),
            street2=a(addr, "Strt2"),
            city=a(addr, "City"),
            state=a(addr, "State"),
            country=a(addr, "Cntry"),
            postal_code=a(addr, "PostlCd"),
            phone=a(addr, "PhNb"),
            total_employees=_int(a(item5a, "TtlEmp")),
            raum_total=_int(a(item5f, "Q5F2C")),
            hnw_clients=_int(a(item5d, "Q5DB1")),
            hnw_raum=_int(a(item5d, "Q5DB3")),
            nonhnw_clients=_int(a(item5d, "Q5DA1")),
            registration_type=a(rgstn, "FirmType"),
            latest_filing_date=a(filing, "Dt"),
            other_text=other_text,
            source_url=(f"https://reports.adviserinfo.sec.gov/reports/ADV/{crd}/PDF/{crd}.pdf"
                        if crd else ""),
        )
        yield rec

        # free memory: clear this element and its now-processed previous siblings
        firm.clear()
        while firm.getprevious() is not None:
            del firm.getparent()[0]


# --------------------------------------------------------------------------- classify

@dataclass
class Candidate:
    firm: dict
    tier: str            # "strong" | "medium" | "client_mix"
    reasons: list = field(default_factory=list)


def classify(rec: FirmRecord) -> Optional[Candidate]:
    """Return a Candidate with a tier + reasons, or None if not a family-office candidate."""
    name = f"{rec.business_name or ''} {rec.legal_name or ''}"
    reasons = []

    if any(p.search(name) for p in config.STRONG_NAME_PATTERNS):
        reasons.append("name_contains_family_office")
        return Candidate(asdict(rec), "strong", reasons)

    if config.FREE_TEXT_MARKER.search(rec.other_text or ""):
        reasons.append("free_text_family_office")
        return Candidate(asdict(rec), "strong", reasons)

    if any(p.search(name) for p in config.MEDIUM_NAME_PATTERNS):
        reasons.append("name_family_capital_wealth_etc")
        return Candidate(asdict(rec), "medium", reasons)

    # weak client-mix heuristic, reported as its own tier and never merged with strong/medium
    total_clients = (rec.hnw_clients or 0) + (rec.nonhnw_clients or 0)
    if rec.raum_total and rec.hnw_raum and total_clients:
        share = rec.hnw_raum / rec.raum_total if rec.raum_total else 0
        if share >= config.CLIENT_MIX_HNW_RAUM_SHARE and total_clients <= config.CLIENT_MIX_MAX_CLIENTS:
            reasons.append(f"hnw_dominant(share={share:.2f},clients={total_clients})")
            return Candidate(asdict(rec), "client_mix", reasons)

    return None


def discover(xml_path: Optional[str] = None) -> dict:
    """Run discovery over the feed. Returns a summary dict and the list of candidates."""
    if xml_path is None:
        xml_path = download_feed()
    t0 = time.time()
    total = 0
    candidates: list[Candidate] = []
    for rec in iter_firms(xml_path):
        total += 1
        c = classify(rec)
        if c:
            candidates.append(c)
    by_tier: dict[str, int] = {}
    for c in candidates:
        by_tier[c.tier] = by_tier.get(c.tier, 0) + 1
    return {
        "feed": os.path.basename(xml_path),
        "firms_scanned": total,
        "candidates_total": len(candidates),
        "by_tier": by_tier,
        "elapsed_s": round(time.time() - t0, 1),
        "candidates": candidates,
    }
