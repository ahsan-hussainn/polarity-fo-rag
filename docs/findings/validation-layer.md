# Finding: the validation layer — measured accuracy, not asserted

**Date:** 2026-07-12 · **Data:** silver = 59 firms, 425 people (251 model-flagged principals)

"Decision-grade" is a claim about *measured* accuracy. This is the measurement. Two things are graded:
the extractor's **principal vs. staff** call (where we claim to beat the FO-MAX reference), and the
**email** contact cell (where the client schema pairs an address with a validation code + grade). The
point is not to report high numbers — it is to report *honest* ones, with the method exposed so a
reader can check them (`python -m pipeline.cli gt-score` / `gt-crosscheck`).

---

## Part 1 — `is_principal`: a measured false-positive / false-negative rate

### Method (independent, reproducible)

- **Ground truth** is adjudicated from each person's title alone, **blind to the model's prediction**
  (`pipeline/eval.py::adjudicate_title`), against a documented rubric: a principal has capital-allocation
  authority or firm ownership (Founder/Owner/Managing Partner/Principal/CEO/President/Chairman/CIO/
  Portfolio Manager/Head-of-Investments). Bare seniority — plain *Partner*, *Managing Director*, *VP* —
  and all advisory/ops/compliance/admin roles are **not** principals. The rubric is stricter than the
  extraction prompt on purpose; the gap is what we measure.
- Because "principal" is partly definitional, we report a **sensitivity bracket**: the strict rubric
  above, and a **lenient** variant that also counts every *Partner* and *Managing Director*. The true
  value sits between.
- Labels are committed at `data/ground_truth/principal_labels.csv` (425 rows). Scoring joins them to
  the model's `is_principal` in silver.

### Result

| Definition | Truth principals | Precision | Recall | FP rate | FN rate |
|---|---|---|---|---|---|
| **Strict** (decision authority) | 126 | **0.49** | 0.98 | 0.43 | 0.02 |
| **Lenient** (Partner/MD count) | 210 | **0.78** | 0.94 | 0.25 | — |

Confusion (strict): TP 123 · FP 128 · TN 171 · FN 3 · accuracy 0.69.

**The extractor's failure mode is over-inclusion, not omission.** Recall is ~0.98 — it almost never
misses a real principal — but precision is 0.49–0.78: of the 251 people it flags as principals, between
a quarter and a half are not, depending on definition. High recall + low precision is the signature of a
net cast too wide.

### Where the false positives come from (strict FP = 128)

| Title family | FP | Defensible as principal? |
|---|---|---|
| Partner (non-managing) | 46 | definitional — lenient counts these |
| Managing Director (bare) | 28 | definitional — lenient counts these |
| Vice President (VP/SVP/EVP) | 30 | **no** — employee officer rank |
| Advisor / Strategist / Wealth | 17 | **no** — client-facing, not allocators |
| Ops / Compliance / Finance C-suite | 4 | **no** — not investment authority |
| Director/Head (non-investment) + other | 3 | **no** |

The 54 non-definitional rows (VPs, advisors, ops officers) are wrong under **any** reasonable definition
— this is why even the lenient precision is only 0.78. The remaining 74 (Partners, bare MDs) are the
honest gray zone.

### The 3 false negatives

`Director of Research`, `Director, Investments`, `Director of Portfolio Management and Trading` — the
model called these *not* principal; the rubric counts investment-leadership Directors as principals. So
the model is not uniformly loose: it under-calls a few investment leads while over-calling senior
non-investment staff. A useful signal for prompt tuning, not just a number.

### Authoritative corroboration (non-circular)

The FP/FN above compares the model to *our* rubric. An independent anchor comes from SEC Form ADV
`total_employees` (public, not our judgment): **13 of 59 firms flag ≥60% of their listed team as
principals** (`gt-crosscheck`). The clearest cases are large firms where this is impossible on its face —
**Oak Hill Advisors 15/15 principals at a firm reporting 435 employees**, **F L Putnam 12/12 at 160**.
A real firm does not have 70–100% principals; the over-inclusion is corroborated by data we did not label.

