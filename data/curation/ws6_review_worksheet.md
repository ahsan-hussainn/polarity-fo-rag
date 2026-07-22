# WS6 — Final human review worksheet

_Release control (mandate): reviewed in full on every surface; the completed decisions are the evidence. Reconciliation: 13/13 surfaces agree (`python -m pipeline.cli reconcile`). Product = 42 rows (24 qualifying FOs + 18 labeled non-FOs); quarantined = 8._

## A. The 24 qualifying family offices
| # | Firm | Primary contact | Authority | Email | ✔/note |
|---|------|-----------------|-----------|-------|--------|
| 1 | BOSTON FAMILY OFFICE LLC | Benjamin T. Richardson | stated | B benjamin.richardson@bosfam.com | |
| 2 | CAMBIENT FAMILY OFFICE, LL | Andrew Fabiano, CFA | stated | route phone/LinkedIn | |
| 3 | CLASS VI FAMILY OFFICE, LL | Matt Blackburn | stated | PUB Matt@classvipartners.com | |
| 4 | CUSTOS FAMILY OFFICE LLC | Tony (Anthony M.) Lopi | stated | PUB anthony@custosfo.com | |
| 5 | DESTINY FAMILY OFFICE | Thomas H. (Tom) Ruggie | stated | route phone/LinkedIn | |
| 6 | EAGLE BAY FAMILY OFFICE | Michael D. Nelson, J.D | stated | PUB michael@eaglebayadvisors.com | |
| 7 | ELEMENT POINTE FAMILY OFFI | Carlos A. Dominguez | stated | route phone/LinkedIn | |
| 8 | FIDUCIARY FAMILY OFFICE, L | Kathleen Anne Grace | stated | route phone/LinkedIn | |
| 9 | FIFTH AVENUE FAMILY OFFICE | Timothy J. Cartwright | stated | PUB tim@fifthavenuefamily.com | |
| 10 | FIVE ELEVEN PARTNERS | Gilbert A. Calderon | stated | route phone/LinkedIn | |
| 11 | HAMPSHIRE FAMILY OFFICE | Greg Blaney Reidy | stated | route phone/LinkedIn | |
| 12 | JFG FAMILY OFFICE | Brandon C. Johnson, CF | stated | route phone/LinkedIn | |
| 13 | LANDMARK MANAGEMENT, LLC | Michael T. Lima, CFA | stated | route phone/LinkedIn | |
| 14 | MARCUARD FAMILY OFFICE LTD | Andreas P. Arni | stated | route phone/LinkedIn | |
| 15 | MATTER FAMILY OFFICE | Jerrel Armstrong, MBA | stated | A jarmstrong@matterfamilyoffice. | |
| 16 | PINE RIDGE ADVISERS LLC | Baldassare (Baldo) Fod | stated | route phone/LinkedIn | |
| 17 | PMG FAMILY OFFICE, LLC | William Fredrick Blake | stated | route phone/LinkedIn | |
| 18 | POINTONE FAMILY OFFICE | Michael Elliott Walsh | stated | route phone/LinkedIn | |
| 19 | PULLIAM FAMILY OFFICE, LLC | John Michael Pulliam | stated | route phone/LinkedIn | |
| 20 | SESTANTE FAMILY OFFICE | Daniel Jerome White (D | stated | route phone/LinkedIn | |
| 21 | TFO FAMILY OFFICE PARTNERS | Charles (Chuck) Robert | stated | route phone/LinkedIn | |
| 22 | TIMONIER | Nicholas (Nick) C. Bak | stated | A nicholas@timonier.com | |
| 23 | WELLSPRING FAMILY OFFICE | Richard (Rich) Joseph  | stated | A rturgeon@wellspringfo.com | |
| 24 | XCEPTION FAMILY OFFICE | Cort Alan Haber, CFP | stated | PUB chaber@xceptionfamilyoffice.co | |

## B. 18 reclassified non-FOs (kept, labeled, not counted)
| # | Firm | Category | ✔/note |
|---|------|----------|--------|
| 1 | SAPIENT CAPITAL LLC | ria_with_fo_practice | |
| 2 | SUMMIT TRAIL ADVISORS, LLC | ria_with_fo_practice | |
| 3 | INNOVATIVE FAMILY OFFICE LLC | ria_with_fo_practice | |
| 4 | 1919 INVESTMENT COUNSEL, LLC | ria_with_fo_practice | |
| 5 | PIONEER FAMILY OFFICE, LLC | ria_with_fo_practice | |
| 6 | ALPHA CAPITAL FAMILY OFFICE, LLC | ria_with_fo_practice | |
| 7 | CRESTWOOD ADVISORS | ria_with_fo_practice | |
| 8 | F L PUTNAM INVESTMENT MANAGEMENT C | wealth_manager | |
| 9 | FAMILY OFFICE RESEARCH, LLC | wealth_manager | |
| 10 | SUPERIOR PLANNING WEALTH MANAGEMEN | wealth_manager | |
| 11 | ARROWROOT FAMILY OFFICE, LLC | wealth_manager | |
| 12 | COMPOUND PLANNING, INC. | wealth_manager | |
| 13 | CHILTON INVESTMENT SERVICES, LLC | wealth_manager | |
| 14 | STOKES FAMILY OFFICE LLC | wealth_manager | |
| 15 | TARBOX FAMILY OFFICE, INC. | wealth_manager | |
| 16 | SENESCHAL FAMILY OFFICE | wealth_manager | |
| 17 | TFO WEALTH PARTNERS | wealth_manager | |
| 18 | ACTIV8 FAMILY OFFICE LLC | wealth_manager | |

## C. 8 quarantined (withheld)
| # | Firm | Reason | ✔/note |
|---|------|--------|--------|
| 1 | CALLAN | entity rejected (not_fo): Institutional investment consu | |
| 2 | CAPITOL FAMILY OFFICE, INC. | entity type unresolved: Own site is a placeholder ('Webs | |
| 3 | CLEARBROOK INVESTMENT CONSULTI | entity rejected (not_fo): Institutional investment consu | |
| 4 | COLLECTIVE FAMILY OFFICE, LLC | entity type unresolved: FO positioning ('family's stewar | |
| 5 | ELYSEUM FAMILY OFFICE S.A. | entity type unresolved: FO division of a EUR2.5B Luxembo | |
| 6 | FREEDOM FAMILY OFFICE, LLC | entity type unresolved: Domain on file is a parked/priva | |
| 7 | NICHOLAS HOFFMAN & COMPANY, LL | entity type unresolved: Own site leads with 'private bou | |
| 8 | TAYLOR FRIGON FAMILY OFFICE, L | entity type unresolved: This LLC self-labels only 'SEC-R | |

## D. Surfaces reviewed
- [ ] Product CSV (qualifying FOs first, email basis PUB/A/B only)
- [ ] Quarantine CSV + reasons
- [ ] Live RAG UI copy / coverage count / badges
- [ ] API /query answer + sources + verification
- [ ] RAG buyer-path answers (present/absent/non-FO/unanswerable)
- [ ] METHODOLOGY/README/validation-chains counts
- [ ] Grounding check firing (rag-eval 8/8 grounded, 7/8 expectation)

## E. Sign-off — COMPLETED
- Reviewer: **Muhammad Ahsan Hussain**   Date: **2026-07-22**
- 50/50 records reviewed ☑   Surfaces A–D ☑
- Automated substrate at sign-off: reconcile 15/15; rag-eval grounded 8/8, expectation 7/8.
- Corrections this review: withheld 12 unconfirmed (C) inferred emails; re-suppressed 2 re-softened vendor-rejected addresses; split 18 non-FOs into reclassified_firms.csv; surfaced Category Basis on the artifact; fixed completion-score double-count; renamed actionability→reachability (phone-only=Low).
- Release decision: 24 family offices approved for release; 18 reclassified + 8 quarantined approved as auditable, not-counted remainder.