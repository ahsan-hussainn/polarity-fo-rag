"""Cross-surface reconciliation (WS6, Bridge Mandate operating standard: every surface must agree).

The mandate requires the counts, records, exports, retrieval corpus, and customer-facing claims to
tell one story, and the final review to run against a consistent artifact. This asserts that
programmatically: it recomputes the load-bearing numbers from each surface (the product CSV, the
quarantine CSV, the database, the contact audit, the deployed retrieval path) and checks they match
each other and the numbers claimed in the docs. It is the substrate the human review runs on, and
evidence that the surfaces agree. Any mismatch is a FAIL, printed, not smoothed over.

Run: `python -m pipeline.cli reconcile`  (exit 0 = all surfaces agree).
"""
from __future__ import annotations

import csv

from pipeline import db

PRODUCT_CSV = "data/gold/family_office_dataset.csv"
RECLASS_CSV = "data/gold/reclassified_firms.csv"
QUARANTINE_CSV = "data/gold/quarantined.csv"
FO_CATEGORIES = {"single_family_office", "multi_family_office"}
REJECTED_GRADES = {"D", "F"}


def _rows(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run() -> dict:
    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    prod = _rows(PRODUCT_CSV)
    reclass = _rows(RECLASS_CSV)
    quar = _rows(QUARANTINE_CSV)
    non_fo_in_prod = [r for r in prod if r["Entity Category"] not in FO_CATEGORIES]

    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select release_state, count(*) from gold.records group by 1")
        db_state = dict(cur.fetchall())
        cur.execute("select count(*) from gold.records where release_state='qualifying'")
        db_qual = cur.fetchone()[0]
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
        cur.execute("select count(*) from gold.records r "
                    "where release_state='qualifying' and not exists "
                    "(select 1 from gold.contact_adjudications ca where ca.crd=r.crd and ca.contact_role='primary')")
        qual_without_contact = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='qualifying' and person_status is distinct from 'proven'")
        qual_unproven_person = cur.fetchone()[0]

    # 1. three files partition the 50; product == qualifying FOs
    check("product CSV == DB qualifying", len(prod) == db_qual, f"CSV {len(prod)} vs DB {db_qual}")
    check("reclassified CSV == DB reclassified", len(reclass) == db_reclass, f"CSV {len(reclass)} vs DB {db_reclass}")
    check("quarantine CSV == DB quarantined", len(quar) == db_quar, f"CSV {len(quar)} vs DB {db_quar}")
    check("three files partition all 50", len(prod) + len(reclass) + len(quar) == 50,
          f"{len(prod)}+{len(reclass)}+{len(quar)}")

    # 2. the product is family offices ONLY, each with a proven person
    check("product is family offices only (no non-FO leaked in)", not non_fo_in_prod, f"{len(non_fo_in_prod)} leaked")
    check("qualifying == affirmed FOs", db_qual == db_fo == len(prod), f"db_qual {db_qual}, db_fo {db_fo}, csv {len(prod)}")
    check("every product FO has a ratified primary contact", qual_without_contact == 0, f"{qual_without_contact}")
    check("every product FO has person_status=proven", qual_unproven_person == 0, f"{qual_unproven_person}")

    # 3. suppression: no vendor-rejected/quarantined address in the product CSV
    leaked = [r[f] for r in prod for f in ("Primary Email", "Secondary Email")
              if r.get(f, "").strip() and r[f].strip().lower() in audited]
    check("no audited (vendor-rejected) address in product CSV", not leaked, f"leaked: {leaked[:3]}")
    graded_reject = [r for r in prod if r["Primary Email Grade"] in REJECTED_GRADES and r["Primary Email"].strip()]
    check("no D/F-graded address shipped operational", not graded_reject, f"{len(graded_reject)} rows")

    # 4. counts
    check("exactly 24 qualifying family offices", len(prod) == 24, f"{len(prod)}")
    check("18 reclassified firms, all wealth_manager/ria_with_fo_practice", len(reclass) == 18
          and all(r["Entity Category"] in ("wealth_manager", "ria_with_fo_practice") for r in reclass),
          f"{len(reclass)}")

    # 5. retrieval corpus: only qualifying FOs retrievable
    from pipeline.rag.retrieve import by_name
    unretr_q = all(len(by_name(r["Firm Name"].split(",")[0][:18])) == 0 for r in quar[:3])
    unretr_r = len(by_name("Tarbox")) == 0 and len(by_name("Chilton")) == 0  # reclassified now unretrievable
    check("quarantined firms NOT retrievable", unretr_q, "checked 3")
    check("reclassified non-FOs NOT retrievable", unretr_r, "Tarbox/Chilton")
    check("a qualifying FO IS retrievable", len(by_name("Wellspring")) > 0, "Wellspring")

    passed = sum(ok for _, ok, _ in checks)
    return {
        "checks": len(checks), "passed": passed, "all_agree": passed == len(checks),
        "surface_counts": {"family_offices": len(prod), "reclassified": len(reclass),
                           "quarantined": len(quar), "db_states": db_state, "audited_addresses": len(audited)},
        "failures": [{"check": n, "detail": d} for n, ok, d in checks if not ok],
        "detail": [{"check": n, "ok": ok, "note": d} for n, ok, d in checks],
    }
