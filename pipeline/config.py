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
# SEC-registered firm feed (RIAs + ERAs) and the state-registered adviser feed (same XML shape,
# advisers typically <$100M AUM -- the small genuine MFOs the SEC feed structurally excludes;
# census 2026-07-27 measured ~116 family-signal candidates there).
ADV_FEED_PREFIX = "IA_FIRM_SEC_Feed_"
ADV_STATE_FEED_PREFIX = "IA_FIRM_STATE_Feed_"

# --- Website enrichment fetch (Stage 2) ---
# Descriptive UA so a site operator can see who we are; we fetch only a few public pages per firm.
WEB_UA = "PolarityIQ Research (ahsannhu17@gmail.com)"

# --- Local working paths (all under gitignored data/raw) ---
DATA_RAW = "data/raw"

# --- Family-office classification (ADR-0004) ---
# Strong: the phrase "family office(s)" (and single/multi variants) in the firm name. The optional
# plural matters: the 2026-07-27 source census measured 11 SEC-feed firms named "... Family
# Offices" (Colony, WE, Cherry Creek, ...) that the singular-only pattern silently dropped --
# near-certain genuine FOs lost to one character.
STRONG_NAME_PATTERNS = [
    re.compile(r"\bfamily\s+offices?\b", re.I),
    re.compile(r"\bmulti[\s-]?family\s+offices?\b", re.I),
    re.compile(r"\bsingle[\s-]?family\s+offices?\b", re.I),
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
