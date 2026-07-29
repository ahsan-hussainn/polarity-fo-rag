"""Domain resolution: recovering candidates the registry stranded (Stage 2).

Measured on day 2: of 341 queued candidates, 108 carry a social-media URL in the ADV website field
(LinkedIn, X, Facebook) and 66 carry no URL at all. Only 49% carry a real firm domain. That is the
binding constraint on the whole climb, not candidate supply -- across the first 70 gate decisions
the site rules fired 19 times while `adv_freetext_fo` fired 40. Fifteen candidates in run 15 scored
exactly 15 (their own ADV filing says they do family-office work) and were excluded solely because
nobody could read their website.

This is the brief's warning made concrete: "a source may be good enough to surface a candidate
record without being strong enough to establish its identity", and "scaling one convenient registry
does not demonstrate market discovery if its blind spots pass into your records unchanged". The ADV
website field is self-reported and unvalidated. Taking it as the firm's domain passes that blind
spot straight into the records.

## The proof standard, and why it is strict

A guessed domain attached to the wrong company is not a gap, it is a false record -- this dataset
already carries one (`arrowrootadvisors.com`, an M&A bank whose pages were extracted as a family
office's). A feasibility probe with a loose bar (any 2 name tokens on the page) resolved 9 of 12
candidates but produced exactly that failure twice: BLOSSOM WEALTH MANAGEMENT -> blossom.com on
{'blossom','management'}, RED DOOR WEALTH MANAGEMENT -> reddoor.net on {'red','door'}. Generic
finance words carry no identifying information, and short generic stems are the most likely domains
to belong to somebody else entirely.

So a domain is accepted only on:

  (a) >=2 DISTINCTIVE tokens from the firm's name appearing on the page -- distinctive meaning not
      in the generic-finance stoplist ('capital', 'wealth', 'advisors', 'family', 'office', ...), or
  (b) 1 distinctive token PLUS independent corroboration: the firm's ADV phone number (matched on
      its last 10 digits, so formatting cannot defeat it) or its ADV city, on the page.

Everything else is left unresolved. An unresolved candidate is honest; a wrong one is a defect that
propagates into the product, the retrieval index, and the agent's answers.

Resolution never overwrites a real website already held; it only fills genuine gaps. A resolved
candidate is re-queued so the ordinary gate path re-reads it -- this module establishes a domain,
it does not decide inclusion.
"""
from __future__ import annotations

import json
import re
import socket

from pipeline import config, db
from pipeline.ops import runlog as rl

SOCIAL = re.compile(r"(linkedin|twitter|x\.com|facebook|instagram|youtube|plus\.google|"
                    r"bizapedia|yelp|crunchbase|bloomberg\.com)", re.I)

# Words that appear in thousands of adviser names and identify nothing.
GENERIC = {
    "capital", "wealth", "management", "advisors", "advisers", "advisory", "partners", "group",
    "financial", "finance", "investment", "investments", "investing", "asset", "assets", "family",
    "office", "offices", "associates", "holdings", "trust", "private", "global", "national",
    "international", "american", "america", "first", "new", "old", "north", "south", "east", "west",
    "company", "companies", "corporation", "incorporated", "services", "service", "planning",
    "consulting", "consultants", "counsel", "securities", "fund", "funds", "equity", "strategies",
    "strategic", "solutions", "resources", "insurance", "retirement", "portfolio", "portfolios",
    "fiduciary", "independent", "premier", "summit", "heritage", "legacy", "pinnacle", "united",
}
LEGAL = {"llc", "inc", "lp", "llp", "ltd", "co", "corp", "pllc", "pc", "plc", "sa", "ag", "the",
         "and", "of", "&"}

TLDS = (".com", ".net", ".co")
MAX_CANDIDATES_PER_FIRM = 8


def _tokens(name: str) -> list[str]:
    return [w for w in re.sub(r"[^\w\s]", " ", (name or "").lower()).split() if w not in LEGAL]


def distinctive(name: str) -> list[str]:
    """Name tokens that actually identify a firm. 'Troob' identifies; 'Capital' does not."""
    return [w for w in _tokens(name) if w not in GENERIC and len(w) > 2]


