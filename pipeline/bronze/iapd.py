"""Live IAPD snapshot: the external fact the ADV staleness detector was missing.

The detector this feeds was broken in a way worth recording, because the shape of the bug is
instructive. It read `gold.records.data_asof` -- our own held value -- observed it, and compared
the next run's observation to the previous one. Nothing in the cycle re-ingests Form ADV, so the
held value could never move, and the comparison was the held value against itself: 772 observations
across 24 runs produced exactly zero trust events. A detector that cannot fire is worse than no
detector, because it reports coverage it does not have.

The fix is not a better comparison, it is a real second party to compare against. This module
fetches the adviser's CURRENT registration record from IAPD -- the same source that backs
adviserinfo.sec.gov -- so the cycle compares what the regulator says today against what we hold.
Three facts are worth watching, and all three are evidence-based rather than clock-based:

  advFilingDate  -- a newer filing means our ADV-derived cells may be superseded.
  iaScope        -- ACTIVE -> anything else means the firm is no longer a registered adviser, which
                    invalidates the basis of every ADV-derived cell we hold. This is the strongest
                    trust signal available on this source and the filing date alone would miss it.
  firmName       -- a rename is an identity event; the held record may now describe a firm that no
                    longer presents under that name.
"""
from __future__ import annotations

import json
import urllib.request

UA = "Mozilla/5.0 (compatible; PolarityIQ FO Research; ahsanhussain17999@gmail.com)"
FIRM_URL = "https://api.adviserinfo.sec.gov/search/firm/{crd}"


def _iso(us_date: str | None) -> str | None:
    """IAPD reports MM/DD/YYYY; the rest of the system speaks ISO."""
    if not us_date or "/" not in us_date:
        return None
    try:
        m, d, y = us_date.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return None


def fetch_firm(crd: str, *, timeout: int = 20) -> dict:
    """Current registration snapshot for one CRD. Raises on transport failure -- the caller
    ledgers it as a fetch error rather than silently treating 'unreachable' as 'unchanged'."""
    req = urllib.request.Request(FIRM_URL.format(crd=crd), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read().decode("utf-8", errors="replace"))

    hits = (payload.get("hits") or {}).get("hits") or []
    if not hits:
        # A CRD that no longer resolves at IAPD is itself a finding, not an error.
        return {"crd": crd, "found": False}
    content = hits[0].get("_source", {}).get("iacontent")
    inner = json.loads(content) if isinstance(content, str) else (content or {})
    basic = inner.get("basicInformation") or {}
    return {
        "crd": crd,
        "found": True,
        "firm_name": basic.get("firmName"),
        "ia_scope": basic.get("iaScope"),
        "adv_filing_date": _iso(basic.get("advFilingDate")),
        "sec_number": basic.get("iaSECNumber"),
    }
