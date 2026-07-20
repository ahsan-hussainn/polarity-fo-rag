# Three records, full validation chain

Three records chosen to span the confidence spectrum after the Bridge Mandate correction pass — a
firm-published contact email (proven), an inferred contact email (honest partial), and a proven
decision-maker with **no** shippable email (honest blank) — because the standard is only credible if
the weak cases are shown too. Every step is reproducible from the named CLI commands and sources.
Reconciled against `data/gold/family_office_dataset.csv`, 2026-07-20.

---

## Record 1 — Custos Family Office (strongest: firm-published contact email)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | SEC Form ADV feed, CRD **294025**; name match "family office" | [ADV filing](https://reports.adviserinfo.sec.gov/reports/ADV/294025/PDF/294025.pdf) |
| **Entity (ADR-0020)** | Affirmed **multi-family office** on 2 independent classes: firm self-description ("we function as our clients' Chief Financial Officer… a bridge across generations", 100% partner-owned) **and** an Altss directory listing ("Austin Multi Family Office"), consistent with an all-HNW-leaning ADV book (46/21) | firm site + altss.com + ADV Item 5 |
| **Decision-maker (ADR-0021/0022)** | Primary **Tony (Anthony M.) Lopiccolo, CFA — Principal & CIO**. Authority `stated`: named CIO **and** ADV Schedule A owner/executive. Selection basis shipped: "named CIO of a small owner-run firm… clearest best-reachable investment decision-maker" | firm team page + [ADV Schedule A](https://reports.adviserinfo.sec.gov/reports/ADV/294025/PDF/294025.pdf) |
| **Email** | `anthony@custosfo.com` — **published on the firm's own team page** (grade **PUB**: proven to be the person's address, source is the firm itself) | custosfo.com team section |
| **Confidence** | **High on every axis.** Entity, person, authority, and email each carry independent evidence; the email is proven to belong to the named CIO. This is the record type the corrected dataset is built around. |

## Record 2 — Wellspring Family Office (proven person, inferred email — the honest partial)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | SEC Form ADV feed, CRD **143112**; name match | [ADV filing](https://reports.adviserinfo.sec.gov/reports/ADV/143112/PDF/143112.pdf) |
| **Entity (ADR-0020)** | Affirmed **multi-family office**: self-identifies "a true multi-family office" **and** BusinessWire rebrand press (Wellspring Financial Advisors → Wellspring Family Office, 2025), predominantly-HNW ADV book (118/21) | wellspringfo.com + businesswire.com |
| **Decision-maker (ADR-0021/0022)** | Primary **Richard (Rich) Turgeon, CFA, CAIA — CIO, Senior Managing Director**. Authority `stated`: named CIO **and** ADV Schedule A officer/owner (10–25%). **Correction to Stage 1**, which led with founder Michael Novak by title rule; Novak is the secondary (Founder/CEO, 25–50% owner) | wellspringfo.com/team + [ADV Schedule A](https://reports.adviserinfo.sec.gov/reports/ADV/143112/PDF/143112.pdf) |
| **Email** | Firm publishes no individual address (only `info@`). The inferred pattern for Turgeon was vendor-verified and graded honestly — **not** presented as verified, and **not** the guessed founder address Stage 1 shipped (`mnovak@…`, which was neither published nor his role) | inferred + MillionVerifier API; `gold.contact_adjudications` |
| **Confidence** | **High on entity + person, partial on email.** The pitch contact is proven; the address is an inferred pattern labeled exactly as such. Reach via the firm line / LinkedIn where the email is unconfirmed. |

## Record 3 — JFG Family Office (proven person, no shippable email — the honest blank)

| Step | What happened | Basis |
|---|---|---|
| **Discovery** | SEC Form ADV feed, CRD **125101**; name match | [ADV filing](https://reports.adviserinfo.sec.gov/reports/ADV/125101/PDF/125101.pdf) |
| **Entity (ADR-0020)** | Affirmed **multi-family office**: "One of the Nation's Premier Integrated Family Offices", history as a single family office serving 154 HNW client families (SmartAsset corroboration) | jfgfamilyoffice.com + smartasset.com |
| **Decision-maker (ADR-0021/0022)** | Primary **Brandon C. Johnson, CFA — CEO & controlling owner** (indirect 50–75% via B&W Holdings, Schedule A control person); secondary **Eric S. Adams — Co-CIO**. De-duplicated from a **58-person** over-extraction down to the two real investment leads | jfgfamilyoffice.com/team + [ADV Schedule A/B](https://reports.adviserinfo.sec.gov/reports/ADV/125101/PDF/125101.pdf) |
| **Email** | The firm publishes no individual address; the inferred pattern (`first.last@jfgfamilyoffice.com`) was **vendor-rejected as undeliverable** for both contacts — so it is **quarantined to `gold.contact_audit` and no email ships**. Outreach routes to the SEC-filed phone | MillionVerifier API (INVALID_API); `gold.contact_audit` |
| **Confidence** | **High on entity + person, zero on email — and stated as zero.** Fabricating a plausible-looking address here would pass a glance and fail a send; the honest blank + phone routing is the product. |

---

**Why these three:** a validation layer is only trustworthy if it can say *no*. Record 1 reaches a
firm-published contact; Record 2 refuses to over-claim an inferred address (and corrects a Stage 1
mis-pick); Record 3 ships no email rather than a guess when the vendor rejects it. The email axis is
deliberately shown at full, partial, and zero confidence — because that is the true state of contact
intelligence, not a uniform "verified."
