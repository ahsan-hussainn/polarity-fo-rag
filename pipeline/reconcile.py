"""Cross-surface reconciliation (WS6, Bridge Mandate operating standard: every surface must agree).

The mandate requires the counts, records, exports, retrieval corpus, and customer-facing claims to
tell one story, and the final review to run against a consistent artifact. This asserts that
programmatically: it recomputes the load-bearing numbers from each surface (the product CSV, the
quarantine CSV, the database, the contact audit, the deployed retrieval path) and checks they match
each other. It does NOT check prose documents -- the literal-count assertions were removed for
scale-invariance when the set began changing every cycle, so docs must scope their numbers to a
stamped date (the METHODOLOGY.md pattern) rather than rely on this module to catch drift. It is
the substrate the human review runs on, and evidence that the surfaces agree. Any mismatch is a
FAIL, printed, not smoothed over.

Run: `python -m pipeline.cli reconcile`  (exit 0 = all surfaces agree).
"""
from __future__ import annotations

import csv

from pipeline import db

PRODUCT_CSV = "data/gold/family_office_dataset.csv"
PRACTICES_CSV = "data/gold/family_office_practices.csv"
PENDING_CSV = "data/gold/pending_decision_maker.csv"
RECLASS_CSV = "data/gold/reclassified_firms.csv"
QUARANTINE_CSV = "data/gold/quarantined.csv"
FO_CATEGORIES = {"single_family_office", "multi_family_office"}
COUNTED_CATEGORIES = FO_CATEGORIES | {"embedded_fo_practice"}
REJECTED_GRADES = {"D", "F"}


