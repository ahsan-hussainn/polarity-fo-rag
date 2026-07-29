"""Stage 2: fetch each candidate firm's website into bronze (raw captures).

For every FO candidate that has a website, fetch the homepage plus a few high-signal internal pages
(team / about / strategy / contact), strip them to readable text, and land one bronze row per page.
That text is the raw material the Stage 3 extraction seam (ADR-0008) consumes; keeping it in bronze
as append-only captures preserves the provenance backbone (ADR-0006).

Deliberately lightweight and polite: stdlib urllib (matching adv.py), a descriptive User-Agent, a
per-request delay, a small page budget per firm, and honest failure recording (dead sites, timeouts,
and bad TLS are logged, not swallowed). Not yet doing robots.txt parsing -- noted as a known gap;
scope is a handful of public pages per firm with a courteous UA and rate limit.
"""
from __future__ import annotations

import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import lxml.html

from pipeline import config

MAX_TEXT = 20_000          # cap stored text per page (chars); enough for extraction, avoids giants
DEFAULT_TIMEOUT = 15       # seconds per request
DEFAULT_MAX_PAGES = 5      # homepage + up to 4 internal pages per firm

# Internal-link classification: (page_type, priority, keywords). Lower priority = fetched first.
_LINK_RULES = [
    ("team", 0, ("team", "people", "leadership", "our-team", "who-we-are", "partners",
                 "professionals", "principals", "management", "bios", "biograph", "staff")),
    ("about", 1, ("about", "about-us", "firm", "company", "overview", "story", "mission")),
    ("strategy", 2, ("strategy", "approach", "investment", "philosophy", "what-we-do",
                     "services", "focus")),
    ("contact", 3, ("contact", "connect", "get-in-touch")),
]
_PRIORITY = {t: p for t, p, _ in _LINK_RULES}

# ADV's WebAddr field is often a social/aggregator profile, not the firm's own site. Fetching those
# returns login walls / generic nav (which the link classifier would mistake for real team pages),
# so we skip them and record the firm as un-enrichable-by-website rather than ingest garbage.
_SKIP_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com",
    "crunchbase.com", "bloomberg.com", "wikipedia.org", "sec.gov", "adviserinfo.sec.gov",
    "google.com", "medium.com", "wechat.com", "weibo.com",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(website: str | None) -> str | None:
    """Turn an ADV website value ('example.com', 'www.x.com', 'http://x') into a fetchable URL."""
    if not website:
        return None
    w = website.strip()
    if not w or " " in w:
        return None
    if "://" not in w:
        w = "https://" + w
    p = urlparse(w)
    return w if p.scheme in ("http", "https") and p.netloc else None


def _reg_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _classify_link(href: str, anchor: str) -> str | None:
    hay = f"{href} {anchor}"
    for ptype, _, keywords in _LINK_RULES:
        if any(k in hay for k in keywords):
            return ptype
    return None


@dataclass
class FetchedPage:
    url: str
    page_type: str            # home | team | about | strategy | contact
    http_status: int | None
    title: str | None
    text: str
    text_len: int
    insecure: bool            # True if we had to fall back to unverified TLS
    error: str | None
    fetched_at: str


# Per-host politeness. The operating plan claimed "bounded worker pool with per-host politeness +
# exponential backoff" and the code had neither: the worker pool is per-FIRM, so two firms on the
# same host (or the same CDN) were fetched with no spacing at all, and a 429 was treated as a
# terminal error rather than an instruction to wait.
#
# The lock map is keyed by host, so unrelated hosts never block each other -- the pool stays as
# concurrent as before, it just cannot stampede one host.
_MIN_HOST_INTERVAL = float(os.getenv("FETCH_MIN_HOST_INTERVAL", "1.0"))
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = int(os.getenv("FETCH_MAX_ATTEMPTS", "3"))
_host_lock = threading.Lock()
_host_state: dict[str, tuple[threading.Lock, list]] = {}


def _host_gate(url: str):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    with _host_lock:
        if host not in _host_state:
            _host_state[host] = (threading.Lock(), [0.0])
        return _host_state[host]


