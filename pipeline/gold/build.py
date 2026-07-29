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
from datetime import date

from pipeline import db
from pipeline.gold import gate, release_band

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
    # ADR-0034: a buyer must be able to tell a human-ratified record from a gate-released one on
    # the artifact itself, not only in the docs.
    ("release_basis", "Release Basis"), ("release_basis_detail", "Release Basis Detail"),
    # decision-grade KPIs (ADR-0013 migration)
    ("reachability_tier", "Reachability"), ("reachability_score", "Reachability Score"),
    ("confidence_score", "Confidence Score"),
    ("data_asof", "Firm Data As-Of (ADV filing)"), ("is_stale", "Source Doc Older Than 15mo"),
    # ADR-0037: what the system actually observed, not calendar arithmetic.
    ("last_checked_at", "Last Checked By System"), ("trust_state", "Trust State"),
    ("trust_reason", "Trust Reason"),
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
        order = ("order by case coalesce(primary_email_grade,'Z') "
                 " when 'PUB' then 0 when 'A' then 1 when 'B' then 2 else 6 end, "
                 "data_completion_score desc, family_office_name")
        cur.execute(f"select {','.join(cols)} from gold.records where release_state = 'qualifying' "
                    f"and entity_category = any(%s) {order}", (list(_FO_CATEGORIES),))
        fo_rows = cur.fetchall()
        # ADR-0028 forbids blending: a family office and an evidenced family-office PRACTICE are
        # both counted, never in the same number and never in the same file. The honest sentence is
        # "N family offices (SFO+MFO) + M evidenced family-office practices", and that sentence is
        # only sayable if the surfaces are separate.
        cur.execute(f"select {','.join(cols)} from gold.records where release_state = 'qualifying' "
                    f"and entity_category = 'embedded_fo_practice' {order}")
        practice_rows = cur.fetchall()
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
        # Confirmed family offices whose DECISION-MAKER evidence is still pending (ADR-0021). A
        # distinct, buyer-meaningful state: the firm is affirmed, the person to call is not yet
        # evidenced. Stage 2 created it -- entity affirmation and contact adjudication are separate
        # human gates, so a climb produces records that clear the first and await the second. They
        # belonged to no export until now, which is exactly what the reconcile partition check
        # caught on scheduled run 20 (24+18+8 against a DB holding 53).
        cur.execute(f"select {','.join(rcols)} from gold.records "
                    "where release_state = 'unresolved' and entity_category = any(%s) "
                    "order by entity_category, family_office_name", (list(_COUNTED_CATEGORIES),))
        pending_rows = cur.fetchall()
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
    ppath = os.path.join(os.path.dirname(path), "pending_decision_maker.csv")
    _write(ppath, [h for _, h in _RECLASS_COLUMNS], pending_rows)
    fpath = os.path.join(os.path.dirname(path), "family_office_practices.csv")
    _write(fpath, [h for _, h in _EXPORT_COLUMNS], practice_rows)
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
    return {"family_offices": len(fo_rows), "fo_practices": len(practice_rows),
            "reclassified": len(reclass_rows), "pending_decision_maker": len(pending_rows),
            "quarantined": len(quarantined), "signals": sum(len(v) for v in sig_by_crd.values()),
            "path": path, "reclassified_path": rpath, "quarantined_path": qpath,
            "pending_path": ppath, "practices_path": fpath, "signals_path": spath}

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


def _reachability(row: dict) -> tuple[str | None, int | None]:
    """How directly can you reach the proven decision-maker? Only qualifying FOs are scored.
    The EMAIL is the only direct-to-the-person channel; phone/LinkedIn are firm-level cold routes.
      High   -- a usable email to the person: firm-published (PUB) or vendor-deliverable (A).
      Medium -- a plausible email to try (B), OR both the SEC phone and LinkedIn (two cold routes).
      Low    -- a single cold route only (phone-only / LinkedIn-only), or nothing."""
    if row.get("release_state") != "qualifying" or row.get("person_status") != "proven":
        return None, None
    g = row.get("primary_email_grade")
    if g in ("PUB", "A"):
        return "High", (100 if g == "PUB" else 85)
    if g == "B":
        return "Medium", 60
    phone, li = bool(row.get("firm_phone")), bool(row.get("corporate_linkedin"))
    if phone and li:
        return "Medium", 45
    if phone or li:
        return "Low", 25
    return "Low", 0


def _confidence(row: dict) -> int | None:
    """How well-PROVEN the record is (distinct from reach): affirmed entity (>=2 evidence classes) +
    person proof (Schedule A-anchored, stated > title-inferred) + email proof (published proves the
    address is theirs; inferred does not). A record can be high-confidence but low-reachability
    (e.g. a proven sole owner with no published email)."""
    if row.get("release_state") != "qualifying":
        return None
    entity = 40  # every qualifying FO cleared the >=2 independent-evidence-class bar (ADR-0020)
    person = 40 if row.get("primary_authority_basis") == "stated" else 25
    g = row.get("primary_email_grade")
    email = 20 if g == "PUB" else 10 if g in ("A", "B") else 5
    return min(100, entity + person + email)


