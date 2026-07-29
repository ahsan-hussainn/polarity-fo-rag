"""Materiality classification for website changes (day 2 of the operating window; ADR-0027).

A hash flip says a page's TEXT moved; it does not say the FACTS moved. Day-1 cycles proved the
difference empirically: five same-hour `website_change` flags, all almost certainly rotating
content. This module closes that gap. When a cycle sees a changed site it re-fetches the firm's
pages, re-runs the extraction seam, and diffs the extracted facts against what silver currently
believes:

- facts identical  -> COSMETIC: trust event `noted`, nothing else changes; the new page text still
  lands in bronze (append-only history) so the judgment is auditable.
- facts moved      -> MATERIAL: fresh capture persisted to silver through the standard path (which
  preserves email-verification state, per the day-1 fix), trust event `refreshed` whose evidence IS
  the field delta. Gold picks the change up in the same cycle's rebuild phase.
- ratified primary contact missing from the new roster -> additional `decision_maker_gone` event,
  action `flagged`: the machine notices, but re-adjudication stays a human release control
  (ADR-0021) -- an automated demotion would be automation deciding what evidence standards require
  judgment to decide.

Every LLM call is ledgered with tokens + USD; a per-cycle budget caps spend and skips are logged
rather than silent (no silent caps)."""
from __future__ import annotations

import json
import re
import time

from pipeline import db
from pipeline.ops import runlog as rl


def _current_silver(crd: str) -> dict | None:
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select thesis, description, sectors, founded_year from silver.firms "
                    "where crd = %s", (crd,))
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("select name, title, is_principal from silver.people where firm_crd = %s",
                    (crd,))
        people = cur.fetchall()
    return {"thesis": row[0], "description": row[1], "sectors": sorted(row[2] or []),
            "founded_year": row[3],
            "team": {p[0].strip().lower(): (p[1], p[2]) for p in people}}


_PUNCT = re.compile(r"[^\w\s]+")
_WS = re.compile(r"\s+")
_TITLE_SYNONYMS = {"sr": "senior", "jr": "junior", "svp": "senior vice president",
                   "vp": "vice president", "evp": "executive vice president",
                   "cio": "chief investment officer", "ceo": "chief executive officer",
                   "coo": "chief operating officer", "cfo": "chief financial officer",
                   "mgr": "manager", "dir": "director"}
# _norm strips '&' as punctuation, so its spelled-out twin has to go too or 'A & B' and
# 'A and B' normalize apart -- measured on 'Co-Founder & CEO' vs 'Co Founder and CEO'.
_TITLE_DROP = {"and", "the", "of"}


def _norm(s: str | None) -> str:
    """Case/punctuation/whitespace-insensitive form. Kills the cheapest class of extraction
    variance without pretending two different statements are the same statement."""
    return _WS.sub(" ", _PUNCT.sub(" ", (s or "").lower())).strip()


def _norm_title(t: str | None) -> str:
    return " ".join(_TITLE_SYNONYMS.get(w, w) for w in _norm(t).split()
                    if w not in _TITLE_DROP)


def _norm_sectors(sectors) -> tuple[str, ...]:
    """Sector labels are LLM free text in list clothing: the same page yields 'Estate, Trusts &
    Philanthropy' one run and 'Estate Planning; Philanthropy' the next. Compare the normalized
    token set so ordering and label punctuation stop counting as facts moving."""
    tokens: set[str] = set()
    for s in sectors or []:
        for part in re.split(r"[,;/&]| and ", s or ""):
            n = _norm(part)
            if n:
                tokens.add(n)
    return tuple(sorted(tokens))


def _facts(sectors, founded_year, team: dict) -> dict:
    """The comparable fact surface, normalized. `team` maps name -> (title, is_principal)."""
    return {"sectors": _norm_sectors(sectors),
            "founded_year": founded_year,
            "roster": tuple(sorted(_norm(n) for n in team)),
            "titles": {_norm(n): _norm_title(t) for n, (t, _) in team.items()}}