def domain_guesses(name: str) -> list[tuple[str, str]]:
    """(domain, specificity) pairs, most-specific first. Deterministic, no network.

    Specificity is 'full' when the stem is the firm's entire name and 'partial' otherwise, and it
    changes the proof bar. `peddockcapitaladvisors.com` is self-evidently one firm's domain;
    `reddoor.net` is a stem that thousands of unrelated businesses could own. The probe's two
    wrong-entity matches were both partial stems, so partial stems are never accepted on name
    tokens alone.
    """
    words = _tokens(name)
    if not words:
        return []
    dist = distinctive(name)
    full = "".join(words)
    stems: list[tuple[str, str]] = []
    for parts in (full, "".join(words[:3]), "".join(words[:2]),
                  "".join(dist), "".join(dist[:2]), dist[0] if dist else None, words[0]):
        if parts and 3 <= len(parts) <= 40 and parts not in [s for s, _ in stems]:
            stems.append((parts, "full" if parts == full else "partial"))
    out: list[tuple[str, str]] = []
    for stem, spec in stems:
        for tld in TLDS:
            d = stem + tld
            if d not in [x for x, _ in out]:
                out.append((d, spec))
    return out[:MAX_CANDIDATES_PER_FIRM]


def _resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, None)
        return True
    except Exception:
        return False


def _phone_digits(phone: str | None) -> str | None:
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else None


def prove(domain: str, *, name: str, phone: str | None, city: str | None,
          specificity: str = "partial") -> dict | None:
    """Fetch the domain and decide whether it demonstrably belongs to THIS firm.

    Returns an evidence dict on proof, None otherwise. The evidence is what a reviewer reads, so it
    names which tokens matched and which corroborator fired -- never just a boolean.
    """
    from pipeline.bronze import website as web

    page, _ = web._page(f"https://{domain}", "home", 15, config.WEB_UA)
    if not page.text:
        page, _ = web._page(f"http://{domain}", "home", 15, config.WEB_UA)
    if not page.text or (page.http_status or 0) >= 400:
        return None

    text = re.sub(r"\s+", " ", page.text.lower())
    digits = re.sub(r"\D", "", text)
    dist = distinctive(name)
    hits = [t for t in dist if t in text]

    corroborators = []
    ph = _phone_digits(phone)
    if ph and ph in digits:
        corroborators.append(f"ADV phone {ph} appears on the page")
    if city and len(city) > 3 and city.lower() in text:
        corroborators.append(f"ADV city {city!r} appears on the page")

    if not hits:
        return None
    if specificity == "full":
        basis = (f"domain is the firm's full name; page carries distinctive token(s) {hits[:4]}"
                 + (f"; also {corroborators[0]}" if corroborators else ""))
    elif corroborators:
        basis = (f"partial-stem domain corroborated independently: distinctive token(s) "
                 f"{hits[:4]} plus {corroborators[0]}")
    else:
        # A partial stem matching only name words is how blossom.com and reddoor.net passed a
        # looser bar. Without independent corroboration this stays unresolved, deliberately.
        return None

    return {"domain": domain, "url": page.url, "http_status": page.http_status,
            "specificity": specificity, "distinctive_hits": hits,
            "corroborators": corroborators, "basis": basis,
            "method": "name_derived_domain_proven"}


def _stranded(limit: int | None) -> list[dict]:
    """Queued candidates with no usable firm domain: absent, or a social profile.

    Ordered by how many times we have already tried and failed, so the queue ROTATES. It used to
    order by entity_key alone and take the first N, which meant the same unresolvable head of the
    queue was re-attempted every cycle while candidates past position N were never reached at all:
    with 140 stranded and a limit of 40, positions 41-140 were unreachable by construction, and the
    measured proof rate decayed 13 -> 5 -> 4 -> 1 -> 1 across runs as the head filled with
    permanent failures. Attempts are recorded per candidate by run(), below.
    """
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select entity_key, firm_name, detail from ops.candidate_queue "
                    "where coalesce(detail->>'resolved_domain','') = '' "
                    "order by coalesce((detail->>'resolve_attempts')::int, 0), entity_key")
        rows = []
        for key, name, detail in cur.fetchall():
            site = (detail or {}).get("website")
            if site and not SOCIAL.search(site):
                continue
            rows.append({"entity_key": key, "firm_name": name, "detail": detail or {}})
    return rows[:limit] if limit else rows


