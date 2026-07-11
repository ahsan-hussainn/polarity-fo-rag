"""Domain-level email verifiability: MX lookup, provider detection, and catch-all detection.

This is the domain half of the ADR-0005 verifier. It answers, per domain: can we reach a mail server,
who runs it, and is it "catch-all" (accepts every address, so no mailbox can be confirmed)? Per-address
inference + grading builds on top of this later.

Method: connect to the top-priority MX on port 25, EHLO, MAIL FROM (null sender, the conventional probe),
then RCPT TO a random address that cannot exist. A 2xx to a definitely-fake address means the domain is
catch-all. A 5xx means the server rejects unknown mailboxes, so real addresses on it can be verified.
No message body (DATA) is ever sent.

Known limitation: some providers (notably Microsoft 365) do "deferred rejection" (accept at RCPT, reject
later) or throttle probers, which can make a normal domain *look* catch-all or unknown. We treat this as a
verifiability *ceiling*, and grade conservatively.
"""
from __future__ import annotations
import smtplib
import socket
from dataclasses import dataclass, field
from typing import Optional

import dns.resolver

# Null sender is the standard bounce/verification probe. HELO name is a neutral placeholder.
PROBE_HELO = "mail.polarityiq-research.dev"
FAKE_LOCALPART = "zq7x9-nouser-4821b3"

# MX hostname substring -> provider label
_PROVIDER_SIGNS = [
    ("microsoft365", ("protection.outlook.com", "mail.protection.outlook.com", "outlook.com")),
    ("google", ("google.com", "googlemail.com", "aspmx.l.google.com")),
    ("proofpoint", ("pphosted.com", "ppe-hosted.com")),
    ("mimecast", ("mimecast.com",)),
    ("barracuda", ("barracudanetworks.com", "cudamail.com")),
    ("zoho", ("zoho.com", "zohomail.com")),
    ("cisco_ironport", ("iphmx.com",)),
    ("amazon_ses", ("amazonaws.com",)),
]


@dataclass
class DomainAssessment:
    domain: str
    mx_ok: bool
    mx_host: Optional[str] = None
    provider: str = "other"
    catch_all: Optional[bool] = None   # True / False / None(unknown)
    rcpt_code: Optional[int] = None
    note: str = ""
    mx_hosts: list = field(default_factory=list)


def mx_lookup(domain: str, timeout: float = 8.0) -> list[tuple[int, str]]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    try:
        ans = resolver.resolve(domain, "MX")
        return sorted((r.preference, str(r.exchange).rstrip(".").lower()) for r in ans)
    except Exception:
        return []


def provider_of(mx_hosts: list[str]) -> str:
    joined = " ".join(mx_hosts).lower()
    for label, signs in _PROVIDER_SIGNS:
        if any(s in joined for s in signs):
            return label
    return "other"


def probe_catch_all(mx_host: str, domain: str, timeout: float = 8.0):
    """Return (catch_all: Optional[bool], rcpt_code: Optional[int], note)."""
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host, 25)
        server.ehlo_or_helo_if_needed()
        server.docmd("MAIL FROM:", "<>")
        code, msg = server.docmd("RCPT TO:", f"<{FAKE_LOCALPART}@{domain}>")
        try:
            server.quit()
        except Exception:
            pass
        if 200 <= code < 300:
            return True, code, "fake address accepted -> catch-all"
        if 500 <= code < 600:
            return False, code, "fake address rejected -> mailbox-level verification possible"
        return None, code, f"ambiguous ({code}) -> greylist/throttle/unknown"
    except (socket.timeout, TimeoutError):
        return None, None, "timeout"
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as e:
        return None, None, f"conn error: {type(e).__name__}"
    except Exception as e:
        return None, None, f"error: {type(e).__name__}: {e}"


def assess_domain(domain: str, timeout: float = 8.0) -> DomainAssessment:
    mx = mx_lookup(domain, timeout=timeout)
    if not mx:
        return DomainAssessment(domain=domain, mx_ok=False, note="no MX record")
    hosts = [h for _, h in mx]
    top = hosts[0]
    provider = provider_of(hosts)
    catch_all, code, note = probe_catch_all(top, domain, timeout=timeout)
    return DomainAssessment(
        domain=domain, mx_ok=True, mx_host=top, provider=provider,
        catch_all=catch_all, rcpt_code=code, note=note, mx_hosts=hosts,
    )
