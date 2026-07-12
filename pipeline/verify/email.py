"""Per-address email inference + SMTP verification + honest grading (ADR-0005).

This is the per-address half that `smtp.py` left as "builds on top of this later." Given a person's
name and their firm's domain (plus the domain-level `DomainAssessment` from smtp.py), it:

  1. infers candidate work-email addresses from common corporate name patterns;
  2. on a mailbox-verifiable domain, SMTP RCPT-probes those candidates (no DATA sent) and takes the
     first the server accepts -- a *confirmed* mailbox;
  3. grades the result on two axes (inference confidence x verification), collapsed to a letter grade
     + a machine code + a plain-English explanation, mirroring the FO-MAX validation chain.

The cardinal rule from the brief (ADR-0005): a catch-all or unconfirmed address is NEVER graded
"valid." An honest "inferred, unconfirmed (B)" beats a fabricated "verified." Every result carries its
evidence (which patterns were probed, the RCPT codes) so the judgment is auditable, not a black box.
"""
from __future__ import annotations

import re
import smtplib
import socket
import unicodedata
from dataclasses import dataclass, field

from pipeline.verify.smtp import DomainAssessment

# Suffixes / credential tokens that are not part of a name's first/last for email purposes.
_DROP_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v", "phd", "cfa", "cpa", "esq", "mba", "dr", "mr",
                "mrs", "ms", "cfp", "jd", "md"}

# Grade table (ADR-0005). letter, code -> explanation is built per-result.
GRADE_A_PLUS = "A+"   # VERIFIED_SOURCED  -- address published on site AND SMTP-confirmed
GRADE_A = "A"         # VERIFIED_SMTP     -- pattern-inferred AND SMTP-confirmed
GRADE_B = "B"         # INFERRED_CATCHALL -- plausible pattern, domain catch-all (unconfirmable)
GRADE_C = "C"         # UNKNOWN_TEMP      -- server ambiguous (greylist/throttle/timeout)
GRADE_D = "D"         # RISKY -- reserved for an AUTHORITATIVE invalid verdict (API verifier); SMTP
                      # pattern-probing can't prove undeliverable (anti-harvesting), so it never emits D
GRADE_F = "F"         # INVALID_NO_MX     -- no reachable mail server


@dataclass
class EmailResolution:
    email: str | None            # best address (believed); None only when no MX
    pattern: str | None          # which name pattern it uses, e.g. 'first.last'
    status: str                  # 'valid'|'catch_all'|'undeliverable'|'unknown'|'no_mx'
    grade: str                   # letter grade above
    code: str                    # machine code (VERIFIED_SMTP, INFERRED_CATCHALL, ...)
    explanation: str             # plain-English, for the graded deliverable
    evidence: dict = field(default_factory=dict)  # mx_host, provider, catch_all, probed codes