def _wait_turn(url: str) -> None:
    """Space requests to the same host, without serialising different hosts."""
    lock, last = _host_gate(url)
    with lock:
        gap = time.monotonic() - last[0]
        if gap < _MIN_HOST_INTERVAL:
            time.sleep(_MIN_HOST_INTERVAL - gap)
        last[0] = time.monotonic()


def _retry_after(e: urllib.error.HTTPError, attempt: int) -> float:
    """Honour Retry-After when the server sends one; otherwise exponential backoff."""
    hdr = None
    try:
        hdr = e.headers.get("Retry-After") if e.headers else None
    except Exception:
        hdr = None
    if hdr:
        try:
            return min(float(int(hdr)), 30.0)
        except (TypeError, ValueError):
            pass
    return min(2.0 ** attempt, 30.0)


def _fetch_raw(url: str, timeout: int, ua: str) -> tuple[int | None, bytes, str, bool, str | None]:
    """(status, body, final_url, insecure, error). Never raises.

    Retries once without TLS verification, and retries rate-limit / transient-server responses with
    backoff (honouring Retry-After). A 429 answered by giving up is how a scraper turns a temporary
    'slow down' into permanent missing evidence.
    """
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,text/plain"}
    insecure = False
    last_err: str | None = None
    for attempt in range(_MAX_ATTEMPTS):
        for verify in (True, False):
            _wait_turn(url)
            try:
                ctx = None if verify else ssl._create_unverified_context()
                req = urllib.request.Request(url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                return resp.getcode(), resp.read(), resp.geturl(), insecure, None
            except urllib.error.HTTPError as e:
                last_err = f"http_{e.code}"
                if e.code in _RETRY_STATUS and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_retry_after(e, attempt))
                    break  # next attempt, from the verified path again
                return e.code, b"", url, insecure, last_err
            except urllib.error.URLError as e:
                if verify and isinstance(getattr(e, "reason", None), ssl.SSLError):
                    insecure = True
                    continue  # retry unverified, same attempt
                last_err = f"url_error: {e.reason}"
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(min(2.0 ** attempt, 30.0))
                    break
                return None, b"", url, insecure, last_err
            except Exception as e:  # socket timeouts, malformed responses, decode issues
                last_err = f"{type(e).__name__}: {e}"
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(min(2.0 ** attempt, 30.0))
                    break
                return None, b"", url, insecure, last_err
    return None, b"", url, insecure, last_err or "unreachable"


def _parse(body: bytes):
    """Return (doc, title, cleaned_text). doc is None if the body is empty/unparseable."""
    if not body:
        return None, None, ""
    try:
        doc = lxml.html.fromstring(body)
    except Exception:
        return None, None, ""
    for bad in doc.xpath("//script | //style | //noscript"):
        bad.getparent().remove(bad)
    title_el = doc.find(".//title")
    title = title_el.text.strip() if title_el is not None and title_el.text else None
    text = re.sub(r"\s+", " ", doc.text_content()).strip()
    return doc, title, text


def _page(url: str, page_type: str, timeout: int, ua: str):
    status, body, final, insecure, err = _fetch_raw(url, timeout, ua)
    doc, title, text = _parse(body)
    text = text[:MAX_TEXT]
    return FetchedPage(final, page_type, status, title, text, len(text), insecure, err, _utcnow()), doc


def _discover(doc, base_url: str, cap: int) -> list[tuple[str, str]]:
    """Same-domain internal links matching team/about/strategy/contact, priority-ordered, capped."""
    base_net = _reg_domain(base_url)
    base_key = base_url.split("#")[0].rstrip("/")
    seen: set[str] = set()
    found: list[tuple[str, str, int]] = []
    for a in doc.xpath("//a[@href]"):
        absu = urljoin(base_url, a.get("href", "")).split("#")[0]
        p = urlparse(absu)
        if p.scheme not in ("http", "https") or _reg_domain(absu) != base_net:
            continue
        key = absu.rstrip("/")
        if key == base_key or key in seen:
            continue
        ptype = _classify_link(a.get("href", "").lower(), (a.text_content() or "").lower())
        if ptype:
            seen.add(key)
            found.append((absu, ptype, _PRIORITY[ptype]))
    found.sort(key=lambda x: x[2])
    return [(u, t) for u, t, _ in found[:cap]]