def _adv_facts(cur, crd: str) -> dict:
    """Everything gold takes from the firm's ADV capture: location, street, phone, AUM, and the
    filing URL that is the verifiable basis for all of them (data we already hold -- free parity).
    Both registry channels carry the same raw shape; the SEC-feed capture wins where a firm has
    both. (Measured miss: CRD 120053 entered via the state channel only and shipped qualifying
    with NO ADV facts -- empty data_asof/is_stale/AUM -- because this query saw only sec_form_adv.)"""
    cur.execute("select raw->>'city', raw->>'state', raw->>'country', raw->>'street1', "
                "raw->>'street2', raw->>'phone', raw->>'raum_total', source_url, "
                "raw->>'latest_filing_date' "
                "from bronze.captures where source in ('sec_form_adv', 'state_form_adv') "
                "and entity_key=%s "
                "order by case source when 'sec_form_adv' then 0 else 1 end limit 1", (crd,))
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


_BAND_PRECISION: dict | None = None


def band_precision() -> dict:
    """ADR-0034's measured precision, computed once per process from the artifact and cached.

    Cached rather than recomputed per record because it re-runs the gate over the whole calibration
    set; regenerated rather than written down because a hand-carried precision figure is exactly
    the drift the counts-from-the-artifact rule exists to stop."""
    global _BAND_PRECISION
    if _BAND_PRECISION is None:
        _BAND_PRECISION = release_band.measure()
    return _BAND_PRECISION


def _adv_raw(cur, crd: str) -> dict:
    """The raw registry capture, for rules that read regulatory client-mix fields the processed
    _adv_facts view does not carry (ADR-0034's band needs hnw_raum / nonhnw_clients)."""
    cur.execute("select raw from bronze.captures "
                "where source in ('sec_form_adv', 'state_form_adv') and entity_key = %s "
                "order by case source when 'sec_form_adv' then 0 else 1 end, id desc limit 1", (crd,))
    r = cur.fetchone()
    return r[0] if r and r[0] else {}


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


