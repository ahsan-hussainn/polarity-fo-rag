"""Validation layer: fill silver.people's contact cells with graded, verified emails (ADR-0005).

This is where "believed" becomes "verified." For each person it takes the firm's domain, runs the
domain-level assessment once (MX + provider + catch-all, cached per domain to stay polite), infers a
work email, SMTP-probes it where the domain is verifiable, and writes back the honest result:
email + pattern + status + a jsonb evidence blob (code, explanation, RCPT codes) + a letter grade.

Scope defaults to principals -- they are the decision-grade contacts the dataset is *for*, and
scoping to them keeps SMTP traffic modest. A catch-all or unconfirmed address is never graded valid
(ADR-0005); the output is an honest confidence distribution, which is the measurable deliverable.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone

import psycopg

from pipeline import db
from pipeline.verify import email as em
from pipeline.verify import smtp


def _connect_retry(attempts: int = 4):
    """Open a DB connection, retrying transient failures (e.g. a DNS blip on the pooler host)."""
    for i in range(attempts):
        try:
            return db.get_conn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))


def _people(scope: str, limit: int | None, only_grade: str | None = None) -> list[tuple]:
    """(person_id, name, firm_crd, firm_name, domain) for the chosen scope. only_grade (a single
    grade letter) restricts to people currently at that grade -- e.g. re-verify just the C's, so an
    API pass does not spend credits reconfirming dead (F) or catch-all (B) domains it cannot improve."""
    conds = []
    if scope == "principals":
        conds.append("p.is_principal")
    if only_grade:
        if only_grade not in ("A", "B", "C", "D", "F"):
            raise ValueError(f"only_grade must be a grade letter, got {only_grade!r}")
        conds.append(f"p.quality_grade = '{only_grade}'")
    where = ("where " + " and ".join(conds)) if conds else ""
    sql = (
        "select p.id, p.name, p.firm_crd, f.firm_name, f.domain "
        "from silver.people p join silver.firms f on f.crd = p.firm_crd "
        f"{where} order by f.domain nulls last, p.id"
    )
    if limit:
        sql += f" limit {int(limit)}"
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def _write(conn, person_id: int, r: em.EmailResolution) -> None:
    verification = {"code": r.code, "explanation": r.explanation,
                    "checked_at": datetime.now(timezone.utc).isoformat(), **r.evidence}
    with conn.cursor() as cur:
        cur.execute(
            "update silver.people set email=%s, email_pattern=%s, email_status=%s,"
            " email_verification=%s::jsonb, quality_grade=%s where id=%s",
            (r.email, r.pattern, r.status, json.dumps(verification, default=str), r.grade, person_id),
        )
        conn.commit()


def run(scope: str = "principals", *, limit: int | None = None, write: bool = False,
        delay: float = 1.0, timeout: float = 8.0, verifier: str | None = None,
        only_grade: str | None = None, max_candidates: int = 3) -> dict:
    """Resolve + grade emails for people in scope. Writes to silver.people only if write=True.
    verifier=None uses SMTP-from-host (free, but blind on anti-harvesting domains); verifier=
    'millionverifier'|'mock' uses the API seam (authoritative valid/invalid -> reachable A/D grades).
    only_grade re-verifies just people at that grade; max_candidates caps API calls per person."""
    people = _people(scope, limit, only_grade)
    vobj = None
    if verifier and verifier != "domain":  # 'domain' = domain-level grading, not an API verifier
        from pipeline.verify import api
        vobj = api.get_verifier(verifier)
    assessments: dict[str, smtp.DomainAssessment] = {}
    grades: Counter = Counter()
    statuses: Counter = Counter()
    rows: list[dict] = []
    write_errors = 0
    # A server that ignores/rejects the FIRST RCPT probe (timeout, greylist, anti-harvest) will do the
    # same for the rest, so cache that verdict per domain and skip re-probing every colleague. Both a
    # speed-up and honest: we do not pretend a per-person confirmation we already know is unavailable.
    blocked: set[str] = set()
    _BLOCKED_CODES = {"UNKNOWN_TEMP", "UNCONFIRMED_REJECTED"}
    conn = _connect_retry() if write else None

    for pid, name, crd, firm_name, domain in people:
        if not domain:
            r = em.EmailResolution(None, None, "no_domain", em.GRADE_F, "INVALID_NO_DOMAIN",
                                   "No firm domain on record; cannot infer an address.", {})
        elif vobj is not None:
            # API path: the verifier handles catch-all + mailbox existence itself, so no SMTP probing.
            r = em.resolve_via_api(name, domain, vobj, max_candidates=max_candidates)
            if delay:
                time.sleep(delay)  # gentle pacing against the API's rate limit
        elif verifier == "domain":
            # Domain-grade path (interim, ADR-0010): one catch-all probe per domain (cached), then
            # grade from it. No per-address probing -> fast, complete, and never falsely "valid".
            if domain not in assessments:
                assessments[domain] = smtp.assess_domain(domain, timeout=timeout)
                if delay:
                    time.sleep(delay)
            r = em.resolve_domain_only(name, domain, assessments[domain])
        elif domain in blocked:
            cands = em.infer_candidates(name, domain)
            pat, email = cands[0] if cands else (None, None)
            r = em.EmailResolution(
                email, pat, "unconfirmed", em.GRADE_C, "UNCONFIRMED_BLOCKED_CACHED",
                "Domain did not usefully answer the first RCPT probe (anti-harvesting/greylisting); "
                "cached to avoid re-probing colleagues. Address inferred, not verified.",
                {"provider": assessments[domain].provider, "domain_blocked_cached": True})
        else:
            if domain not in assessments:
                assessments[domain] = smtp.assess_domain(domain, timeout=timeout)
                if delay:
                    time.sleep(delay)  # politeness between new-domain SMTP probes
            r = em.resolve(name, domain, assessments[domain], timeout=timeout)
            if r.code in _BLOCKED_CODES:
                blocked.add(domain)
        if write:
            try:
                _write(conn, pid, r)
            except (psycopg.OperationalError, psycopg.InterfaceError):
                # transient connection loss -- reconnect once and retry; skip on a second failure so
                # one blip never aborts a long run (already-written rows persist; re-runs are idempotent)
                try:
                    conn = _connect_retry()
                    _write(conn, pid, r)
                except Exception:
                    write_errors += 1
                    continue
        grades[r.grade] += 1
        statuses[r.status] += 1
        rows.append({"person": name, "firm": firm_name, "email": r.email,
                     "grade": r.grade, "code": r.code, "status": r.status})

    if conn is not None:
        conn.close()
    return {
        "scope": scope, "written": write, "people": len(people),
        "domains_probed": len(assessments), "write_errors": write_errors,
        "by_grade": dict(sorted(grades.items())),
        "by_status": dict(sorted(statuses.items())),
        "rows": rows,
    }