def _diff_facts(old: dict, ext) -> tuple[dict[str, str], list[str]]:
    """Deltas between silver's beliefs and a fresh extraction, split into FACT-shaped changes
    (sectors, founded year, roster, titles) and WORDING changes (thesis/description prose).

    The prose split was a measured decision (runs 4-6: the same six dynamic-page firms re-flagged
    'material' every cycle on rewording alone). Runs 2-14 then falsified this module's next
    assumption -- that fact-shaped fields are stable under re-extraction. They are not: four firms
    re-flagged on nearly every cycle because sector labels and job titles are themselves LLM free
    text ('Equity, Fixed Income, Hedge Funds' vs 'Equity, Fixed Income, External Managers'). So
    fact fields are compared NORMALIZED here, and `classify` additionally requires a delta to
    reproduce on the next cycle before it moves silver.

    Returns (deltas keyed by field, wording notes) -- keyed so each field is confirmed separately.
    """
    wording: list[str] = []
    if _norm(old["thesis"]) != _norm(ext.thesis):
        wording.append("thesis wording shifted")
    if _norm(old["description"]) != _norm(ext.description):
        wording.append("description wording shifted")

    new_team = {m.name.strip().lower(): (m.title, m.is_principal) for m in ext.team}
    old_f = _facts(old["sectors"], old["founded_year"], old["team"])
    new_f = _facts(ext.sectors, ext.founded_year, new_team)

    deltas: dict[str, str] = {}
    if old_f["founded_year"] != new_f["founded_year"]:
        deltas["founded_year"] = f"founded_year {old_f['founded_year']} -> {new_f['founded_year']}"
    if old_f["sectors"] != new_f["sectors"]:
        deltas["sectors"] = f"sectors {list(old_f['sectors'])} -> {list(new_f['sectors'])}"
    gone = sorted(set(old_f["roster"]) - set(new_f["roster"]))
    added = sorted(set(new_f["roster"]) - set(old_f["roster"]))
    if gone:
        deltas["roster_gone"] = f"people no longer listed: {', '.join(gone[:5])}"
    if added:
        deltas["roster_added"] = f"people newly listed: {', '.join(added[:5])}"
    for name in sorted(set(old_f["titles"]) & set(new_f["titles"])):
        if old_f["titles"][name] != new_f["titles"][name]:
            deltas[f"title:{name}"] = (f"title changed for {name}: "
                                       f"{old_f['titles'][name]!r} -> {new_f['titles'][name]!r}")
    return deltas, wording


def _field_value(facts: dict, field: str):
    """The value a delta key refers to inside a fact fingerprint."""
    key, _, rest = field.partition(":")
    if key == "title":
        return (facts.get("titles") or {}).get(rest)
    return facts.get({"roster_gone": "roster", "roster_added": "roster"}.get(key, key))