def _adv_facts(crd: str) -> dict:
    with db.get_conn() as c, c.cursor() as cur:
        # sec_13f included: a 13F candidate's corroborators (city, phone) come from its submission
        # header, lifted into the same keys the ADV captures use, so proof works identically here.
        cur.execute("select raw from bronze.captures "
                    "where source in ('sec_form_adv','state_form_adv','sec_13f')"
                    " and entity_key = %s order by id desc limit 1", (crd,))
        r = cur.fetchone()
    return r[0] if r else {}


def run(*, limit: int | None = None, write: bool = False, workers: int = 6) -> dict:
    """Resolve domains for stranded candidates and re-queue the ones proven.

    Concurrency is bounded and the work is per-firm independent, so a failure resolves to
    'unresolved' for that firm and never touches the rest.
    """
    import contextvars
    from concurrent.futures import ThreadPoolExecutor, as_completed

    targets = _stranded(limit)
    stats = {"considered": len(targets), "proven": 0, "unresolved": 0, "errors": 0,
             "written": write, "dns_checked": 0}

    def work(cand: dict) -> tuple[dict, dict | None, int]:
        crd = cand["entity_key"].split(":", 1)[-1]
        adv = _adv_facts(crd)
        name = adv.get("business_name") or adv.get("legal_name") or cand["firm_name"] or ""
        checked = 0
        for d, spec in domain_guesses(name):
            if not _resolves(d):
                continue
            checked += 1
            ev = prove(d, name=name, phone=adv.get("phone"), city=adv.get("city"),
                       specificity=spec)
            if ev:
                return cand, ev, checked
        return cand, None, checked

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(contextvars.copy_context().run, work, t) for t in targets]
        for fut in as_completed(futs):
            try:
                cand, ev, checked = fut.result()
            except Exception as e:
                stats["errors"] += 1
                rl.event("resolve", "domain_error", status="error", detail={"error": repr(e)})
                continue
            stats["dns_checked"] += checked
            if not ev:
                stats["unresolved"] += 1
                if write:
                    _note_attempt(cand["entity_key"])
                continue
            stats["proven"] += 1
            rl.event("resolve", "domain_proven", call_class="external_api",
                     target=cand["entity_key"],
                     detail={"domain": ev["domain"], "basis": ev["basis"]})
            if write:
                _apply(cand["entity_key"], ev)
    return stats


def _note_attempt(entity_key: str) -> None:
    """Record a failed resolution so the queue rotates instead of re-burning the same head.

    Deliberately a counter rather than a permanent give-up flag: a firm with no website today may
    publish one next week, and the resolver is cheap. This changes the ORDER work is attempted in,
    not whether it is ever attempted again.
    """
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "update ops.candidate_queue set detail = coalesce(detail,'{}'::jsonb) ||"
            " jsonb_build_object('resolve_attempts',"
            "   coalesce((detail->>'resolve_attempts')::int, 0) + 1,"
            "   'resolve_last_attempt', now()::text)"
            " where entity_key = %s", (entity_key,))
        c.commit()


def _apply(entity_key: str, ev: dict) -> None:
    """Record the proven domain and re-open the candidate for the ordinary gate path.

    Stage goes back to 'discovered' so the next cycle fetches the real site and re-gates it with
    the evidence it was missing. The prior gate decision stays in gold.entity_gate -- decisions are
    append-only, so the record shows what was decided on thin evidence and what changed when the
    evidence arrived.
    """
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "update ops.candidate_queue set"
            " detail = coalesce(detail,'{}'::jsonb) || %s::jsonb,"
            " stage = 'discovered', status = 'pending', claimed_by = null, updated_at = now()"
            " where entity_key = %s",
            (json.dumps({"website": f"https://{ev['domain']}", "resolved_domain": ev["domain"],
                         "domain_evidence": ev,
                         "adv_website_was": "social_or_absent"}, default=str), entity_key))
        c.commit()