### What would change this

The rubric is title-based and cannot see a bio; at large multi-strategy firms a "Managing Director" can
genuinely run capital, which the strict rubric under-credits (hence the bracket). Anchoring truth to ADV
Schedule A (named owners/officers) would replace human adjudication with a registry — the strongest next
step. The measured lever is **precision**: tightening the extraction prompt (exclude bare Partner/MD/VP
unless paired with a control/investment role) should move it toward the lenient bound, and this harness
will measure whether it does.

---

## Part 2 — email verification: an honest confidence distribution

Every principal gets an inferred work address (`pipeline/verify/email.py`) plus a grade: **A** confirmed
deliverable · **B** inferred on a catch-all domain (plausible, unconfirmable) · **C** live domain but
this mailbox unverified · **F** no reachable mail server (dead domain, definitely bad). **A catch-all or
unconfirmed address is never graded valid** — the disqualifying move in the brief.

### Key finding — the "verifiable" ceiling is lower than the domain probe suggested, and SMTP can't clear it

The Stage-1 domain probe found 73% of FO domains "mailbox-verifiable" (they 5xx-reject a *fake* address).
That does **not** mean a *real* address can be confirmed. Verified directly: **Microsoft 365 tenants
5xx-reject every external RCPT probe** — `info@`, `contact@`, `office@` on `flputnam.com` and
`jfgfamilyoffice.com` (mailboxes that certainly exist) all return `550`. M365 is ~half of FO domains, so
**SMTP confirmation from a single host is structurally unavailable** — the wrong tool. This is exactly why
the reference product (FO-MAX, whose schema carries a validation code + explanation + quality grade per
email) uses a verification *API*, not host SMTP.

### What shipped

Two graders were built (ADR-0010): a **domain-level grader** (F/B/C, the credit-free interim) and the
**API-verifier seam** (`pipeline/verify/api.py`, MillionVerifier client + offline mock). Once a funded
key was available, the API pass ran over the live-domain principals, verifying up to three inferred
patterns each and stopping at the first deliverable mailbox. Crucially, the API confirms **M365**
mailboxes that host SMTP cannot (`info@wellspringfo.com` → `ok`), so the A grade is genuinely reached.

### Result — grade distribution over the 251 principals (after the API pass)

| Grade | Meaning | Count | Share |
|---|---|---:|---:|
| A | confirmed deliverable (API `ok`) | 88 | 35% |
| B | catch-all domain — plausible, unconfirmable | 27 | 11% |
| C | API unknown / greylisted — inferred, unconfirmed | 9 | 4% |
| D | every inferred pattern authoritatively invalid | 109 | 43% |
| F | no MX — dead domain, address definitely bad | 18 | 7% |

**88 principals now carry a verified work email** (~438 MillionVerifier credits spent). Of the 42 gold
firms with a team page, **13 lead with a senior principal *and* an A-grade email** — e.g. Wellspring's
Michael Novak (Founder & CEO, `mnovak@wellspringfo.com`), Oak Hill's Glenn August (Founder & CEO,
`gaugust@oakhilladvisors.com`). That is the decision-grade record the reference cannot produce: the
actual founder, with a confirmed address.

The large **D bucket (43%) is an honest finding, not a failure**: for nearly half the principals, none
of the common patterns (`first.last`, `flast`, `first`) is their real address — FO principals use
idiosyncratic addresses — and the API says so authoritatively rather than us presenting a guess as
verified. The 9 A+ (sourced-and-verified) grades were unreachable because these FO sites do not publish
individual principal emails (0 clean site-email→principal matches); inference+verification (A) is the
realistic ceiling, which is exactly how FO-MAX operates too. Better inference (more patterns) or a
sourced-email crawl (`mailto:` from raw HTML) would convert some D's — measurable with this same harness.
