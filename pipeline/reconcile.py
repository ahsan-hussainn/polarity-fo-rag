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
    quar = _rows(QUARANTINE_CSV)
    prod_fo = [r for r in prod if r["Entity Category"] in FO_CATEGORIES]

    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select release_state, count(*) from gold.records group by 1")
        db_state = dict(cur.fetchall())
        cur.execute("select count(*) from gold.records where release_state != 'quarantined'")
        db_shipped = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state = 'quarantined'")
        db_quar = cur.fetchone()[0]
        cur.execute("select count(*) from gold.records where release_state='qualifying'")
        db_qual = cur.fetchone()[0]
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

    # 1. row-count agreement: CSVs vs DB
    check("product CSV rows == DB shipped (non-quarantined)", len(prod) == db_shipped,
          f"CSV {len(prod)} vs DB {db_shipped}")
    check("quarantine CSV rows == DB quarantined", len(quar) == db_quar, f"CSV {len(quar)} vs DB {db_quar}")
    check("total adjudicated == 50", len(prod) + len(quar) == 50, f"{len(prod)}+{len(quar)}")

    # 2. qualifying == affirmed FO with a proven person
    check("qualifying == affirmed FOs (all MFO)", db_qual == db_fo == len(prod_fo),
          f"db_qual {db_qual}, db_fo {db_fo}, csv_fo {len(prod_fo)}")
    check("every qualifying FO has a ratified primary contact", qual_without_contact == 0,
          f"{qual_without_contact} without contact")
    check("every qualifying FO has person_status=proven", qual_unproven_person == 0,
          f"{qual_unproven_person} unproven")

    # 3. suppression: no vendor-rejected/quarantined address in the product CSV
    leaked = [r["Primary Email"] for r in prod for f in ("Primary Email", "Secondary Email")
              if r.get(f, "").strip() and r[f].strip().lower() in audited]
    check("no audited (vendor-rejected) address in product CSV", not leaked, f"leaked: {leaked[:3]}")
    graded_reject = [r for r in prod if r["Primary Email Grade"] in REJECTED_GRADES and r["Primary Email"].strip()]
    check("no D/F-graded address shipped operational", not graded_reject, f"{len(graded_reject)} rows")

    # 4. category honesty: FO count claim vs reality; non-FOs labelled, not counted as FOs
    check("exactly 24 qualifying family offices", len(prod_fo) == 24, f"{len(prod_fo)}")
    non_fo = [r for r in prod if r["Entity Category"] not in FO_CATEGORIES]
    check("18 reclassified non-FOs kept, labelled", len(non_fo) == 18
          and all(r["Entity Category"] in ("wealth_manager", "ria_with_fo_practice") for r in non_fo),
          f"{len(non_fo)} non-FO rows")

    # 5. retrieval corpus agrees: quarantined not retrievable, a qualifying FO is
    from pipeline.rag.retrieve import by_name
    q_names = [r["Firm Name"] for r in quar]
    unretr = all(len(by_name(n.split(",")[0][:18])) == 0 for n in q_names[:4])
    check("sampled quarantined firms are NOT retrievable", unretr, "checked 4")
    check("a qualifying FO IS retrievable", len(by_name("Wellspring")) > 0, "Wellspring")

    # 6. audit-trail size claim
    check("contact_audit holds 28 vendor-rejected addresses", len(audited) == 28, f"{len(audited)}")

    passed = sum(ok for _, ok, _ in checks)
    return {
        "checks": len(checks), "passed": passed, "all_agree": passed == len(checks),
        "surface_counts": {"product_csv": len(prod), "quarantine_csv": len(quar),
                           "db_qualifying": db_qual, "db_states": db_state,
                           "qualifying_family_offices": len(prod_fo), "reclassified_non_fo": len(non_fo),
                           "audited_addresses": len(audited)},
        "failures": [{"check": n, "detail": d} for n, ok, d in checks if not ok],
        "detail": [{"check": n, "ok": ok, "note": d} for n, ok, d in checks],
    }
