"""Independent post-generation grounding check (ADR-0023, Bridge Mandate correction #5).

Prompt-only grounding is below the floor: the release decision cannot depend only on the same model
saying its answer is safe. This module is a DETERMINISTIC, model-independent check that runs against
the composed answer and the retrieved records it was allowed to use, and decides whether the answer
may ship. It does not call an LLM -- it checks the text against the evidence with plain string/number
logic, so it cannot be talked out of a failure the way a self-grading model can.

Checks (each a way an answer can be ungrounded or unsafe):
  1. email grounding  -- every email in the answer belongs to a retrieved record (no invented
                         address). BLOCKS release.
  2. suppression      -- no quarantined/vendor-rejected address (gold.contact_audit) appears
                         anywhere. BLOCKS release.
  3. count fidelity   -- if the retrieval carried a dataset total, an explicit count claim that
                         contradicts it is logged as a WARNING (count phrases are regex-detected,
                         too noisy to block on).
  4. category honesty -- a firm that is not a standalone family office (wealth manager, RIA with
                         an FO practice, or an advisory firm with an evidenced embedded FO
                         practice) named in the answer must carry its label; a bare "family
                         office" presentation of one BLOCKS release.
Firm-name grounding from free text is NOT implemented -- firm-name detection in prose is too noisy
to block on. Firm honesty is enforced through the email checks plus the category check above.
Stated here so the control's documented scope matches its code, not more.

Returns a Verdict; answer.py repairs-or-refuses on failure and logs the result, so the control is
visible in real runs (a check that never changes a release has not proved authority).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline import db

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_FO_CATEGORIES = {"single_family_office", "multi_family_office"}
# Category -> the plain label the answer must carry for a firm that is not a standalone FO
# (ADR-0028: embedded_fo_practice qualifies for coverage but is never presented as an FO).
_NON_FO_LABEL = {"wealth_manager": "wealth manager",
                 "ria_with_fo_practice": "RIA with a family-office practice",
                 "embedded_fo_practice": "family-office practice"}


@dataclass
class Verdict:
    ok: bool
    failures: list[str] = field(default_factory=list)   # hard problems that block release
    warnings: list[str] = field(default_factory=list)   # softer signals, logged, do not block


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _quarantined_emails(crds: list[str]) -> set[str]:
    """Vendor-rejected addresses for the retrieved firms -- must never appear in a shipped answer."""
    if not crds:
        return set()
    with db.get_pool().connection() as c, c.cursor() as cur:
        cur.execute("select lower(email) from gold.contact_audit where crd = any(%s)", (crds,))
        return {r[0] for r in cur.fetchall()}


def check(answer_text: str, hits: list[dict], total: int | None = None) -> Verdict:
    """Verify a composed answer against the records it was allowed to use. Pure/deterministic."""
    v = Verdict(ok=True)
    text = answer_text or ""
    low = text.lower()

    # allowed vocabulary from the retrieved records
    allowed_emails = {(_norm(h.get("primary_contact_email")) and (h.get("primary_contact_email") or "").lower())
                      for h in hits}
    allowed_emails |= {(h.get("secondary_contact_email") or "").lower() for h in hits}
    allowed_emails.discard("")
    crds = [h["crd"] for h in hits]

    # 1. email grounding -- every email string in the answer must belong to a retrieved record.
    for em in {m.group(0).lower() for m in _EMAIL_RE.finditer(text)}:
        if em not in allowed_emails:
            v.failures.append(f"answer contains an email not in the retrieved records: {em}")

    # 2. suppression -- a vendor-rejected/quarantined address must not appear on any surface.
    for em in _quarantined_emails(crds):
        if em and em in low:
            v.failures.append(f"answer exposes a quarantined (vendor-rejected) address: {em}")

    # 3. count fidelity -- if a dataset total was provided, a count CLAIM must match it. Only explicit
    #    count phrasings are judged ("N family offices", "there are N", "a total of N") -- never bare
    #    numbers or list markers like "2." which are not counts.
    if total is not None:
        claims = re.findall(r"\b(\d{1,3})\s+(?:\*\*)?(?:family off|multi-family|record|firm|result|match)", low)
        claims += re.findall(r"(?:there are|a total of|count of|found)\s+(?:\*\*)?(\d{1,3})", low)
        for nstr in claims:
            n = int(nstr)
            if n != total:
                v.warnings.append(f"answer states a count of '{n}' but the dataset total is {total}")

    # 4. category honesty -- a firm that is not a standalone FO must not be presented as one.
    #    BLOCKS release: a confidently mislabelled entity is the exact harm ADR-0023 exists to stop,
    #    and the repair path (answer.py names the failure and re-composes) handles it.
    for h in hits:
        cat = h.get("entity_category")
        if cat in _NON_FO_LABEL:
            name_l = _norm(h.get("family_office_name"))
            # if the firm is named AND the answer calls it a family office without the correction label
            if name_l and name_l in _norm(text) and "family office" in low and _NON_FO_LABEL[cat] not in low:
                v.failures.append(f"{h['family_office_name']} is a {_NON_FO_LABEL[cat]}, not a "
                                  f"standalone family office; the answer must label it as such")

    v.ok = not v.failures
    return v
