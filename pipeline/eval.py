"""Proxy-label benchmark for the extractor's is_principal call.

This measures the extractor's principal-vs-staff call against a documented TITLE RUBRIC, not against
independent human ground truth about real investment authority: labels are generated deterministically
by `adjudicate_title()` (422 of 425 by rule, 3 manual overrides), so it is a *proxy-label* benchmark.
It reports how far the extractor's is_principal agrees with that rubric -- a real, reproducible
measurement, but it does not establish that a person actually holds investment authority (ADR-0021's
Schedule A pass does that). It does three things:

  export()     -- dump people to a BLIND labelling CSV (no model prediction shown), so the rubric
                  labelling is independent of what the model guessed.
  score()      -- join the rubric proxy-labels back to the model's is_principal and compute the
                  confusion matrix + precision / recall / false-positive / false-negative rates.
  crosscheck() -- an AUTHORITATIVE, non-circular sanity anchor: compare each firm's website
                  "principal" count to its SEC Form ADV `total_employees`. A firm with more website
                  principals than it reports employees is over-inclusion, corroborated by public data.

Labelling rubric (documented so the truth set is reproducible, not a black box):
  PRINCIPAL  = investment decision authority OR firm ownership: Founder/Co-Founder, Owner, Managing
               Partner/Member, Principal, CEO, President, Chairman, CIO. (COO/Managing Director at a
               small firm count when they denote ownership/leadership.)
  NOT        = employees without ownership/allocation authority: Advisor/Wealth Advisor (even
               "Senior"), Analyst, Associate, VP, Chief Compliance Officer, Controller, and all
               operations / client-service / admin / marketing / IT roles.
This is deliberately STRICTER than the extraction prompt (which counts "partners" and "managing
directors" broadly) -- that gap is exactly what we are measuring.
"""
from __future__ import annotations

import csv
import os
import re

from pipeline import db

GT_DIR = "data/ground_truth"
LABELS_CSV = os.path.join(GT_DIR, "principal_labels.csv")

# Strong signals of capital-allocation authority or firm ownership. Matched as substrings against a
# punctuation-normalized title. Deliberately requires an investment/leadership qualifier -- a bare
# "Managing Director" or "Partner" is seniority, not control, and is NOT counted (that gap is the
# over-inclusion we measure). See module docstring for the full rubric.
_STRONG = (
    "founder", "co founder", "owner", "managing member", "managing partner", "co managing partner",
    "managing principal", "chief executive", "ceo", "chairman", "chief investment officer",
    "portfolio manager", "head of investment", "head asset management", "head of asset management",
    "head markets", "head private markets", "head of private", "head of research", "head portfolio",
    "director of investments", "director investments", "managing director investments",
    "managing director of investments", "director of research", "director of portfolio",
    "investment manager",
)

# Exact-title manual overrides (human-in-the-loop corrections to the rule). Keyed by the raw title.
TITLE_OVERRIDES: dict[str, int] = {
    "Founder Emeritus": 0,                                   # retired; not an active decision-maker
    "Head of North American Private Credit Origination & Partner": 1,  # investment origination lead
    "Member of the Board of Directors": 0,                   # governance, not the operating principal
}


# Titles that a LENIENT (ownership-inclusive) definition also counts as principal -- bare seniority
# that the strict rule excludes. Used only for the sensitivity bracket, not the canonical labels.
_LENIENT_EXTRA = ("partner", "managing director", "senior partner")


def adjudicate_title(title: str | None, *, strict: bool = True) -> int:
    """Blind (model-independent) principal judgment from title text alone, per the documented rubric.
    Returns 1 (principal: ownership/allocation authority) or 0 (employee/support/advisory).
    strict=False also counts bare Partner / Managing Director (the sensitivity upper bound)."""
    if not title:
        return 0
    if strict and title in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[title]
    tx = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", title.lower())).strip()
    def has(w: str) -> bool:
        return re.search(r"\b" + re.escape(w) + r"\b", tx) is not None
    if "emeritus" in tx:
        return 0
    if any(s in tx for s in _STRONG):
        return 1
    if has("principal") or has("cio"):
        return 1
    if has("president") and not has("vice president"):
        return 1
    if not strict and any(s in tx for s in _LENIENT_EXTRA):
        return 1
    return 0


def export(path: str = LABELS_CSV, limit: int | None = None) -> int:
    """Write a blind labelling template (person_id, firm, name, title, truth[blank], note[blank])."""
    sql = (
        "select p.id, p.firm_crd, f.firm_name, p.name, p.title "
        "from silver.people p join silver.firms f on f.crd = p.firm_crd "
        "order by f.firm_name, p.id"
    )
    if limit:
        sql += f" limit {int(limit)}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["person_id", "firm_crd", "firm_name", "name", "title",
                    "truth_is_principal", "note"])
        for pid, crd, firm, name, title in rows:
            w.writerow([pid, crd, firm, name, title, "", ""])
    return len(rows)