def _confirm(crd: str, deltas: dict[str, str], new_facts: dict, *, write: bool
             ) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Split deltas into CONFIRMED, UNCONFIRMED (first sighting) and OSCILLATING.

    A site change is a claim about the world; extraction variance is a claim about the model. The
    first separator was reproduction -- a real change repeats, variance does not -- so a delta had
    to be seen twice consecutively before moving silver. Production falsified that as sufficient.

    Measured on CRD 329496 over runs 15/17/20/22: the extractor emitted exactly two sector sets,
    one of them intermittently dropping 'Asset Protection & Risk Management' from a ten-item list.
    Set A appeared at run 15, vanished at 17, returned at 20 and 22 -- and because 20 and 22
    agreed, the delta confirmed and rewrote silver. Nothing on the site had changed. This is the
    residual the day-2 finding predicted in writing ("a model that produces the wrong value ~50% of
    the time will occasionally emit it twice in a row").

    Reproduction cannot see it, because a returning value and a new value that repeated look
    identical when you only hold the previous observation. The sequence tells them apart: a value
    that was already seen, then superseded, and has now come back is OSCILLATING. Silver is not
    rewritten for it, and the trust event says so in those words -- which is a more useful thing to
    tell a reader than a fifth "site facts changed".
    """
    hist = rl.observation_history(crd, "fact_fingerprint", limit=6,
                                  exclude_run=rl.current_run())
    seq = [json.loads(v) for v, _, _ in hist if v]
    prev = seq[-1] if seq else {}
    if write:
        rl.observe(crd, "fact_fingerprint", json.dumps(new_facts, default=str, sort_keys=True))

    confirmed, unconfirmed, oscillating = {}, {}, {}
    for field, text in deltas.items():
        now = _field_value(new_facts, field)
        before = _field_value(prev, field) if prev else None
        past = [_field_value(f, field) for f in seq]
        # Did this exact value appear earlier and then get displaced by a different one? That is
        # what oscillation looks like in a sequence, and it stays true however many times the value
        # has since repeated: A,B,A,A is still a model alternating between A and B, not a site that
        # changed twice. Testing only "the previous observation differs" misses that -- measured on
        # 329496, where the A,B,A,A sequence confirmed on its second consecutive A.
        returned = any(_same(past[i], now) and any(not _same(past[j], now)
                                                   for j in range(i + 1, len(past)))
                       for i in range(len(past)))
        if returned:
            oscillating[field] = text
        elif prev and before is not None and _same(before, now):
            confirmed[field] = text
        else:
            unconfirmed[field] = text
    return confirmed, unconfirmed, oscillating


def _same(a, b) -> bool:
    """JSON round-trips tuples to lists; compare on shape-insensitive form."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def classify(firm: dict, *, write: bool, prior_run) -> dict:
    """Re-fetch + re-extract one changed firm and act on the result. Returns a summary dict;
    never raises (a materiality failure must not kill the cycle)."""
    from pipeline.bronze import website as web
    from pipeline.silver import extract as ex
    from pipeline.silver import load as sl

    crd, name, site = firm["crd"], firm.get("family_office_name"), firm.get("website")
    out = {"crd": crd, "verdict": "error", "deltas": []}
    try:
        old = _current_silver(crd)
        if old is None:
            rl.event("observe", "materiality_skip", target=crd, status="skipped",
                     detail={"reason": "no silver baseline for this firm"})
            out["verdict"] = "no_baseline"
            return out

        pages = web.fetch_site(site)
        texted = [p for p in pages if p.text]
        if not texted:
            rl.trust_event(crd, "website_change", None, None,
                           "page text changed per hash, but the re-fetch returned no readable "
                           "text; treated as unresolved, will retry next cycle", "flagged")
            out["verdict"] = "refetch_empty"
            return out
        page_dicts = [{"bronze_id": None, "page_type": p.page_type, "url": p.url,
                       "title": p.title, "text": p.text} for p in texted]
        text, urls, _, home = sl._combine(page_dicts)

        extractor = ex.get_extractor(None)
        t_ex = time.monotonic()
        result = extractor.extract(text, source_url=home)
        # Timed because this call is the system's next scaling bottleneck and architecture note 5
        # has to answer "what breaks first, at what volume" from measurement, not from a guess.
        extract_ms = int((time.monotonic() - t_ex) * 1000)
        usage = result.usage or {}
        tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        rl.event("observe", "materiality_extract", call_class="model", target=crd,
                 duration_ms=extract_ms, tokens_in=tin, tokens_out=tout,
                 usd=rl.usd_for("gpt-4o-mini", tin, tout),
                 detail={"pages": len(texted), "provider": result.provider})

        ext = result.extraction
        deltas, wording = _diff_facts(old, ext)
        new_team = {m.name.strip().lower(): (m.title, m.is_principal) for m in ext.team}
        new_facts = _facts(ext.sectors, ext.founded_year, new_team)
        confirmed, unconfirmed, oscillating = _confirm(crd, deltas, new_facts, write=write)
        material = list(confirmed.values())
        out["deltas"] = material
        out["unconfirmed"] = list(unconfirmed.values())
        out["oscillating"] = list(oscillating.values())

        # The raw capture is history either way (append-only; identical pages dedupe to 0 rows).
        if write:
            db.insert_captures([web._page_to_bronze_row(crd, name, p) for p in texted])

        since = f"since run {prior_run[2]} ({prior_run[1]:%Y-%m-%d %H:%M}Z)" if prior_run else ""
        if not material:
            out["verdict"] = ("oscillating" if oscillating else
                              "unconfirmed" if unconfirmed else "cosmetic")
            if oscillating:
                detail = (f"fact delta OSCILLATING ({'; '.join(list(oscillating.values())[:3])}) -- "
                          "this exact value was recorded earlier, replaced, and has now returned, "
                          "so the extractor is alternating between forms rather than the site "
                          "changing; silver not rewritten and this record's site-derived cells "
                          "cannot be kept current by re-extraction alone")
            elif unconfirmed:
                detail = (f"fact delta seen ONCE ({'; '.join(list(unconfirmed.values())[:4])}) -- "
                          "not yet reproduced, so it is not yet distinguishable from extraction "
                          "variance; silver not rewritten, re-checked next cycle")
            elif wording:
                detail = (f"prose wording shifted ({', '.join(wording)}) -- extraction variance on "
                          "dynamic page content, not a fact change")
            else:
                detail = "extracted facts identical"
            rl.trust_event(crd, "website_change", prior_run[0][:16] if prior_run else None, None,
                           f"home-page text changed {since}; {detail}", "noted")
            return out

        out["verdict"] = "material"
        if write:
            ids = _bronze_ids_for(crd, urls)
            sl._persist({"crd": crd, "firm_name": name}, result, urls, ids, home)
        pending = (f" ({len(unconfirmed)} further delta(s) seen once and awaiting reproduction)"
                   if unconfirmed else "")
        rl.trust_event(crd, "website_change", prior_run[0][:16] if prior_run else None, None,
                       f"site facts changed {since}: {'; '.join(material[:6])} -- each reproduced "
                       f"on two consecutive extractions{pending}; silver refreshed through the "
                       "standard path (verification state preserved); gold rebuilds this cycle",
                       "refreshed")

        # A ratified decision-maker disappearing is release-relevant: flag it for human
        # re-adjudication (ADR-0021 keeps that judgment human); never auto-demote here. Gated on
        # the roster delta being CONFIRMED: telling a reviewer their proven contact vanished, on
        # evidence that turns out to be one flaky extraction, spends the scarcest thing here.
        primary = (firm.get("primary_contact_name") or "").strip().lower()
        if primary and "roster_gone" in confirmed \
                and primary not in {m.name.strip().lower() for m in result.extraction.team}:
            rl.trust_event(crd, "decision_maker_gone", firm.get("primary_contact_name"), None,
                           f"ratified primary contact {firm.get('primary_contact_name')!r} is not "
                           "on the re-extracted roster -- needs human re-adjudication before the "
                           "record's contact evidence can be trusted (ADR-0021)", "flagged")
            out["primary_contact_gone"] = True
        return out
    except Exception as e:  # one firm's failure must not kill the cycle
        rl.event("observe", "materiality_error", target=crd, status="error",
                 detail={"error": repr(e)})
        rl.trust_event(crd, "website_change", None, None,
                       f"page text changed but materiality classification failed ({type(e).__name__});"
                       " flag stands, will retry next cycle", "flagged")
        return out


def _bronze_ids_for(crd: str, urls: list[str]) -> list[int]:
    """Latest bronze capture id per fetched page URL -- the lineage a fresh persist records."""
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select distinct on (raw->>'page_url') id from bronze.captures"
            " where source = 'website' and entity_key = %s and raw->>'page_url' = any(%s)"
            " order by raw->>'page_url', id desc",
            (crd, urls))
        return [r[0] for r in cur.fetchall()]
