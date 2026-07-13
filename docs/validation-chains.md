# Three records, full validation chain

Deliverable #3. Three records chosen to span the confidence spectrum — a verified contact (A), a
catch-all inference (B), and an honest blank (F) — because the grading system is only credible if the
low grades are shown too. Every step is reproducible from the CLI commands named.

---

## Record 1 — Wellspring Family Office (A-grade: verified contact)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | SEC Form ADV feed `IA_FIRM_SEC_Feed_07_11_2026`, CRD **143112**; classified `strong` (firm name contains "family office") by `pipeline/bronze/adv.py::classify` | [ADV filing PDF](https://reports.adviserinfo.sec.gov/reports/ADV/143112/PDF/143112.pdf) |
| **Firm facts** | Street/city/state, phone `216-367-0680`, AUM $5.06B taken directly from the ADV capture (bronze row, `source='sec_form_adv'`) | same filing PDF |
| **Extraction** | Site fetched to bronze (home/about/team pages, provenance per page); gpt-4o-mini Structured Outputs extracted thesis, description, sectors, and a 10-person team with per-person `is_principal` + reason | https://wellspringfo.com |
| **Enrichment** | Corporate LinkedIn matched by search, disambiguated on domain, committed to `data/enrichment/corporate_linkedin.json` | https://www.linkedin.com/company/wellspring-family-office |
| **Contact selection** | Michael Novak ranked primary by the documented seniority function (`gold/build.py::principal_rank`: Founder & CEO → 100) | site team page |
| **Email validation** | Patterns inferred (`mnovak@`, `michael.novak@`, …); MillionVerifier API returned `ok` for `mnovak@wellspringfo.com` → grade **A**, code `VERIFIED_API`. The evidence blob in `silver.people.email_verification` records every probed pattern and verdict | API result, re-runnable via `validate-emails --verifier millionverifier` |
| **Confidence** | **High.** Two independent sources agree on the entity (SEC + its own site); the contact email is confirmed deliverable by a third party. This is the record type the dataset is built around. |

## Record 2 — Boston Family Office (B-grade: plausible, honestly unconfirmable)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | Same ADV feed, CRD **107141**, `strong` name match | [ADV filing PDF](https://reports.adviserinfo.sec.gov/reports/ADV/107141/PDF/107141.pdf) |
| **Extraction** | Site → bronze → gpt-4o-mini: thesis, description, 5 sectors, 11-person team (9 model-flagged principals) | https://bosfam.com |
| **Contact selection** | George P. Beal, Managing Partner & Portfolio Manager → primary; Benjamin T. Richardson (CIO) → secondary | site team page |
| **Email validation** | Domain `bosfam.com` is **catch-all** — its server accepts *any* address, so no individual mailbox can be confirmed by anyone. Per the cardinal rule (ADR-0005) the inferred `george.beal@bosfam.com` is graded **B / INFERRED_CATCHALL**: *plausible inference, cannot be confirmed* — never "verified" | API catch-all verdict, recorded in the evidence blob |
| **Confidence** | **Medium.** The person, title, and firm are verified from the firm's own site; the address is the most common corporate pattern on a domain that structurally cannot confirm it. A client should treat it as a best-effort address, and the grade says exactly that. |

## Record 3 — Collective Family Office (F-grade: the honest blank)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | Same ADV feed, CRD **301274**, `strong` name match | [ADV filing PDF](https://reports.adviserinfo.sec.gov/reports/ADV/301274/PDF/301274.pdf) |
| **Extraction** | Site → bronze → gpt-4o-mini: thesis, description, sectors, 4-person team incl. David Sivel (Principal, CEO) and Brian Luster (Principal, CIO) | https://collectivefamilyoffice.com |
| **Email validation** | The domain has **no reachable MX record** — no mail server exists, so *no* email address on this domain can be deliverable. Email cell left **blank**, grade **F / INVALID_NO_MX** | DNS MX lookup, recorded in the evidence blob |
| **Confidence** | **Firm-level high, contact-email zero — and stated as zero.** Fabricating a plausible-looking address here would pass a glance and fail a send; the blank + F grade is the honest product. The named principals and firm facts remain verified and actionable via phone/LinkedIn. |

---

**Why these three:** a validation layer is only trustworthy if it can say *no*. Record 1 shows the
pipeline reaching a confirmed contact; Record 2 shows it refusing to over-claim when confirmation is
structurally impossible; Record 3 shows it preferring an honest blank over a fabricated cell — the
exact behavior the brief marks as pass/fail.
