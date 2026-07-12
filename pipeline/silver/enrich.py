"""Firm-level enrichment that comes from outside the regulatory + website sources.

Some FO-MAX parity fields (corporate LinkedIn, and later contact location) cannot be derived from ADV
or the firm's own site -- they need an external lookup. That lookup is search-assisted (a web search
per firm, disambiguated against the firm's domain / founder / city, recording an honest blank rather
than a guess when nothing clearly matches), so it is NOT a deterministic transform like the rest of the
pipeline. To keep it reproducible and auditable anyway, the *results* are committed as a data artifact
(data/enrichment/corporate_linkedin.json) and this loader re-applies them to silver.firms. Re-running
the load is idempotent; re-running the *search* is a separate, human/agent-driven step.
"""
from __future__ import annotations

import json
import os

from pipeline import db

LINKEDIN_JSON = "data/enrichment/corporate_linkedin.json"


def load_corporate_linkedin(path: str = LINKEDIN_JSON) -> dict:
    """Apply committed corporate-LinkedIn results to silver.firms. Only accepts /company/ URLs."""
    if not os.path.exists(path):
        return {"error": f"not found: {path}"}
    records = json.load(open(path, encoding="utf-8"))
    loaded = skipped = 0
    with db.get_conn() as c, c.cursor() as cur:
        for r in records:
            url = (r.get("corporate_linkedin") or "").strip().rstrip("/")
            if url and "linkedin.com/company/" in url:
                cur.execute("update silver.firms set corporate_linkedin=%s, "
                            "corporate_linkedin_source=%s where crd=%s",
                            (url, r.get("matched_on") or "search", r["crd"]))
                loaded += cur.rowcount
            else:
                skipped += 1
        c.commit()
    return {"records": len(records), "loaded": loaded, "skipped_blank": skipped, "path": path}