def _rows(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run() -> dict:
    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    prod = _rows(PRODUCT_CSV)
    practices = _rows(PRACTICES_CSV)
    pending = _rows(PENDING_CSV)
    reclass = _rows(RECLASS_CSV)
    quar = _rows(QUARANTINE_CSV)
    non_fo_in_prod = [r for r in prod if r["Entity Category"] not in FO_CATEGORIES]

    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select release_state, count(*) from gold.records group by 1")
        db_state = dict(cur.fetchall())
        db_total = sum(db_state.values())
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and entity_category = any(%s)", (list(FO_CATEGORIES),))
        db_qual = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and entity_category = 'embedded_fo_practice'")
        db_practices = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='unresolved' "
                    "and entity_category = any(%s)", (list(COUNTED_CATEGORIES),))
        db_pending = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='unresolved' "
                    "and entity_category in ('wealth_manager','ria_with_fo_practice')")
        db_reclass = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state = 'quarantined'")
        db_quar = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where entity_category = any(%s) and release_state='qualifying'",
                    (list(FO_CATEGORIES),))
        db_fo = cur.fetchone()[0]
        cur.execute("select lower(email) from gold.contact_audit")
        audited = {r[0] for r in cur.fetchall()}
        # ADR-0034 split the qualifying set by release basis, so the person invariants split too.
        # They do not weaken: each basis must be internally consistent, and a record may not claim
        # one basis while carrying the other's evidence.
        cur.execute("select count(*) from gold.records r "
                    "where release_state='qualifying' and release_basis='human_ratified' "
                    "and not exists (select 1 from gold.contact_adjudications ca "
                    "                where ca.crd=r.crd and ca.contact_role='primary')")
        qual_without_contact = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and release_basis='human_ratified' and person_status is distinct from 'proven'")
        qual_unproven_person = cur.fetchone()[0]
        # A gate-released record must NOT present a decision-maker: the band established the
        # entity, nothing established the person. Contact data on such a row would be an
        # unratified name shipped as proven -- the Bridge Mandate's corrected failure.
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and release_basis='gate_released' and (person_status is distinct from "
                    "'not_established' or primary_contact_name is not null "
                    "or primary_contact_email is not null)")
        gate_released_with_person = cur.fetchone()[0]
        # Every gate-released record must carry the evidence that released it, on the record.
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and release_basis='gate_released' and coalesce(release_basis_detail,'')=''")
        gate_released_no_basis = cur.fetchone()[0]
        # No qualifying record may lack a release basis entirely.
        cur.execute("select count(*) from gold.records where release_state='qualifying' "
                    "and release_basis is null")
        qual_no_basis = cur.fetchone()[0]
        cur.execute("select release_basis, count(*) from gold.records "
                    "where release_state='qualifying' group by 1")
        by_basis = dict(cur.fetchall())
        cur.execute("select count(*) from gold.records where release_state='qualifying' and data_asof is null")
        qual_no_freshness = cur.fetchone()[0]

    # 1. the three exports partition every record the system holds; product == qualifying FOs.
    #    Totals are DERIVED from the database, never hardcoded, so these hold at any dataset size
    #    (the Stage 1 versions asserted the literal numbers 50/24/18, which breaks on the first
    #    record the Stage 2 climb adds -- and a release control that fails on growth teaches
    #    people to ignore it).
    check("product CSV == DB qualifying family offices", len(prod) == db_qual, f"CSV {len(prod)} vs DB {db_qual}")
    check("practices CSV == DB qualifying embedded practices", len(practices) == db_practices,
          f"CSV {len(practices)} vs DB {db_practices}")
    check("pending CSV == DB affirmed-awaiting-decision-maker", len(pending) == db_pending,
          f"CSV {len(pending)} vs DB {db_pending}")
    check("reclassified CSV == DB reclassified", len(reclass) == db_reclass, f"CSV {len(reclass)} vs DB {db_reclass}")
    check("quarantine CSV == DB quarantined", len(quar) == db_quar, f"CSV {len(quar)} vs DB {db_quar}")
    # Stage 2 split this from three surfaces to five. Entity affirmation and decision-maker
    # adjudication are separate human gates, so the climb produces records that clear the first and
    # await the second; and ADR-0028 forbids counting an evidenced practice in the same number as a
    # family office. Both facts are states a buyer can read, so both get their own file. The check
    # itself is unchanged in kind: every held record appears in exactly one surface, totals derived
    # from the database. It caught this gap on scheduled run 20 and failed the run, which is the
    # behaviour that makes it worth keeping.
    check("five exports partition all held records",
          len(prod) + len(practices) + len(pending) + len(reclass) + len(quar) == db_total,
          f"{len(prod)}+{len(practices)}+{len(pending)}+{len(reclass)}+{len(quar)} "
          f"vs DB total {db_total}")

    # 2. the product is family offices ONLY, each with a proven person
    check("product is family offices only (no non-FO leaked in)", not non_fo_in_prod, f"{len(non_fo_in_prod)} leaked")
    check("qualifying == affirmed FOs", db_qual == db_fo == len(prod), f"db_qual {db_qual}, db_fo {db_fo}, csv {len(prod)}")
    check("every human-ratified FO has a ratified primary contact", qual_without_contact == 0,
          f"{qual_without_contact}")
    check("every human-ratified FO has person_status=proven", qual_unproven_person == 0,
          f"{qual_unproven_person}")
    check("no gate-released record presents a decision-maker", gate_released_with_person == 0,
          f"{gate_released_with_person} gate-released rows carry a person")
    check("every gate-released record carries its release evidence", gate_released_no_basis == 0,
          f"{gate_released_no_basis} missing release_basis_detail")
    check("every qualifying record states a release basis", qual_no_basis == 0,
          f"{qual_no_basis} with null release_basis")
    # A record released with no freshness basis cannot participate in staleness tracking at all --
    # CRD 120053 shipped exactly that way (state-channel capture invisible to _adv_facts) and
    # nothing caught it. Now something does.
    check("every qualifying record carries its freshness basis (data_asof)", qual_no_freshness == 0,
          f"{qual_no_freshness} missing")

    # 3. suppression: no vendor-rejected/quarantined address in the product CSV
    leaked = [r[f] for r in prod for f in ("Primary Email", "Secondary Email")
              if r.get(f, "").strip() and r[f].strip().lower() in audited]
    check("no audited (vendor-rejected) address in product CSV", not leaked, f"leaked: {leaked[:3]}")
    graded_reject = [r for r in prod if r["Primary Email Grade"] in REJECTED_GRADES and r["Primary Email"].strip()]
    check("no D/F-graded address shipped operational", not graded_reject, f"{len(graded_reject)} rows")

    # 4. categorical integrity (counts themselves are covered by the derived checks above)
    check("some qualifying family offices exist", len(prod) > 0, f"{len(prod)}")
    check("reclassified are all wealth_manager/ria_with_fo_practice",
          all(r["Entity Category"] in ("wealth_manager", "ria_with_fo_practice") for r in reclass),
          f"{len(reclass)} rows")

    # 5. retrieval corpus: only qualifying FOs retrievable. Probes are SAMPLED from the live
    #    exports (never hardcoded firm names) so the check keeps meaning as the dataset grows.
    from pipeline.rag.retrieve import by_name

    def _probe(row):  # distinctive name prefix, same lookup technique the UI uses
        name = row.get("Family Office Name") or row.get("Firm Name") or ""
        return name.split(",")[0][:18]

    quar_hits = [_probe(r) for r in quar[:3] if len(by_name(_probe(r))) > 0]
    reclass_hits = [_probe(r) for r in reclass[:3] if len(by_name(_probe(r))) > 0]
    prod_miss = [_probe(r) for r in prod[:2] if len(by_name(_probe(r))) == 0]
    check("quarantined firms NOT retrievable", not quar_hits,
          f"sampled {min(3, len(quar))}; hits: {quar_hits}")
    check("reclassified non-FOs NOT retrievable", not reclass_hits,
          f"sampled {min(3, len(reclass))}; hits: {reclass_hits}")
    check("qualifying FOs ARE retrievable", not prod_miss,
          f"sampled {min(2, len(prod))}; misses: {prod_miss}")

    passed = sum(ok for _, ok, _ in checks)
    return {
        "checks": len(checks), "passed": passed, "all_agree": passed == len(checks),
        "surface_counts": {"family_offices": len(prod), "practices": len(practices),
                           "pending_decision_maker": len(pending), "reclassified": len(reclass),
                           "quarantined": len(quar), "db_states": db_state,
                           "qualifying_by_release_basis": by_basis,
                           "audited_addresses": len(audited)},
        "failures": [{"check": n, "detail": d} for n, ok, d in checks if not ok],
        "detail": [{"check": n, "ok": ok, "note": d} for n, ok, d in checks],
    }