def fetch_site(website: str, *, timeout: int = DEFAULT_TIMEOUT, ua: str = config.WEB_UA,
               max_pages: int = DEFAULT_MAX_PAGES) -> list[FetchedPage]:
    """Fetch a firm's homepage + a few high-signal internal pages. Returns one FetchedPage each."""
    home_url = _normalize(website)
    if not home_url:
        return [FetchedPage(website or "", "home", None, None, "", 0, False, "bad_url", _utcnow())]
    domain = _reg_domain(home_url)
    if domain in _SKIP_DOMAINS:
        return [FetchedPage(home_url, "home", None, None, "", 0, False,
                            f"skipped_non_site:{domain}", _utcnow())]
    home, doc = _page(home_url, "home", timeout, ua)
    pages = [home]
    if doc is not None and home.error is None:
        for url, ptype in _discover(doc, home.url, max_pages - 1):
            page, _ = _page(url, ptype, timeout, ua)
            pages.append(page)
    return pages


def _page_to_bronze_row(crd, firm_name, p: FetchedPage) -> dict:
    return {
        "source": "website",
        "source_url": p.url,
        "entity_key": crd,
        "fetched_at": p.fetched_at,
        "raw": {
            "crd": crd, "firm_name": firm_name, "page_url": p.url, "page_type": p.page_type,
            "http_status": p.http_status, "title": p.title, "text_len": p.text_len,
            "text": p.text, "insecure": p.insecure,
        },
    }


def _firms_with_websites(limit: int) -> list[tuple]:
    """Pull (crd, business_name, website) from bronze for firms that have a website, richest first."""
    from pipeline import db

    # Highest-confidence family offices first: firms whose NAME literally contains "family office",
    # then the rest of the strong tier (free-text matches), then medium, then weak client-mix. Within
    # a bucket, richest first. This targets the firms we actually want principals for -- not the
    # biggest AUM (which are institutional managers that merely mention "family office").
    sql = (
        "select raw->>'crd', raw->>'business_name', raw->>'website' "
        "from bronze.captures "
        "where source = 'sec_form_adv' and coalesce(raw->>'website', '') <> '' "
        "order by case "
        "           when raw->>'reasons' like '%%name_contains_family_office%%' then 0 "
        "           when raw->>'tier' = 'strong' then 1 "
        "           when raw->>'tier' = 'medium' then 2 else 3 end, "
        "         (raw->>'raum_total')::numeric desc nulls last "
        "limit %s"
    )
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql, (limit,))
        return cur.fetchall()


def run(limit: int, *, max_pages: int = DEFAULT_MAX_PAGES, write: bool = False,
        delay: float = 1.0, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Fetch websites for `limit` firms (richest first). Writes to bronze only if write=True."""
    firms = _firms_with_websites(limit)
    total_pages_with_text = 0
    firms_with_content = 0
    pages_fetched = 0
    stored = 0
    failures: list[dict] = []
    if write:
        from pipeline import db

    for i, (crd, name, website) in enumerate(firms, 1):
        pages = fetch_site(website, timeout=timeout, max_pages=max_pages)
        pages_fetched += len(pages)
        good = [p for p in pages if p.error is None and p.text_len > 0]
        firm_rows = [_page_to_bronze_row(crd, name, p) for p in good]
        total_pages_with_text += len(firm_rows)
        # Write per firm so an interruption leaves partial progress and a re-run resumes
        # (bronze dedupe on (source, content_hash) makes re-running idempotent).
        if write and firm_rows:
            stored += db.insert_captures(firm_rows)
        if good:
            firms_with_content += 1
        else:
            failures.append({"crd": crd, "name": name, "website": website,
                             "error": pages[0].error or "no_text"})
        got = ", ".join(f"{p.page_type}{'*' if p.insecure else ''}" for p in good) or "-"
        print(f"  [{i}/{len(firms)}] {(name or '')[:38]:38} {website[:32]:32} -> {len(good)}p ({got})")
        if delay and i < len(firms):
            time.sleep(delay)

    return {
        "firms_attempted": len(firms),
        "firms_with_content": firms_with_content,
        "pages_fetched": pages_fetched,
        "pages_with_text": total_pages_with_text,
        "pages_stored_new": stored if write else None,
        "written": write,
        "failures": failures,
    }
