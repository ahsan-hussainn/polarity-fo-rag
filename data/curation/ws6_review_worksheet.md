# WS6 — Final human review worksheet

_The mandate makes this review the release control: for the original 50 records it must be done in full, on every surface, and the completed decisions are the evidence. Mark each row **OK** or note a correction. Nothing here is claimed 'reviewed' until you have signed it._

**Reconciliation:** all 13 cross-surface checks pass (`python -m pipeline.cli reconcile`). Product = 42 rows (24 qualifying FOs + 18 labeled non-FOs); quarantined = 8.

## A. The 24 qualifying family offices — review each (entity, contact, authority, email)

| # | Firm | Primary contact | Authority | Email basis | Why-this-contact (shipped) | ✔/note |
|---|------|-----------------|-----------|-------------|----------------------------|--------|
| 1 | BOSTON FAMILY OFFICE LLC | Benjamin T. Richardson | stated | B benjamin.richardson@bosfam | Named CIO overseeing investment strategy/asset allocation AND Schedule | |
| 2 | CAMBIENT FAMILY OFFICE, LL | Andrew Fabiano, CFA | stated | C andrew.fabiano@cambient.co | Bio states he oversees investment strategy, asset allocation and manag | |
| 3 | CLASS VI FAMILY OFFICE, LL | Matt Blackburn | stated | PUB Matt@classvipartners.com | Runs the FO day-to-day, 'actively involved in investment strategy, ass | |
| 4 | CUSTOS FAMILY OFFICE LLC | Tony (Anthony M.) Lopi | stated | PUB anthony@custosfo.com | Named CIO of a small owner-run firm, Schedule A owner/executive, with  | |
| 5 | DESTINY FAMILY OFFICE | Thomas H. (Tom) Ruggie | stated | C thomas.ruggie@destinyfamil | Controlling owner-principal (revocable trust 75%+, sole Schedule A con | |
| 6 | EAGLE BAY FAMILY OFFICE | Michael D. Nelson, J.D | stated | PUB michael@eaglebayadvisors.c | Owner-principal (Schedule A code D 50-75%, control) and CEO; the only  | |
| 7 | ELEMENT POINTE FAMILY OFFI | Carlos A. Dominguez | stated | C carlos.dominguez@elementpo | Named CIO (allocation, manager selection, risk) AND co-founding owner- | |
| 8 | FIDUCIARY FAMILY OFFICE, L | Kathleen Anne Grace | stated | - (none) | Triple authority - majority owner (Schedule A code D 50-75%, control), | |
| 9 | FIFTH AVENUE FAMILY OFFICE | Timothy J. Cartwright | stated | PUB tim@fifthavenuefamily.com | Co-owner (Schedule A code D, 50-75%, control person); firm's explicit  | |
| 10 | FIVE ELEVEN PARTNERS | Gilbert A. Calderon | stated | C gilbert.calderon@five11par | Named CIO on both firm site and ADV Schedule A - the family office's i | |
| 11 | HAMPSHIRE FAMILY OFFICE | Greg Blaney Reidy | stated | C greg.reidy@hampshirefamily | Sole Schedule A owner (code E, 75%+, control) - the single owner-princ | |
| 12 | JFG FAMILY OFFICE | Brandon C. Johnson, CF | stated | - (none) | CEO and controlling owner (indirect 50-75% via B&W Holdings LLC), publ | |
| 13 | LANDMARK MANAGEMENT, LLC | Michael T. Lima, CFA | stated | C michael.lima@landmark-mgmt | Leads manager research, due diligence, and other investment activities | |
| 14 | MARCUARD FAMILY OFFICE LTD | Andreas P. Arni | stated | C andreas.arni@marcuardfamil | CEO and Managing Partner of this partner-led MFO, ADV control person/o | |
| 15 | MATTER FAMILY OFFICE | Jerrel Armstrong, MBA | stated | A jarmstrong@matterfamilyoff | CIO who sets and oversees investment strategy, asset allocation, portf | |
| 16 | PINE RIDGE ADVISERS LLC | Baldassare (Baldo) Fod | stated | C baldassare.fodera@pineridg | Founder, Managing Member and 75%+ sole owner (ADV code E) of a ~$5B di | |
| 17 | PMG FAMILY OFFICE, LLC | William Fredrick Blake | stated | C william.blake@pmgfamilyoff | Only named executive officer on Schedule A and sole control-person Man | |
| 18 | POINTONE FAMILY OFFICE | Michael Elliott Walsh | stated | - (none) | CEO and control-person owner (via Front Row LLC in holding co Point1 L | |
| 19 | PULLIAM FAMILY OFFICE, LLC | John Michael Pulliam | stated | C john.pulliam@pulliamfamily | Sole named owner, officer, and control person (75%+ owner) - the only  | |
| 20 | SESTANTE FAMILY OFFICE | Daniel Jerome White (D | stated | C daniel.white@sestante.com | Investment lead - ex-CIO of predecessor Sestante Capital Advisors (202 | |
| 21 | TFO FAMILY OFFICE PARTNERS | Charles (Chuck) Robert | stated | C charles.carroll@tfopartner | Named CIO who leads the Investment Committee (+ Operating/Executive Co | |
| 22 | TIMONIER | Nicholas (Nick) C. Bak | stated | A nicholas@timonier.com | President + majority owner (50-75%) + control person per current ADV - | |
| 23 | WELLSPRING FAMILY OFFICE | Richard (Rich) Joseph  | stated | A rturgeon@wellspringfo.com | Named CIO responsible for the investment program, Schedule A officer/o | |
| 24 | XCEPTION FAMILY OFFICE | Cort Alan Haber, CFP | stated | PUB chaber@xceptionfamilyoffic | Co-founder and CIO owning investment philosophy, asset allocation and  | |

## B. The 18 reclassified non-FOs — confirm each is correctly NOT counted as a family office

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

## C. The 8 quarantined firms — confirm each is correctly withheld

| # | Firm | Reason | ✔/note |
|---|------|--------|--------|
| 1 | CALLAN | entity rejected (not_fo): Institutional investment consultin | |
| 2 | CAPITOL FAMILY OFFICE, INC. | entity type unresolved: Own site is a placeholder ('Website  | |
| 3 | CLEARBROOK INVESTMENT CONSULTI | entity rejected (not_fo): Institutional investment consultin | |
| 4 | COLLECTIVE FAMILY OFFICE, LLC | entity type unresolved: FO positioning ('family's steward')  | |
| 5 | ELYSEUM FAMILY OFFICE S.A. | entity type unresolved: FO division of a EUR2.5B Luxembourg  | |
| 6 | FREEDOM FAMILY OFFICE, LLC | entity type unresolved: Domain on file is a parked/private W | |
| 7 | NICHOLAS HOFFMAN & COMPANY, LL | entity type unresolved: Own site leads with 'private boutiqu | |
| 8 | TAYLOR FRIGON FAMILY OFFICE, L | entity type unresolved: This LLC self-labels only 'SEC-Regis | |

## D. Customer surfaces — review each reachable surface

- [ ] Product CSV (`data/gold/family_office_dataset.csv`) — 39 columns, qualifying FOs first
- [ ] Quarantine CSV (`data/gold/quarantined.csv`) — 8 withheld firms + reasons
- [ ] Live RAG UI (`pipeline/rag/index.html`) — header copy, coverage count, card badges, grade legend
- [ ] API `/query` output — answer text + sources + verification verdict
- [ ] RAG answers — run the buyer paths: present firm, absent firm, multi-constraint, non-FO, unanswerable
- [ ] METHODOLOGY.md / README.md / validation-chains.md — every count + status word
- [ ] Grounding check firing — `python -m pipeline.cli rag-eval` (grounded 8/8, expectation 7/8)

## E. Sign-off

- Reviewer: __________________  Date: __________
- Records reviewed in full (50/50): ☐   Surfaces reviewed (A–D): ☐
- Corrections applied this review (list): 