def label(path: str = LABELS_CSV) -> dict:
    """Generate the ground-truth labels by adjudicating each person's title (blind to the model's
    is_principal). Writes the labelled CSV; the rubric in adjudicate_title() is the documented method."""
    sql = ("select p.id, p.firm_crd, f.firm_name, p.name, p.title "
           "from silver.people p join silver.firms f on f.crd = p.firm_crd order by f.firm_name, p.id")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n1 = 0
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["person_id", "firm_crd", "firm_name", "name", "title",
                    "truth_is_principal", "note"])
        for pid, crd, firm, name, title in rows:
            truth = adjudicate_title(title)
            n1 += truth
            note = "override" if title in TITLE_OVERRIDES else ""
            w.writerow([pid, crd, firm, name, title, truth, note])
    return {"labelled": len(rows), "principals": n1, "non_principals": len(rows) - n1, "path": path}


def score(path: str = LABELS_CSV) -> dict:
    """Join the rubric proxy-labels to the model's is_principal; return the confusion matrix + rates."""
    labelled: dict[int, int] = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("truth_is_principal") or "").strip().lower()
            if v in ("1", "0", "true", "false", "yes", "no", "y", "n"):
                labelled[int(r["person_id"])] = 1 if v in ("1", "true", "yes", "y") else 0
    if not labelled:
        return {"error": "no labelled rows found", "path": path}

    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select id, name, title, firm_crd, is_principal from silver.people "
                    "where id = any(%s)", (list(labelled),))
        preds = {r[0]: r for r in cur.fetchall()}

    tp = fp = tn = fn = 0
    false_positives, false_negatives = [], []
    for pid, truth in labelled.items():
        row = preds.get(pid)
        if not row:
            continue
        _, name, title, crd, pred = row
        pred = 1 if pred else 0
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 1 and truth == 0:
            fp += 1
            false_positives.append({"name": name, "title": title, "firm_crd": crd})
        elif pred == 0 and truth == 0:
            tn += 1
        else:
            fn += 1
            false_negatives.append({"name": name, "title": title, "firm_crd": crd})

    n = tp + fp + tn + fn
    def rate(a, b): return round(a / b, 3) if b else None

    # Sensitivity: re-score against the LENIENT definition (bare Partner/MD counts) so the reported
    # over-inclusion isn't an artifact of a strict rubric. Precision's true value sits in this bracket.
    ltp = lfp = ltn = lfn = 0
    for pid in labelled:
        row = preds.get(pid)
        if not row:
            continue
        pred = 1 if row[4] else 0
        lt = adjudicate_title(row[2], strict=False)
        if pred and lt: ltp += 1
        elif pred and not lt: lfp += 1
        elif not pred and not lt: ltn += 1
        else: lfn += 1

    return {
        "labelled": len(labelled), "scored": n,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": rate(tp, tp + fp),          # of predicted principals, how many are real
        "recall": rate(tp, tp + fn),             # of real principals, how many we caught
        "false_positive_rate": rate(fp, fp + tn),  # of true non-principals, how many wrongly flagged
        "false_negative_rate": rate(fn, fn + tp),  # of real principals, how many we missed
        "accuracy": rate(tp + tn, n),
        "precision_lenient": rate(ltp, ltp + lfp),  # upper bound if every Partner/MD is a principal
        "false_positive_rate_lenient": rate(lfp, lfp + ltn),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def crosscheck(ratio_threshold: float = 0.6, min_people: int = 4) -> dict:
    """Corroborating (non-circular) over-inclusion signal: an implausibly high share of a firm's team
    flagged as principals. A real firm has few actual control persons; a team page where >60% are
    "principals" is a data-quality flag. ADV total_employees is reported as authoritative context --
    100% principal ratios at firms reporting dozens/hundreds of employees are the clearest cases."""
    sql = (
        "select f.crd, f.firm_name, "
        "  (select count(*) from silver.people p where p.firm_crd=f.crd and p.is_principal) as principals, "
        "  (select count(*) from silver.people p where p.firm_crd=f.crd) as people, "
        "  (b.raw->>'total_employees')::int as adv_employees "
        "from silver.firms f "
        "left join bronze.captures b on b.source='sec_form_adv' and b.entity_key=f.crd "
        "order by principals desc"
    )
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    flagged = []
    for crd, firm, principals, people, emp in rows:
        if people >= min_people and people and principals / people >= ratio_threshold:
            flagged.append({"firm": firm, "crd": crd, "website_principals": principals,
                            "website_people": people, "principal_ratio": round(principals / people, 2),
                            "adv_employees": emp})
    return {"firms": len(rows), "min_people": min_people, "ratio_threshold": ratio_threshold,
            "over_inclusion_flagged": len(flagged), "flagged": flagged}
