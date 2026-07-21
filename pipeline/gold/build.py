"""Silver -> gold: assemble decision-grade, FO-MAX-shaped records (ADR-0011).

Gold is the product view. Per firm it carries the firm's facts, a PRIMARY and SECONDARY contact chosen
from the firm's principals by seniority, each with the honest email chain (email -> code -> explanation
-> grade), plus location from the SEC ADV capture and a data-completion score. Choosing the primary by
seniority is exactly where we beat FO-MAX: their Walton contact is an Accounting Manager, ours is the
firm's most senior principal by construction. Nothing here is re-derived from raw -- gold reads the
already-validated silver + the ADV bronze row, so every cell keeps its lineage.
"""
from __future__ import annotations

import csv
import os
import re

from pipeline import db

GOLD_CSV = "data/gold/family_office_dataset.csv"

# Curation gate (ADR-0015): discovery over-includes by design (over-discover then filter, ADR-0007),
# so the last filter is an explicit entity-validity judgment BEFORE a record can ship as a "family
# office". These firms were surfaced by ADV free-text/name matching but are not family offices, or
# their ADV WebAddr points at a different company so the enriched cells describe the wrong entity.
# A wrong record dressed as an FO is worse than a smaller honest file; reasons are persisted to
# gold.excluded_firms so the judgment is auditable.
EXCLUDED: dict[str, str] = {
    "125352": "Oak Hill Advisors: institutional alternative-credit manager (~$112B AUM, 435 ADV "
              "employees); our own gt-crosscheck flagged it (15/15 'principals'). Not a family office.",
    "157920": "Clearlake Capital Group: institutional private-equity firm, not a family office; "
              "matched only on ADV free-text.",
    "107876": "Hamilton Lane: global private-markets asset manager; ADV WebAddr resolves to a product "
              "subpage, so the extracted profile describes the wrong thing. Not a family office.",
    "143422": "Aksia: institutional alternatives research/advisory firm, not a family office.",
    "132167": "Cliffwater: institutional consultant/index provider; ADV WebAddr points at its index "
              "product site. Not a family office.",
    "140195": "Mariner: national RIA platform; ADV WebAddr is a marketing subdomain. Not a family "
              "office, and no contact intelligence was recoverable.",
    "171992": "SpiderRock Advisors: options-overlay manager acquired by BlackRock; ADV WebAddr is "
              "blackrock.com, so domain-derived cells belong to a different company.",
    "166159": "Naya Capital Management: long/short equity hedge fund, not a family office; record also "
              "carried contradictory ADV location data (London street address, UAE country).",
    "174027": "Parvus Asset Management: hedge fund, not a family office; no enrichable content.",
}

# Release policy (ADR-0019): vendor verdicts that make an address unsafe for customer use. A value
# with one of these codes is moved to gold.contact_audit and its operational field is nulled --
# enforced HERE, at the single writer, so no product surface (CSV, prompt, API, UI) can carry it.
# The grade/code/explanation stay on the record as verification metadata: "we probed, the vendor
# rejected every pattern" is honest disclosure (the shipped F rows already worked this way).
REJECTED_CODES = {"INVALID_API", "INVALID_NO_MX"}

