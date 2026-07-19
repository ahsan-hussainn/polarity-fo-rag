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
    ("entity_category", "Entity Category"), ("release_state", "Release State"),
    ("data_completion_score", "Data Completion Score"), ("principal_count", "Principal Count"),
    ("people_count", "People Count"),
]


def export(path: str = GOLD_CSV) -> dict:
    """Write gold.records to a CSV deliverable (FO-MAX-style columns), best rows first.
    Quarantined records do NOT ship in the product file (ADR-0019/0020) -- they are written to a
    separate quarantined.csv beside it, with their release reasons, as the auditable remainder."""
    cols = [c for c, _ in _EXPORT_COLUMNS]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with db.get_conn() as c, c.cursor() as cur:
        # Actionability-first ordering: a reviewer reads row 1 first, so lead with records a client
        # could act on today (vendor-deliverable A email > B catch-all > C unknown > none),
        # then by completion. Completion alone would rank a contactless record above a deliverable one.
        cur.execute(f"select {','.join(cols)} from gold.records "
                    "where release_state != 'quarantined' "
                    "order by case coalesce(primary_email_grade,'Z') "
                    " when 'A' then 0 when 'B' then 1 when 'C' then 2 when 'D' then 3 "
                    " when 'F' then 4 else 5 end, "
                    "data_completion_score desc, family_office_name")
        rows = cur.fetchall()
        cur.execute("select crd, family_office_name, entity_category, release_reasons "
                    "from gold.records where release_state = 'quarantined' order by family_office_name")
        quarantined = cur.fetchall()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([h for _, h in _EXPORT_COLUMNS])
        for r in rows:
            out = []
            for col, v in zip(cols, r):
                out.append("; ".join(v) if isinstance(v, list) else v)
            w.writerow(out)
    qpath = os.path.join(os.path.dirname(path), "quarantined.csv")
    with open(qpath, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["CRD", "Firm Name", "Entity Category", "Release Reasons"])
        for crd, name, cat, reasons in quarantined:
            w.writerow([crd, name, cat, "; ".join(reasons or [])])
    return {"rows": len(rows), "quarantined": len(quarantined), "path": path, "quarantined_path": qpath}

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


# Key cells the completion score rewards (firm facts + a gradeable primary contact).
_SCORE_FIELDS = (
    "family_office_name", "domain", "website", "description", "investment_thesis",
    "investing_sectors", "founded_year", "city",
    "primary_contact_name", "primary_contact_title", "primary_contact_email",
    "primary_email_grade",
)


def _completion(row: dict) -> int:
    # A vendor-rejected contact slot is not "complete" data (WS0 audit: D-grades were inflating
    # this score). The grade cell only counts when it describes a usable-or-unconfirmed address.
    got = sum(1 for f in _SCORE_FIELDS if row.get(f) not in (None, "", [], "{}"))
    if row.get("primary_email_grade") in ("D", "F"):
        got -= 1  # the grade field is populated, but it certifies an unusable slot
    return round(100 * max(got, 0) / len(_SCORE_FIELDS))


def _adv_facts(cur, crd: str) -> dict:
    """Everything gold takes from the firm's SEC ADV capture: location, street, phone, AUM, and the
    filing URL that is the verifiable basis for all of them (data we already hold -- free parity)."""
    cur.execute("select raw->>'city', raw->>'state', raw->>'country', raw->>'street1', "
                "raw->>'street2', raw->>'phone', raw->>'raum_total', source_url "
                "from bronze.captures where source='sec_form_adv' and entity_key=%s limit 1", (crd,))
    r = cur.fetchone()
    if not r:
        return {}
    street = ", ".join(p for p in (r[3], r[4]) if p) or None
    return {"city": r[0], "state": r[1], "country": r[2], "street_address": street,
            "firm_phone": r[5], "aum_usd": int(r[6]) if r[6] else None, "adv_filing_url": r[7]}


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
    """ADR-0019 release decision from the ADR-0020 entity adjudication (person gate, ADR-0021,
    lands in WS3 and is a pending reason until then). Returns
    (release_state, reasons, entity_category, entity_status)."""
    person_pending = "person evidence pending (ADR-0021)"
    if adj is None or adj["status"] == "unresolved":
        return ("unresolved",
                ["entity adjudication pending (ADR-0020)", person_pending],
                adj["category"] if adj else None, adj["status"] if adj else None)
    if adj["status"] == "rejected":
        return "quarantined", [f"entity rejected: {adj['rationale']}"], adj["category"], "rejected"
    if adj.get("duplicate_of"):
        return ("quarantined", [f"duplicate of CRD {adj['duplicate_of']}: {adj['rationale']}"],
                adj["category"], "affirmed")
    return "unresolved", [person_pending], adj["category"], "affirmed"


def build(write: bool = False) -> dict:
    """Assemble gold.records from silver + ADV bronze. Upserts one row per firm when write=True.
    Firms in EXCLUDED (ADR-0015) are skipped, recorded in gold.excluded_firms, and removed from
    gold.records if a previous build wrote them."""
    out = {"written": write, "firms": 0, "with_primary": 0, "excluded": len(EXCLUDED), "rows": []}
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd, category, status, duplicate_of, rationale from gold.entity_adjudications")
        adjudications = {r[0]: {"category": r[1], "status": r[2], "duplicate_of": r[3],
                                "rationale": r[4]} for r in cur.fetchall()}
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
            row["data_completion_score"] = _completion(row)
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