# Categories that may carry the words "family office" as an IDENTITY claim (ADR-0020).
_FO_CATEGORIES = {"single_family_office", "multi_family_office"}
# Everything ADR-0028 counts toward the 500: the two identity categories plus evidenced embedded
# practices. Counted together, reported separately -- "N family offices + M evidenced family-office
# practices" -- and never summed into one number on any surface.
_COUNTED_CATEGORIES = _FO_CATEGORIES | {"embedded_fo_practice"}


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
    out = {"written": write, "firms": 0, "with_primary": 0, "excluded": len(EXCLUDED),
           "by_release": {}, "rows": []}
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
        # ADR-0034: gate affirms that cleared the auto-release band. Only consulted where no human
        # adjudication exists -- the precedence rule (human outranks the gate) is unchanged.
        cur.execute(
            "select distinct on (replace(entity_key,'crd:','')) replace(entity_key,'crd:','') as crd,"
            "       decision, category, score, evidence "
            "  from gold.entity_gate where decision = 'affirm' "
            " order by replace(entity_key,'crd:',''), decided_at desc")
        gate_affirms = {r[0]: {"category": r[2], "score": r[3], "evidence": r[4]}
                        for r in cur.fetchall()}
        # ADR-0037: the operating layer's evidence, joined onto the record it is about. Latest
        # event per (crd, check_type): a later 'noted'/'refreshed' supersedes an earlier 'flagged',
        # so a firm that was flagged and then re-verified reads as current rather than carrying a
        # flag forever.
        # Only evidence gathered by a REAL operating cycle drives a customer-facing flag. Dry runs
        # stay in the ledger -- the submitted logs are uncurated -- but a dry run does not classify
        # materiality, so its events are incomplete by construction and one of them was already
        # surfacing "(dry-run: materiality not classified)" as a buyer-visible warning. Writes from
        # dry runs are now suppressed at source (ADR-0036); this filter covers the rows written
        # before that, without deleting anything from an append-only ledger.
        cur.execute(
            "select distinct on (te.crd, te.check_type) te.crd, te.check_type, te.action, "
            "       te.evidence, te.created_at "
            "  from ops.trust_events te join ops.runs r using (run_id) "
            " where coalesce(r.config->>'write', 'false') = 'true' "
            " order by te.crd, te.check_type, te.created_at desc")
        trust_latest: dict[str, list[dict]] = {}
        for tcrd, ctype, action, evidence, at in cur.fetchall():
            trust_latest.setdefault(tcrd, []).append(
                {"check": ctype, "action": action, "evidence": evidence, "at": at})
        cur.execute("select crd, max(observed_at) from ops.observations group by crd")
        last_seen = {r[0]: r[1] for r in cur.fetchall()}
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
            row["release_basis"] = None
            row["release_basis_detail"] = None
            if (crd, "primary") in cadj:
                row["release_basis"] = "human_ratified"
                _apply_contact(cur, crd, row, cadj, write, rejected_addrs)
                # _COUNTED_CATEGORIES, not _FO_CATEGORIES: ADR-0028 made the evidenced embedded
                # practice a COUNTED category, but this gate still carried the pre-0028 assumption
                # that only SFO/MFO can qualify. Compass cleared both human gates and stayed
                # 'unresolved' anyway -- the third category was unreachable in code. Counted here,
                # still reported on its own surface (family_office_practices.csv) and never summed
                # into the family-office number.
                if row["entity_status"] == "affirmed" and row["entity_category"] in _COUNTED_CATEGORIES:
                    row["release_state"] = "qualifying"
                    standard = "ADR-0020" if row["entity_category"] in _FO_CATEGORIES else "ADR-0028 category 3"
                    row["release_reasons"] = [f"entity affirmed {row['entity_category']} ({standard}); "
                                              f"decision-maker proven (ADR-0021)"]
            elif crd in gate_affirms and adjudications.get(crd) is None:
                # ADR-0034: no human has adjudicated this entity, but the deterministic gate
                # affirmed it AND the affirm cleared the measured auto-release band. It counts on
                # ENTITY evidence alone (ADR-0028 is entity-strict, field-permissive) and says so.
                #
                # It does NOT get a decision-maker. The band establishes what the firm is; nothing
                # in it establishes who allocates, and an extracted-but-unratified name presented
                # as the proven decision-maker is the precise claim-stronger-than-evidence failure
                # the Bridge Mandate corrected. person_status says 'not_established' out loud.
                ga = gate_affirms[crd]
                band = release_band.evaluate(
                    {"adv": _adv_raw(cur, crd)},
                    {"decision": "affirm", "score": ga["score"],
                     "category": ga["category"], "evidence": ga["evidence"] or []})
                if band["released"] and ga["category"] in _COUNTED_CATEGORIES:
                    row["release_state"] = "qualifying"
                    row["entity_category"] = ga["category"]
                    row["entity_status"] = "affirmed"
                    row["release_basis"] = "gate_released"
                    row["release_basis_detail"] = band["basis"]
                    row["category_basis"] = (
                        f"entity established by the automated inclusion gate "
                        f"({gate.GATE_VERSION.split(' (')[0]}), released under "
                        f"{release_band.BAND_VERSION.split(' (')[0]}: {band['basis']}. No human has "
                        f"ratified this entity; the band's category label measured "
                        f"{band_precision()['strict_fo_precision']} correct on the calibration set.")
                    row["release_reasons"] = [
                        f"entity affirmed {ga['category']} by the deterministic gate and cleared "
                        f"the auto-release band (ADR-0034); decision-maker NOT established"]
                    row["person_status"] = "not_established"
                    # No contact ships on a gate-released record, even if extraction found names.
                    for role in ("primary", "secondary"):
                        for f in ("contact_name", "contact_title", "contact_email", "email_grade",
                                  "email_code", "email_explanation"):
                            row[f"{role}_{f}"] = None
                    row["primary_contact_location"] = None
                    row["primary_authority_basis"] = None
                    row["primary_selection_basis"] = None
                else:
                    row["release_reasons"] = [
                        f"gate affirmed {ga['category']} but the affirm did not clear the "
                        f"auto-release band: {band['basis']}; awaiting human adjudication"]
            row["data_completion_score"] = _completion(row)
            # Record-level KPIs (ADR-0013 migration): reachability (reach the DM?), confidence (how
            # well-proven?), and freshness (SEC ADV filing date + a staleness flag when > 15 months,
            # past the annual-filing window). Computed for qualifying FOs; N/A elsewhere.
            row["reachability_tier"], row["reachability_score"] = _reachability(row)
            row["confidence_score"] = _confidence(row)
            # ADR-0037: freshness the system actually measured, as opposed to calendar arithmetic.
            # `is_stale` below stays (it is a genuine signal about the source document's age) but
            # it is no longer the only thing a buyer can read, and it is no longer the thing that
            # carries the word "stale" alone.
            row["last_checked_at"] = last_seen.get(crd)
            flagged = [t for t in trust_latest.get(crd, []) if t["action"] == "flagged"]
            row["trust_state"] = "flagged" if flagged else "current"
            row["trust_reason"] = (
                "; ".join(f"{t['check']}: {t['evidence']}" for t in
                          sorted(flagged, key=lambda t: t["at"], reverse=True)[:2])
                if flagged else None)
            filed = adv.get("latest_filing_date")
            row["data_asof"] = filed
            row["is_stale"] = None
            if filed and row.get("release_state") == "qualifying":
                y, m = (int(x) for x in filed[:7].split("-"))
                today = date.today()  # relative to when THIS build runs, so scheduled rebuilds stay honest
                months = (today.year - y) * 12 + (today.month - m)
                row["is_stale"] = months > 15
            out["firms"] += 1
            if p:
                out["with_primary"] += 1
            # Per-basis counts land in the cycle ledger, so every run records how many records each
            # release basis produced -- the honest way to show the unattended path is doing work.
            k = f"{row['release_state']}:{row.get('release_basis') or 'none'}"
            out["by_release"][k] = out["by_release"].get(k, 0) + 1
            out["rows"].append({"firm": name, "primary": p.get("name"), "title": p.get("title"),
                                "grade": p.get("grade"), "score": row["data_completion_score"],
                                "release": k})
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