# gold.records column -> human header for the shipped CSV (FO-MAX-style naming, in reading order).
_EXPORT_COLUMNS = [
    ("crd", "CRD"),  # stable SEC identifier: identity resolution must be auditable from the artifact
    ("family_office_name", "Family Office Name"), ("domain", "Domain"), ("website", "Website"),
    ("url_quality", "URL Quality"), ("corporate_linkedin", "Corporate LinkedIn"),
    ("street_address", "Street Address"), ("city", "City"), ("state", "State"),
    ("country", "Country"), ("firm_phone", "Firm Phone"), ("founded_year", "Founded Year"),
    ("aum_usd", "AUM (USD)"),
    ("investment_thesis", "Investment Thesis"), ("description", "Description"),
    ("investing_sectors", "Investing Sectors"),
    ("primary_contact_name", "Primary Contact"), ("primary_contact_title", "Primary Title"),
    ("primary_authority_basis", "Primary Authority Basis"),
    ("primary_selection_basis", "Why This Contact"),
    ("primary_contact_location", "Primary Contact Location"),
    ("primary_contact_email", "Primary Email"), ("primary_email_grade", "Primary Email Grade"),
    ("primary_email_code", "Primary Email Validation Code"),
    ("primary_email_explanation", "Primary Email Explanation"),
    ("secondary_contact_name", "Secondary Contact"), ("secondary_contact_title", "Secondary Title"),
    ("secondary_contact_email", "Secondary Email"), ("secondary_email_grade", "Secondary Email Grade"),
    ("secondary_email_code", "Secondary Email Validation Code"),
    ("secondary_email_explanation", "Secondary Email Explanation"),
    # Per-cell basis (the brief's verification test): which source each cell family traces to.
    # ADV filing -> name/address/phone/AUM/founded-registration; website -> thesis/description/
    # sectors/team; the email chain carries its own method (code + explanation) per address.
    ("adv_filing_url", "Firm Facts Source (SEC Form ADV)"),
    ("profile_source_url", "Profile Source (Firm Website)"),
    ("entity_category", "Entity Category"), ("category_basis", "Category Basis"),
    ("person_status", "Person Status"), ("release_state", "Release State"),
    # decision-grade KPIs (ADR-0013 migration)
    ("actionability_tier", "Actionability"), ("actionability_score", "Actionability Score"),
    ("confidence_score", "Confidence Score"),
    ("data_asof", "Firm Data As-Of (ADV filing)"), ("is_stale", "Stale?"),
    ("data_completion_score", "Data Completion Score"), ("principal_count", "Principal Count"),
    ("people_count", "People Count"),
]


# Firm-level columns for the reclassified sidecar (no contact fields: their decision-makers were
# not proven to the ADR-0021 standard, so we present the firm, not an unverified person).
_RECLASS_COLUMNS = [
    ("crd", "CRD"), ("family_office_name", "Firm Name"), ("entity_category", "Entity Category"),
    ("category_basis", "Category Basis"), ("domain", "Domain"), ("website", "Website"),
    ("city", "City"), ("state", "State"), ("aum_usd", "AUM (USD)"), ("firm_phone", "Firm Phone"),
    ("investment_thesis", "Investment Thesis"), ("investing_sectors", "Investing Sectors"),
    ("adv_filing_url", "Firm Facts Source (SEC Form ADV)"),
]