def _ascii(s: str) -> str:
    """Fold accents to ASCII (José -> Jose) so inferred localparts are mail-safe."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def name_parts(name: str) -> tuple[str | None, str | None]:
    """(first, last) as clean lowercase alpha tokens; drops titles/suffixes/credentials/initials."""
    # Credentials and suffixes almost always follow a comma ("Dylan Brix, CFA, CTFA" / "Putnam, III"),
    # so cut at the first comma; and drop parenthetical/quoted nicknames ("Eliza (Happy) Rowe").
    base = re.sub(r"\([^)]*\)", " ", name.split(",")[0])
    # Join apostrophes/hyphens rather than split them (O'Brien -> obrien, Anne-Marie -> annemarie),
    # matching how those names become email localparts; other punctuation becomes a token break.
    folded = re.sub(r"[’'\"“”\-]", "", _ascii(base).lower())
    toks = [t for t in re.split(r"[\s]+", re.sub(r"[^a-z\s]", " ", folded)) if t]
    toks = [t for t in toks if t not in _DROP_TOKENS]
    # drop single-letter middle initials but keep a genuinely single-token name
    if len(toks) > 1:
        toks = [toks[0]] + [t for t in toks[1:] if len(t) > 1]
    if not toks:
        return None, None
    if len(toks) == 1:
        return toks[0], None
    return toks[0], toks[-1]


def infer_candidates(name: str, domain: str) -> list[tuple[str, str]]:
    """Ordered (pattern_name, email) candidates, most-common corporate patterns first."""
    first, last = name_parts(name)
    if not first:
        return []
    fi = first[0]
    if not last:
        return [("first", f"{first}@{domain}")]
    specs = [
        ("first.last", f"{first}.{last}"),
        ("flast",      f"{fi}{last}"),
        ("firstlast",  f"{first}{last}"),
        ("first",      f"{first}"),
        ("first_last", f"{first}_{last}"),
        ("f.last",     f"{fi}.{last}"),
        ("lastf",      f"{last}{fi}"),
    ]
    return [(pat, f"{lp}@{domain}") for pat, lp in specs]


def resolve_domain_only(name: str, domain: str, assessment: DomainAssessment) -> EmailResolution:
    """Grade from the DOMAIN assessment alone -- no per-address probing (fast, complete, honest).
    This is the interim path while API credits (ADR-0010) are pending: it never reaches A (no mailbox
    is confirmed), but it gives every principal a real, defensible grade. F = dead domain (definitely
    bad), B = catch-all (plausible, unconfirmable), C = live domain, this mailbox not verified."""
    candidates = infer_candidates(name, domain)
    pat, email = (candidates[0] if candidates else (None, None))
    ev = {"mx_host": assessment.mx_host, "provider": assessment.provider,
          "catch_all": assessment.catch_all, "grade_basis": "domain_only"}
    if not assessment.mx_ok:
        return EmailResolution(None, None, "no_mx", GRADE_F, "INVALID_NO_MX",
                               "Domain has no reachable mail server (MX); no address is possible.", ev)
    if assessment.catch_all is True:
        return EmailResolution(email, pat, "catch_all", GRADE_B, "INFERRED_CATCHALL",
                               "Domain is catch-all (accepts any address); address is a plausible "
                               "inference that cannot be confirmed.", ev)
    return EmailResolution(email, pat, "unconfirmed", GRADE_C, "DOMAIN_LIVE_UNVERIFIED",
                           "Domain is live and accepts mail, but this specific mailbox was not verified "
                           "(domain-level grade only). API verification is needed to reach A.", ev)


def resolve_via_api(name: str, domain: str, verifier, *, max_candidates: int = 4) -> EmailResolution:
    """Infer candidate addresses and confirm them with an API verifier (ADR-0010). Unlike SMTP-from-
    host, the API can authoritatively return valid (A) and invalid (D). Verifies patterns in order and
    stops at the first deliverable mailbox (or a catch-all verdict). Never marks catch-all/unknown valid."""
    candidates = infer_candidates(name, domain)
    if not candidates:
        return EmailResolution(None, None, "no_name", GRADE_F, "INVALID_NO_NAME",
                               "Could not parse a first/last name to infer an address.", {})
    default_pat, default_email = candidates[0]
    probed: list[tuple[str, str]] = []
    for pat, email in candidates[:max_candidates]:
        v = verifier.verify(email)
        probed.append((email, v.result))
        ev = {"verifier": getattr(verifier, "name", "?"), "probed": probed, "quality": v.quality}
        if v.result == "ok":  # authoritative: this mailbox is deliverable
            return EmailResolution(email, pat, "valid", GRADE_A, "VERIFIED_API",
                                   "Address confirmed deliverable by the verification API.", ev)
        if v.result == "catch_all":  # domain accepts everything -> cannot confirm a person; never valid
            return EmailResolution(default_email, default_pat, "catch_all", GRADE_B, "INFERRED_CATCHALL",
                                   "Domain is catch-all (accepts any address); address is a plausible "
                                   "inference the API cannot confirm.", ev)
        if v.result == "disposable":
            return EmailResolution(email, pat, "disposable", GRADE_D, "RISKY_DISPOSABLE",
                                   "Address is on a disposable/temporary-mail domain.", ev)
        # 'invalid' / 'unknown' / 'error' -> try the next pattern
    ev = {"verifier": getattr(verifier, "name", "?"), "probed": probed}
    if probed and all(r == "invalid" for _, r in probed):  # API authoritatively rejected every pattern
        return EmailResolution(default_email, default_pat, "undeliverable", GRADE_D, "INVALID_API",
                               "The API confirmed every inferred pattern is undeliverable; this person's "
                               "real address is not one of the common patterns.", ev)
    return EmailResolution(default_email, default_pat, "unknown", GRADE_C, "UNKNOWN_API",
                           "API could not confirm any inferred pattern (unknown/greylisted); address "
                           "inferred, not verified.", ev)


def probe_addresses(mx_host: str, emails: list[str], timeout: float = 8.0
                    ) -> list[tuple[str, int | None, bool | None]]:
    """RCPT-probe candidates on ONE connection (polite). Stops at the first accepted address.
    Returns [(email, rcpt_code, verdict)] where verdict True=accepted, False=rejected, None=ambiguous."""
    results: list[tuple[str, int | None, bool | None]] = []
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host, 25)
        server.ehlo_or_helo_if_needed()
        server.docmd("MAIL FROM:", "<>")
        for email in emails:
            try:
                code, _ = server.docmd("RCPT TO:", f"<{email}>")
            except Exception:
                results.append((email, None, None))
                break
            verdict = True if 200 <= code < 300 else (False if 500 <= code < 600 else None)
            results.append((email, code, verdict))
            if verdict is True:
                break
        try:
            server.quit()
        except Exception:
            pass
    except (socket.timeout, TimeoutError, smtplib.SMTPException, OSError):
        pass
    return results


def resolve(name: str, domain: str, assessment: DomainAssessment, *,
            sourced_email: str | None = None, timeout: float = 8.0,
            max_candidates: int = 5) -> EmailResolution:
    """Infer + (where possible) verify a person's work email, then grade honestly (ADR-0005)."""
    candidates = infer_candidates(name, domain)
    ev = {"mx_host": assessment.mx_host, "provider": assessment.provider,
          "catch_all": assessment.catch_all, "sourced": bool(sourced_email)}

    # F -- no reachable mail server: nothing to infer against.
    if not assessment.mx_ok:
        return EmailResolution(None, None, "no_mx", GRADE_F, "INVALID_NO_MX",
                               "Domain has no reachable mail server (MX); no address is possible.", ev)

    default_pat, default_email = (candidates[0] if candidates else (None, None))
    if sourced_email:  # a real address lifted from the site outranks any pattern guess
        default_pat, default_email = "sourced", sourced_email

    # B -- catch-all domain accepts every address, so no mailbox can be confirmed. Never "valid."
    if assessment.catch_all is True:
        return EmailResolution(
            default_email, default_pat, "catch_all", GRADE_B, "INFERRED_CATCHALL",
            "Domain is catch-all (accepts any address), so this mailbox cannot be confirmed; "
            "address is a plausible inference, not verified.", ev)

    # C -- domain-level catch-all probe was itself ambiguous (greylist/throttle): don't trust probes.
    if assessment.catch_all is None:
        return EmailResolution(
            default_email, default_pat, "unknown", GRADE_C, "UNKNOWN_TEMP",
            "Mail server gave an ambiguous response (greylisting/throttling); address inferred but "
            "not confirmed.", ev)

    # Microsoft 365 tenants 5xx-reject EVERY external RCPT probe (verified empirically: even info@ /
    # contact@ return 550), so per-address probing is load without signal. Grade unconfirmed directly
    # rather than hammer the server and then mislabel a valid mailbox "undeliverable" (ADR-0005).
    if assessment.provider == "microsoft365":
        return EmailResolution(
            default_email, default_pat, "unconfirmed", GRADE_C, "UNCONFIRMED_M365",
            "Microsoft 365 rejects all external RCPT probes (anti-harvesting), so no address can be "
            "SMTP-confirmed from this host; address is inferred, not verified.", ev)

    # Other verifiable domains (reject fake addresses): probe the candidate patterns for a real mailbox.
    probed = probe_addresses(assessment.mx_host, [e for _, e in candidates[:max_candidates]], timeout)
    ev["probed"] = [(e, c) for e, c, _ in probed]
    hit = next(((e, v) for (e, c, v) in probed if v is True), None)
    if hit:
        email = hit[0]
        pat = next((p for p, ce in candidates if ce == email), default_pat)
        if sourced_email and email.lower() == sourced_email.lower():
            return EmailResolution(email, "sourced", "valid", GRADE_A_PLUS, "VERIFIED_SOURCED",
                                   "Address published on the firm site and confirmed by SMTP RCPT.", ev)
        return EmailResolution(email, pat, "valid", GRADE_A, "VERIFIED_SMTP",
                               "Mailbox confirmed by SMTP RCPT (server accepts it and rejects fakes).", ev)
    if probed and all(v is False for _, _, v in probed):
        # Every candidate rejected -- INCLUDING plausible patterns. We cannot honestly distinguish
        # "all our guesses were wrong" from an anti-harvesting server that 5xx-rejects every unknown
        # RCPT (common on M365; ADR-0005's verifiability ceiling). Claiming "undeliverable" would
        # overstate certainty, so we grade it unconfirmed, not risky.
        return EmailResolution(default_email, default_pat, "unconfirmed", GRADE_C, "UNCONFIRMED_REJECTED",
                               "Server rejected all probed patterns; consistent with anti-harvesting "
                               "(rejects unknown recipients wholesale), so no address can be confirmed "
                               "here. Address is inferred, not verified.", ev)
    return EmailResolution(default_email, default_pat, "unknown", GRADE_C, "UNKNOWN_TEMP",
                           "SMTP probing was inconclusive (timeout/ambiguous codes); address inferred "
                           "but not confirmed.", ev)
