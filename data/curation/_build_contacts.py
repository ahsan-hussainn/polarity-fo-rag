"""Assemble ratified contact adjudications (WS3, ADR-0021/0022) from the person-research batches
into the file contact-apply consumes. Evidence is grounded in ADV Schedule A (the regulatory anchor)
+ the firm site/LinkedIn per the affiliation as-of; published_email is the ONLY email claimed for a
person. Ratified by the human release control 2026-07-20 (CEO-as-primary for Marcuard with Gnaegi
noted; Pine Ridge + Pulliam primary-only). Run once.
"""
import glob
import json

DECIDER = "Muhammad Ahsan Hussain (ratified 2026-07-20)"


def adv_url(crd):
    return f"https://reports.adviserinfo.sec.gov/reports/ADV/{crd}/PDF/{crd}.pdf"


def evidence_for(crd, c):
    """Minimal auditable evidence per contact: authority (ADV Schedule A anchor), affiliation
    (dated site/LinkedIn), email (published or honestly none). Full spans live in the research
    transcripts referenced by data/curation/research/ws3/."""
    ev = [
        {"axis": "authority", "source_url": adv_url(crd),
         "observed": f"{c['title']}; authority_basis={c['authority_basis']} "
                     f"(ADV Schedule A owner/officer anchor)"},
        {"axis": "affiliation", "source_url": adv_url(crd),
         "observed": f"current affiliation as of {c['affiliation_asof']}"},
    ]
    if c.get("published_email"):
        ev.append({"axis": "email", "source_url": "firm website (team page)",
                   "observed": f"published individual address {c['published_email']}"})
    else:
        ev.append({"axis": "email", "source_url": "firm website",
                   "observed": "no published individual address; any pattern would be inferred, not claimed"})
    return ev


rows = []
firms = []
for f in sorted(glob.glob("data/curation/research/ws3/batch*.json")):
    firms.extend(json.load(open(f, encoding="utf-8")))
assert len(firms) == 24, f"expected 24 firms, got {len(firms)}"

for fm in firms:
    crd = fm["crd"]
    for role in ("primary", "secondary"):
        c = fm.get(role) or {}
        if not c.get("name"):
            continue  # primary-only firms (Pine Ridge, Pulliam) skip the empty secondary
        sel = c["selection_basis"]
        if crd == "155003" and role == "primary":  # ratified note (Marcuard)
            sel += (" For a private-markets fund pitch specifically, route to Thomas Gnaegi "
                    "(Head of Private Markets, firm-stated; not on Schedule A).")
        rows.append({
            "crd": crd, "contact_role": role, "name": c["name"], "title": c["title"],
            "selection_basis": sel, "authority_basis": c["authority_basis"],
            "affiliation_asof": c["affiliation_asof"], "published_email": c.get("published_email"),
            "evidence": evidence_for(crd, c), "decided_by": DECIDER,
        })

with open("data/curation/contact_adjudications.json", "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1)
prim = sum(1 for r in rows if r["contact_role"] == "primary")
pub = sum(1 for r in rows if r["published_email"])
print(f"wrote {len(rows)} contact rows across {prim} firms; {pub} carry a published email")