def export(path: str = GOLD_CSV) -> dict:
    """Write the three deliverable CSVs (the product is family offices only; the rest is auditable
    remainder): family_office_dataset.csv = the QUALIFYING affirmed family offices; reclassified_firms
    .csv = real firms whose FO label was marketing (wealth managers / RIAs), firm-level only;
    quarantined.csv = not-a-family-office + unresolved. Every one of the 50 lands in exactly one file."""
    cols = [c for c, _ in _EXPORT_COLUMNS]
    rcols = [c for c, _ in _RECLASS_COLUMNS]
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def _write(p, header, rows):
        with open(p, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for r in rows:
                w.writerow(["; ".join(v) if isinstance(v, list) else v for v in r])

    with db.get_conn() as c, c.cursor() as cur:
        # Product = qualifying family offices only. Actionability-first: published email (PUB, proven)
        # > vendor-deliverable inferred (A) > catch-all (B) > no email; contactless records sink.
        cur.execute(f"select {','.join(cols)} from gold.records where release_state = 'qualifying' "
                    "order by case coalesce(primary_email_grade,'Z') "
                    " when 'PUB' then 0 when 'A' then 1 when 'B' then 2 else 6 end, "
                    "data_completion_score desc, family_office_name")
        fo_rows = cur.fetchall()
        # Recent signals per firm (correction #6): most recent first, for the "why now" summary column
        # and the full-detail record_signals.csv sidecar.
        cur.execute("select crd, signal_type, signal_date, description, source_url "
                    "from gold.record_signals order by crd, signal_date desc")
        sig_by_crd: dict[str, list] = {}
        for scrd, stype, sdate, sdesc, surl in cur.fetchall():
            sig_by_crd.setdefault(scrd, []).append((stype, sdate, sdesc, surl))
        # Reclassified = affirmed-but-not-FO (kept for audit, firm-level, not counted as FOs).
        cur.execute(f"select {','.join(rcols)} from gold.records "
                    "where release_state = 'unresolved' and entity_category in "
                    "('wealth_manager','ria_with_fo_practice') order by entity_category, family_office_name")
        reclass_rows = cur.fetchall()
        cur.execute("select crd, family_office_name, entity_category, category_basis, release_reasons "
                    "from gold.records where release_state = 'quarantined' order by family_office_name")
        quarantined = cur.fetchall()

    # Main product CSV: map columns + a "Recent Signals" summary (count + most-recent dated event).
    crd_idx = cols.index("crd")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([h for _, h in _EXPORT_COLUMNS] + ["Recent Signals"])
        for r in fo_rows:
            out = ["; ".join(v) if isinstance(v, list) else v for v in r]
            sigs = sig_by_crd.get(r[crd_idx], [])
            if sigs:
                stype, sdate, sdesc, _ = sigs[0]
                summary = f"{len(sigs)} signal(s); latest {sdate} ({stype}): {sdesc[:80]}"
            else:
                summary = "no recent signal found"
            w.writerow(out + [summary])
    rpath = os.path.join(os.path.dirname(path), "reclassified_firms.csv")
    _write(rpath, [h for _, h in _RECLASS_COLUMNS], reclass_rows)
    # Full-detail signals sidecar: one row per dated, sourced signal.
    spath = os.path.join(os.path.dirname(path), "record_signals.csv")
    with open(spath, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["CRD", "Signal Type", "Date", "Description", "Source URL"])
        for scrd in sorted(sig_by_crd):
            for stype, sdate, sdesc, surl in sig_by_crd[scrd]:
                w.writerow([scrd, stype, sdate, sdesc, surl])
    qpath = os.path.join(os.path.dirname(path), "quarantined.csv")
    with open(qpath, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["CRD", "Firm Name", "Entity Category", "Category Basis", "Release Reasons"])
        for crd, name, cat, basis, reasons in quarantined:
            w.writerow([crd, name, cat, basis, "; ".join(reasons or [])])
    return {"family_offices": len(fo_rows), "reclassified": len(reclass_rows),
            "quarantined": len(quarantined), "signals": sum(len(v) for v in sig_by_crd.values()),
            "path": path, "reclassified_path": rpath, "quarantined_path": qpath, "signals_path": spath}

# Seniority score for picking the primary/secondary contact among a firm's principals. Higher = more
# senior / better first point of contact for a capital allocator.
def principal_rank(title: str | None) -> int:
    t = (title or "").lower()
    def has(w): return re.search(r"\b" + w + r"\b", t) is not None
    if any(w in t for w in ("founder", "owner", "managing member")): return 100
    if "managing partner" in t: return 95
    if has("chief executive") or has("ceo"): return 90
    if has("president") and "vice" not in t: return 85
    if has("chairman"): return 84
    if has("chief investment officer") or has("cio"): return 80
    if has("principal"): return 70
    if "portfolio manager" in t: return 60
    if "managing director" in t: return 50
    if "partner" in t: return 45
    return 10


# Key cells the completion score rewards (firm facts + a named, reachable primary contact). Note:
# email GRADE is intentionally NOT a scored field -- it is metadata about the email, so scoring both
# email and grade would double-count one underlying fact (a record with no email would lose two
# points for one gap). This measures FIELD COMPLETENESS, not trust; the proof signals (entity
# category, person status, authority basis, email grade) are their own columns on the record.
_SCORE_FIELDS = (
    "family_office_name", "domain", "website", "description", "investment_thesis",
    "investing_sectors", "founded_year", "city",
    "primary_contact_name", "primary_contact_title", "primary_contact_email",
)


def _completion(row: dict) -> int:
    got = sum(1 for f in _SCORE_FIELDS if row.get(f) not in (None, "", [], "{}"))
    return round(100 * got / len(_SCORE_FIELDS))


# Reach quality by email/channel basis -- the axis that varies once a decision-maker is proven.
_REACH = {"PUB": 55, "A": 40, "B": 30}   # firm-published > vendor-deliverable > catch-all


def _actionability(row: dict) -> tuple[str | None, int | None]:
    """Can a fund manager act on this FO today? Only qualifying FOs are scored (others = N/A).
    base = a proven decision-maker (stated authority worth more than title-inferred);
    reach = the contact channel (published/vendor-deliverable email > catch-all > phone > LinkedIn)."""
    if row.get("release_state") != "qualifying" or row.get("person_status") != "proven":
        return None, None
    base = 40 if row.get("primary_authority_basis") == "stated" else 30
    reach = _REACH.get(row.get("primary_email_grade"))
    if reach is None:  # no shippable email -> fall to the next channel
        reach = 15 if row.get("firm_phone") else (8 if row.get("corporate_linkedin") else 0)
    score = base + reach
    tier = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
    return tier, score


def _confidence(row: dict) -> int | None:
    """How well-PROVEN the record is (distinct from reach): affirmed entity (>=2 evidence classes) +
    person proof (Schedule A-anchored, stated > title-inferred) + email proof (published proves the
    address is theirs; inferred does not). A record can be high-confidence but low-actionability
    (e.g. a proven sole owner with no published email)."""
    if row.get("release_state") != "qualifying":
        return None
    entity = 40  # every qualifying FO cleared the >=2 independent-evidence-class bar (ADR-0020)
    person = 40 if row.get("primary_authority_basis") == "stated" else 25
    g = row.get("primary_email_grade")
    email = 20 if g == "PUB" else 10 if g in ("A", "B") else 5
    return min(100, entity + person + email)


def _adv_facts(cur, crd: str) -> dict:
    """Everything gold takes from the firm's SEC ADV capture: location, street, phone, AUM, and the
    filing URL that is the verifiable basis for all of them (data we already hold -- free parity)."""
    cur.execute("select raw->>'city', raw->>'state', raw->>'country', raw->>'street1', "
                "raw->>'street2', raw->>'phone', raw->>'raum_total', source_url, "
                "raw->>'latest_filing_date' "
                "from bronze.captures where source='sec_form_adv' and entity_key=%s limit 1", (crd,))
    r = cur.fetchone()
    if not r:
        return {}
    street = ", ".join(p for p in (r[3], r[4]) if p) or None
    return {"city": r[0], "state": r[1], "country": r[2], "street_address": street,
            "firm_phone": r[5], "aum_usd": int(r[6]) if r[6] else None, "adv_filing_url": r[7],
            "latest_filing_date": r[8]}


def _url_quality(cur, crd: str) -> str | None:
    """Derive a FO-MAX-style URL Quality from our own fetch signals (pages, HTTP status, TLS)."""
    cur.execute("select raw->>'http_status', raw->>'insecure', raw->>'page_type' from bronze.captures "
                "where source='website' and entity_key=%s", (crd,))
    rows = cur.fetchall()
    if not rows:
        return None
    pages = len(rows)
    home_ok = any(r[2] == "home" and str(r[0]) == "200" for r in rows)
    insecure = any(str(r[1]).lower() == "true" for r in rows)
    if home_ok and not insecure and pages >= 3:
        return "Highest"
    if home_ok and not insecure:
        return "Medium"
    if home_ok:
        return "Medium-Low"
    return "Lower"


def _released_email(cur, crd: str, role: str, contact: dict, write: bool) -> str | None:
    """ADR-0019 release gate for one contact slot. A vendor-rejected address (REJECTED_CODES) is
    recorded in gold.contact_audit and NOT released -- returns None so the operational field ships
    blank. Non-rejected addresses pass through unchanged."""
    email, code = contact.get("email"), contact.get("code")
    if not email or code not in REJECTED_CODES:
        return email
    if write:
        cur.execute(
            "insert into gold.contact_audit (crd, contact_role, contact_name, email, grade, code, "
            "explanation, reason) values (%s,%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (crd, contact_role, email) do nothing",
            (crd, role, contact.get("name"), email, contact.get("grade"), code,
             contact.get("explanation"),
             "vendor rejected as invalid/undeliverable; unsafe for customer use (ADR-0019)"))
    return None


def _contacts(cur, crd: str) -> list[dict]:
    """A firm's principals, most-senior first, with their email grade chain."""
    cur.execute(
        "select name, title, email, quality_grade, email_verification->>'code', "
        "       email_verification->>'explanation' "
        "from silver.people where firm_crd=%s and is_principal order by id", (crd,))
    people = [{"name": n, "title": t, "email": e, "grade": g, "code": c, "explanation": x}
              for n, t, e, g, c, x in cur.fetchall()]
    people.sort(key=lambda p: principal_rank(p["title"]), reverse=True)
    return people


def _release(adj: dict | None) -> tuple[str, list[str], str | None, str | None]:
    """ADR-0019 release decision from the ADR-0020 entity adjudication. Note two distinct senses of
    'unresolved': an *entity* whose type could not be affirmed is QUARANTINED (policy: not released,
    not counted, not retrievable); an affirmed entity whose *person* evidence is still pending
    (ADR-0021, WS3) keeps release_state 'unresolved' -- it ships during the repair, labeled, but is
    not yet certified 'qualifying'. Returns (release_state, reasons, entity_category, entity_status)."""
    person_pending = "person evidence pending (ADR-0021)"
    if adj is None:  # defensive: no adjudication on record (should not occur post-WS2)
        return "unresolved", ["no entity adjudication on record"], None, None
    if adj["status"] == "rejected":
        return "quarantined", [f"entity rejected ({adj['category']}): {adj['rationale']}"], adj["category"], "rejected"
    if adj["status"] == "unresolved":
        return ("quarantined", [f"entity type unresolved: {adj['rationale']}"],
                adj["category"], "unresolved")
    if adj.get("duplicate_of"):
        return ("quarantined", [f"duplicate of CRD {adj['duplicate_of']}: {adj['rationale']}"],
                adj["category"], "affirmed")
    # affirmed entity (FO or reclassified non-FO): ships, labeled by category, pending the person pass
    return "unresolved", [person_pending], adj["category"], "affirmed"


# Affirmed FO categories -- only these count toward the "family office" product and the 500 (ADR-0020).
_FO_CATEGORIES = {"single_family_office", "multi_family_office"}


def _apply_contact(cur, crd: str, row: dict, cadj: dict, write: bool, rejected: set) -> None:
    """Overlay the ratified decision-maker (ADR-0021/0022) onto the product row, replacing the
    title-ladder pick, and resolve the honest email for that person:
      PUB -- individual address the firm itself publishes (proven to be theirs);
      A/B/C -- WS3b vendor-verified INFERRED pattern, labeled precisely (A deliverable != proven
               to be their mailbox; B catch-all; C unknown);
      D/F -- vendor-rejected: quarantined to gold.contact_audit (ADR-0019), never shipped.
    A guess is never presented as the person's confirmed address."""
    pri = cadj.get((crd, "primary"))
    sec = cadj.get((crd, "secondary"))
    if not pri:
        return
    row["person_status"] = "proven"
    row["primary_authority_basis"] = pri["authority_basis"]
    row["primary_selection_basis"] = pri["selection_basis"]
    for role, c in (("primary", pri), ("secondary", sec)):
        c = c or {}
        row[f"{role}_contact_name"] = c.get("name")
        row[f"{role}_contact_title"] = c.get("title")
        email = grade = code = expl = None
        pub, inf = c.get("published_email"), c.get("inferred_email")
        # Once the verifier rejected an address it stays rejected: an address anywhere in the
        # vendor-rejected audit trail is never shipped, even if a later (temporally noisy) probe
        # softened its grade (ADR-0019). This suppression is what the WS6 reconciliation enforces.
        if pub and pub.lower() not in rejected:
            email, grade, code = pub, "PUB", "PUBLISHED_FIRM_SITE"
            expl = "individual address published on the firm's own website (source: the firm itself)"
        elif c.get("inferred_grade") in ("A", "B") and inf and inf.lower() not in rejected:
            # only a vendor-DELIVERABLE (A) or catch-all-plausible (B) inferred address ships. A bare
            # 'unknown' (C) inference is a uniform first.last guess the vendor could not confirm; per
            # the WS6 human review it is withheld rather than shipped as look-alike signal -- the firm
            # routes to its SEC-filed phone / LinkedIn instead (the conservative, more honest choice).
            grade, code = c["inferred_grade"], c["inferred_code"]
            email = inf
            caveat = (" Inferred pattern for the proven contact; vendor-deliverable but NOT proven to "
                      "be this person's mailbox." if grade == "A" else "")
            expl = (c.get("inferred_explanation") or "") + caveat
        elif inf and inf.lower() in rejected:
            expl = "no individual address published; the inferred pattern was previously vendor-rejected (withheld)"
        elif c.get("inferred_grade") == "C":
            expl = ("no individual address published; the inferred pattern was unconfirmed by the vendor "
                    "and is withheld (WS6) -- reach via the firm's SEC-filed phone / LinkedIn")
        elif c.get("inferred_grade") in ("D", "F") and c.get("inferred_email"):
            # vendor-rejected inferred address for the proven person: audit it, ship nothing (ADR-0019)
            if write:
                cur.execute(
                    "insert into gold.contact_audit (crd, contact_role, contact_name, email, grade, "
                    "code, explanation, reason) values (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "on conflict (crd, contact_role, email) do nothing",
                    (crd, role, c.get("name"), c["inferred_email"], c["inferred_grade"],
                     c.get("inferred_code"), c.get("inferred_explanation"),
                     "WS3b: vendor rejected the inferred address for the proven contact (ADR-0019)"))
            expl = "no individual address published; inferred pattern was vendor-rejected (quarantined)"
        else:
            expl = "no individual address published or verifiable for this contact"
        row[f"{role}_contact_email"] = email
        row[f"{role}_email_grade"] = grade
        row[f"{role}_email_code"] = code
        row[f"{role}_email_explanation"] = expl


def build(write: bool = False) -> dict:
    """Assemble gold.records from silver + ADV bronze. Upserts one row per firm when write=True.
    Firms in EXCLUDED (ADR-0015) are skipped, recorded in gold.excluded_firms, and removed from
    gold.records if a previous build wrote them."""
    out = {"written": write, "firms": 0, "with_primary": 0, "excluded": len(EXCLUDED), "rows": []}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, category, status, duplicate_of, rationale from gold.entity_adjudications")
        adjudications = {r[0]: {"category": r[1], "status": r[2], "duplicate_of": r[3],
                                "rationale": r[4]} for r in cur.fetchall()}
        cur.execute("select crd, contact_role, name, title, selection_basis, authority_basis, "
                    "published_email, inferred_email, inferred_grade, inferred_code, "
                    "inferred_explanation from gold.contact_adjudications")
        cadj = {(r[0], r[1]): {"name": r[2], "title": r[3], "selection_basis": r[4],
                               "authority_basis": r[5], "published_email": r[6],
                               "inferred_email": r[7], "inferred_grade": r[8],
                               "inferred_code": r[9], "inferred_explanation": r[10]}
                for r in cur.fetchall()}
        # Addresses the verifier has EVER rejected (from prior builds' audit) -- never re-shipped.
        cur.execute("select lower(email) from gold.contact_audit")
        rejected_addrs = {r[0] for r in cur.fetchall()}
        cur.execute("select crd, firm_name, domain, thesis, description, sectors, founded_year, "
                    "extracted_by, corporate_linkedin, source_urls, "
                    "(select count(*) from silver.people p where p.firm_crd=f.crd) "
                    "from silver.firms f order by firm_name")
        firms = cur.fetchall()

        for crd, name, domain, thesis, desc, sectors, founded, by, linkedin, src_urls, people_ct in firms:
            if crd in EXCLUDED:
                if write:
                    cur.execute("insert into gold.excluded_firms (crd, firm_name, reason) "
                                "values (%s,%s,%s) on conflict (crd) do update set "
                                "reason=excluded.reason, decided_at=now()", (crd, name, EXCLUDED[crd]))
                    cur.execute("delete from gold.records where crd=%s", (crd,))
                continue
            contacts = _contacts(cur, crd)
            adv = _adv_facts(cur, crd)
            city, state, country = adv.get("city"), adv.get("state"), adv.get("country")
            website = f"https://{domain}" if domain else None
            p = contacts[0] if len(contacts) > 0 else {}
            s = contacts[1] if len(contacts) > 1 else {}
            p_email = _released_email(cur, crd, "primary", p, write) if p else None
            s_email = _released_email(cur, crd, "secondary", s, write) if s else None
            contact_loc = ", ".join(x for x in (city, state) if x) if p else None
            row = {
                "crd": crd, "family_office_name": name, "domain": domain, "website": website,
                "description": desc, "investment_thesis": thesis, "investing_sectors": sectors or [],
                "founded_year": founded, "city": city, "state": state, "country": country,
                "street_address": adv.get("street_address"), "url_quality": _url_quality(cur, crd),
                "firm_phone": adv.get("firm_phone"), "aum_usd": adv.get("aum_usd"),
                "adv_filing_url": adv.get("adv_filing_url"),
                "profile_source_url": (src_urls[0] if src_urls else None),
                "corporate_linkedin": linkedin, "primary_contact_location": contact_loc,
                "primary_contact_name": p.get("name"), "primary_contact_title": p.get("title"),
                "primary_contact_email": p_email, "primary_email_grade": p.get("grade"),
                "primary_email_code": p.get("code"), "primary_email_explanation": p.get("explanation"),
                "secondary_contact_name": s.get("name"), "secondary_contact_title": s.get("title"),
                "secondary_contact_email": s_email, "secondary_email_grade": s.get("grade"),
                "secondary_email_code": s.get("code"), "secondary_email_explanation": s.get("explanation"),
                "principal_count": len(contacts), "people_count": people_ct, "extracted_by": by,
            }
            # ADR-0019: no record is presumed qualifying; the entity adjudication (ADR-0020) and,
            # in WS3, the person evidence pass (ADR-0021) decide what release permits.
            (row["release_state"], row["release_reasons"],
             row["entity_category"], row["entity_status"]) = _release(adjudications.get(crd))
            adj = adjudications.get(crd)
            row["category_basis"] = adj["rationale"] if adj else None
            # ADR-0021/0022: overlay the proven decision-maker; an affirmed FO with a ratified person
            # pass earns 'qualifying' (counts toward the 500). Reclassified non-FOs keep their old
            # contacts and stay unresolved -- they are not family offices and are not counted.
            if (crd, "primary") in cadj:
                _apply_contact(cur, crd, row, cadj, write, rejected_addrs)
                if row["entity_status"] == "affirmed" and row["entity_category"] in _FO_CATEGORIES:
                    row["release_state"] = "qualifying"
                    row["release_reasons"] = [f"entity affirmed {row['entity_category']} (ADR-0020); "
                                              f"decision-maker proven (ADR-0021)"]
            row["data_completion_score"] = _completion(row)
            # Record-level KPIs (ADR-0013 migration): actionability (act today?), confidence (how
            # well-proven?), and freshness (SEC ADV filing date + a staleness flag when > 15 months,
            # past the annual-filing window). Computed for qualifying FOs; N/A elsewhere.
            row["actionability_tier"], row["actionability_score"] = _actionability(row)
            row["confidence_score"] = _confidence(row)
            filed = adv.get("latest_filing_date")
            row["data_asof"] = filed
            row["is_stale"] = None
            if filed and row.get("release_state") == "qualifying":
                y, m = (int(x) for x in filed[:7].split("-"))
                months = (2026 - y) * 12 + (7 - m)  # relative to the build month (2026-07)
                row["is_stale"] = months > 15
            out["firms"] += 1
            if p:
                out["with_primary"] += 1
            out["rows"].append({"firm": name, "primary": p.get("name"), "title": p.get("title"),
                                "grade": p.get("grade"), "score": row["data_completion_score"]})
            if write:
                cols = list(row)
                cur.execute(
                    f"insert into gold.records ({','.join(cols)}) "
                    f"values ({','.join(['%s'] * len(cols))}) "
                    f"on conflict (crd) do update set "
                    + ", ".join(f"{k}=excluded.{k}" for k in cols if k != "crd")
                    + ", generated_at=now()",
                    [row[k] for k in cols])
        if write:
            c.commit()
    return out
