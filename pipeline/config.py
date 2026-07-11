"""Static config: source endpoints, request rules, and family-office match rules.

Kept in one place so the discovery heuristics are auditable and easy to tune. The SEC requires a
declared User-Agent (verified: generic UA -> HTTP 403) and asks for <=10 req/s.
"""
import re

# --- SEC access ---
SEC_UA = "PolarityIQ Research ahsannhu17@gmail.com"
ADV_MANIFEST_URL = (
    "https://reports.adviserinfo.sec.gov/reports/CompilationReports/"
    "CompilationReports.manifest.json"
)
ADV_FEED_BASE = "https://reports.adviserinfo.sec.gov/reports/CompilationReports/"
# We want the SEC-registered firm feed (RIAs + ERAs), not the state or individuals feeds.
ADV_FEED_PREFIX = "IA_FIRM_SEC_Feed_"

# --- Local working paths (all under gitignored data/raw) ---
DATA_RAW = "data/raw"

# --- Family-office classification (ADR-0004) ---
# Strong: the phrase "family office" (and single/multi variants) in the firm name.
STRONG_NAME_PATTERNS = [
    re.compile(r"\bfamily\s+office\b", re.I),
    re.compile(r"\bmulti[\s-]?family\s+office\b", re.I),
    re.compile(r"\bsingle[\s-]?family\s+office\b", re.I),
]
# Medium: family-linked capital/wealth naming that is often (not always) a family office.
MEDIUM_NAME_PATTERNS = [
    re.compile(r"\bfamily\s+(capital|wealth|partners|investments?|holdings|advisor|advisors|"
               r"advisers|group|trust|management|enterprises?)\b", re.I),
    re.compile(r"\bMFO\b"),  # multi-family office abbreviation
]
# Free-text marker anywhere in the filing's "Other" fields (e.g. Item 5.G other services).
FREE_TEXT_MARKER = re.compile(r"family\s+office", re.I)

# Client-mix heuristic (weak, supplementary tier only): HNW-dominant AUM with very few clients
# looks like a (multi-)family office. Reported separately; never a strong signal on its own.
CLIENT_MIX_HNW_RAUM_SHARE = 0.75
CLIENT_MIX_MAX_CLIENTS = 15
