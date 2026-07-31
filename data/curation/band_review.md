# Band-released records — sampled review (ADR-0034)

11 records released by the auto-release band with **no human ratification**. The band's 16/16 counted precision is measured on the calibration set its own thresholds were chosen against; this review is the only out-of-sample measurement.

For each: does it belong in the qualifying set (`counted_ok`), and is the band's category right (`category_ok`)? Record answers in `data/curation/band_review_verdicts.json`, then run `python -m pipeline.cli band-review --measure`.

## AIONIOS CAPITAL PARTNERS, LLC  ·  CRD 313190

- **Band assigned:** `embedded_fo_practice`
- **Released because:** client mix consistent with the entity claim: 100% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** NEWPORT BEACH, CA · $3M
- **Client mix:** HNW RAUM share **100%** (2,520,010 of 2,520,010) · 1 HNW clients · **0 non-HNW** · 1 employees
- **Gate:** score 80 → `embedded_fo_practice` [site_fo_practice, site_fo_selfdesc, adv_freetext_fo, structural_fo_shape]
- **Website:** https://aionios.us · says "family office" 9×
- **ADV filing:** 2026-03-30 · https://reports.adviserinfo.sec.gov/reports/ADV/313190/PDF/313190.pdf
- **Stated sectors:** Investment Management, Wealth Management, Private Equity, Venture Capital, Real Estate, Alternative Investments

**What the firm publishes about itself:**

  - _ria_with_fo_practice_ — "Aionios Capital Partners | Wealth Management And Family Office Services top of pageAionios Capital PartnersHomeAboutTeamServicesStrategiesClient Portal"  
    <https://www.aionios.us/>
  - _ria_with_fo_practice_ — "anning Core needs Aspirational & Legacy Driven objectives​​ Investment Advisory Family Office Services​ ​ Aionios will work directly with clients incorporating existing relationships"  
    <https://www.aionios.us/services>
  - _ria_with_fo_practice_ — "efficiency strategies with liquidity needs or events Philanthropic placements ​​Family Office Services: Family Office Services Banking and Credit Strategy Family Governance & Educati"  
    <https://www.aionios.us/services>
  - _ria_with_fo_practice_ — "th liquidity needs or events Philanthropic placements ​​Family Office Services: Family Office Services Banking and Credit Strategy Family Governance & Education Wealth Strategy Famil"  
    <https://www.aionios.us/services>
  - _ria_with_fo_practice_ — "he perpetually changing landscape of financial advisory, wealth management, and family office services. ​ Rick earned his undergraduate degree at the University of Southern Californi"  
    <https://www.aionios.us/team>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `embedded_fo_practice` the right label?
note        : 
```

## ANGELES FAMILY OFFICE  ·  CRD 338266

- **Band assigned:** `multi_family_office`
- **Released because:** concordant published evidence, gate score 100 >= 100 [name_fo_strong+site_fo_practice+site_fo_selfdesc+adv_freetext_fo]
- **Location / AUM:** SANTA MONICA, CA · $182M
- **Client mix:** HNW RAUM share **79%** (142,910,383 of 181,973,559) · 18 HNW clients · **0 non-HNW** · 5 employees
- **Gate:** score 100 → `multi_family_office` [name_fo_strong, site_fo_practice, site_fo_selfdesc, adv_freetext_fo]
- **Website:** https://angelesinvestments.com · says "family office" 48×
- **ADV filing:** 2026-06-03 · https://reports.adviserinfo.sec.gov/reports/ADV/338266/PDF/338266.pdf
- **Stated sectors:** Multi-asset, Private Wealth, Institutional OCIO, Advisory

**What the firm publishes about itself:**

  - _ria_with_fo_practice_ — "titutional investment expertise, holistic estate and wealth advice, and bespoke family office services to support generationally wealthy families Santa Monica, CA – January 13, 2026"  
    <https://www.angelesinvestments.com/insights/press/angeles-wealth-management-acquires-xo-capital-launches-angeles-family-office>
  - _ria_with_fo_practice_ — "With the launch of AFO, the firm will integrate these core strengths with XO's family office services, creating a comprehensive in-house offering that enables AFO to address the ful"  
    <https://www.angelesinvestments.com/insights/press/angeles-wealth-management-acquires-xo-capital-launches-angeles-family-office>
  - _ria_with_fo_practice_ — "ment and inorganic growth efforts across the firm's private wealth and emerging family office services. "Launching AFO is about building on a strong foundation and expanding what we"  
    <https://www.angelesinvestments.com/insights/press/angeles-wealth-management-acquires-xo-capital-launches-angeles-family-office>
  - _wealth_manager_ — "anuary 13, 2026 — Angeles Wealth Management, LLC ("Angeles Wealth"), a national wealth management firm serving generationally wealthy families, today announced the acquisition of XO"  
    <https://www.angelesinvestments.com/insights/press/angeles-wealth-management-acquires-xo-capital-launches-angeles-family-office>
  - _wealth_manager_ — "geles Wealth Management Angeles Wealth Management is a national, SEC-registered wealth management firm serving generationally wealthy families. Providing high-net-worth and ultra-hig"  
    <https://www.angelesinvestments.com/insights/press/angeles-wealth-management-acquires-xo-capital-launches-angeles-family-office>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## BILTMORE FAMILY OFFICE, LLC  ·  CRD 167174

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 98% of regulatory AUM from high-net-worth clients, 14 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** CHARLOTTE, NC · $3467M
- **Client mix:** HNW RAUM share **98%** (3,412,626,557 of 3,467,117,434) · 71 HNW clients · **14 non-HNW** · 24 employees
- **Gate:** score 75 → `multi_family_office` [name_fo_strong, site_fo_selfdesc, adv_freetext_fo]
- **Website:** https://biltmorefamilyoffice.com · says "family office" 29×
- **ADV filing:** 2026-03-23 · https://reports.adviserinfo.sec.gov/reports/ADV/167174/PDF/167174.pdf
- **Stated sectors:** Wealth Management, Investment Services, Estate Planning

**What the firm publishes about itself:**

  - _multi_family_office_ — "t Generation℠ Learn more → We're always growing. Meet our team → Some call it a Multi-Family Office. We call it a Collaborative Family Office Governance & Education Investment Ser"  
    <https://www.biltmorefamilyoffice.com/>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## BMO FAMILY OFFICE, LLC  ·  CRD 110264

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 98% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** CHICAGO, IL · $9990M
- **Client mix:** HNW RAUM share **98%** (9,822,408,877 of 9,989,953,619) · 70 HNW clients · **0 non-HNW** · 130 employees
- **Gate:** score 85 → `multi_family_office` [name_fo_strong, site_fo_practice, site_fo_selfdesc]
- **Website:** https://uswealth.bmo.com:443 · says "family office" 123×
- **ADV filing:** 2026-01-28 · https://reports.adviserinfo.sec.gov/reports/ADV/110264/PDF/110264.pdf
- **Stated sectors:** Wealth Management, Investment Management, Trust & Estate, Philanthropy, Tax Planning

**What the firm publishes about itself:**

  - _ria_with_fo_practice_ — "products and services through BMO Bank N.A., a national bank with trust powers; family office services and investment advisory services through BMO Family Office, LLC, an SEC-registe"  
    <https://uswealth.bmo.com:443/our-services/bmo-family-office-wealth-owners/>
  - _ria_with_fo_practice_ — "ed. Not all products and services are available in every state and/or location. Family Office Services are not fiduciary services and are not subject to the Investment Advisers Act o"  
    <https://uswealth.bmo.com:443/our-services/bmo-family-office-wealth-owners/>
  - _wealth_manager_ — "ervices and investment advisory services through BMO Family Office, LLC, an SEC-registered investment adviser; investment advisory services through Stoker Ostler Wealth Advisors, Inc., an S"  
    <https://uswealth.bmo.com:443/our-services/bmo-family-office-wealth-owners/>
  - _wealth_manager_ — "nvestment advisory services through Stoker Ostler Wealth Advisors, Inc., an SEC-registered investment adviser; and trust and investment management services through BMO Delaware Trust Compan"  
    <https://uswealth.bmo.com:443/our-services/bmo-family-office-wealth-owners/>
  - _ria_with_fo_practice_ — "products and services through BMO Bank N.A., a national bank with trust powers; family office services and investment advisory services through BMO Family Office, LLC, an SEC-registe"  
    <https://uswealth.bmo.com:443/bmo-investment-services/insurance-risk-management/>
  - _ria_with_fo_practice_ — "ed. Not all products and services are available in every state and/or location. Family Office Services are not fiduciary services and are not subject to the Investment Advisers Act o"  
    <https://uswealth.bmo.com:443/bmo-investment-services/insurance-risk-management/>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## CONSCIENTIA FAMILY OFFICE, LLC  ·  CRD 307727

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 100% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** MIAMI, FL · $97M
- **Client mix:** HNW RAUM share **100%** (97,284,414 of 97,284,414) · 10 HNW clients · **0 non-HNW** · 4 employees
- **Gate:** score 80 → `multi_family_office` [name_fo_strong, site_fo_selfdesc, structural_fo_shape]
- **Website:** https://conscientiafo.com · says "family office" 8×
- **ADV filing:** 2026-03-30 · https://reports.adviserinfo.sec.gov/reports/ADV/307727/PDF/307727.pdf
- **Stated sectors:** wealth management, family business management, financial planning, investment decisions, family governance

**What the firm publishes about itself:**

  - _multi_family_office_ — "TIC APPROACH PERSONALIZED SERVICE TRANSPARENCY ALIGNMENT OF INTERESTSAND VALUES MULTI-FAMILY OFFICE INFRASTRUCTURE SINGLE-FAMILYOFFICE APPROACH 24/7 SUPPORTAND GUIDANCE MAKE US YO"  
    <https://www.conscientiafo.com/what-we-do-for-you.html>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## HARBOUR CAPITAL ADVISORS, LLC  ·  CRD 157266

- **Band assigned:** `embedded_fo_practice`
- **Released because:** client mix consistent with the entity claim: 100% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** TYSONS CORNER, VA · $701M
- **Client mix:** HNW RAUM share **100%** (701,078,839 of 701,078,839) · 55 HNW clients · **0 non-HNW** · 11 employees
- **Gate:** score 60 → `embedded_fo_practice` [site_fo_practice, site_fo_selfdesc, adv_freetext_fo]
- **Website:** https://harbourcapitaladvisors.com · says "family office" 7×
- **ADV filing:** 2026-02-27 · https://reports.adviserinfo.sec.gov/reports/ADV/157266/PDF/157266.pdf

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `embedded_fo_practice` the right label?
note        : 
```

## HONOR FAMILY OFFICE, LLC  ·  CRD 317000

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 98% of regulatory AUM from high-net-worth clients, 2 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** SANTA BARBARA, CA · $55M
- **Client mix:** HNW RAUM share **98%** (53,838,618 of 54,695,335) · 4 HNW clients · **2 non-HNW** · 1 employees
- **Gate:** score 80 → `multi_family_office` [name_fo_strong, site_fo_selfdesc, structural_fo_shape]
- **Website:** https://honorfamilyoffice.com · says "family office" 7×
- **ADV filing:** 2026-03-18 · https://reports.adviserinfo.sec.gov/reports/ADV/317000/PDF/317000.pdf
- **Stated sectors:** ESG investing, Socially responsible investing

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## KOIOS PRIVATE FAMILY OFFICES, LLC  ·  CRD 338355

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 100% of regulatory AUM from high-net-worth clients, 1 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** DES MOINES, IA · $1M
- **Client mix:** HNW RAUM share **100%** (1,457,806 of 1,458,719) · 4 HNW clients · **1 non-HNW** · 2 employees
- **Gate:** score 80 → `multi_family_office` [name_fo_strong, site_fo_selfdesc, structural_fo_shape]
- **Website:** https://koiospfo.com · says "family office" 13×
- **ADV filing:** 2026-06-11 · https://reports.adviserinfo.sec.gov/reports/ADV/338355/PDF/338355.pdf
- **Stated sectors:** equities, fixed income, currencies, precious metals, commodities, digital assets

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## ONEASCENT FAMILY OFFICES  ·  CRD 323305

- **Band assigned:** `multi_family_office`
- **Released because:** concordant published evidence, gate score 100 >= 100 [name_fo_strong+site_fo_practice+site_fo_selfdesc+adv_freetext_fo]
- **Location / AUM:** BIRMINGHAM, AL · $544M
- **Client mix:** HNW RAUM share **43%** (232,110,401 of 544,486,722) · 35 HNW clients · **43 non-HNW** · 14 employees
- **Gate:** score 100 → `multi_family_office` [name_fo_strong, site_fo_practice, site_fo_selfdesc, adv_freetext_fo]
- **Website:** https://oneascent.com · says "family office" 31×
- **ADV filing:** 2026-04-28 · https://reports.adviserinfo.sec.gov/reports/ADV/323305/PDF/323305.pdf
- **Stated sectors:** Public Markets, Private Markets, Philanthropy

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## WEALTH DIMENSIONS FAMILY OFFICE, INC  ·  CRD 266787

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 100% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** CINCINNATI, OH · $626M
- **Client mix:** HNW RAUM share **100%** (625,356,253 of 625,928,679) · 13 HNW clients · **0 non-HNW** · 16 employees
- **Gate:** score 100 → `multi_family_office` [name_fo_strong, site_fo_practice, adv_freetext_fo, structural_fo_shape]
- **Website:** https://wealthdimensions.com · says "family office" 1×
- **ADV filing:** 2025-09-25 · https://reports.adviserinfo.sec.gov/reports/ADV/266787/PDF/266787.pdf
- **Stated sectors:** Financial Planning, Investment Management, Insurance, Tax Planning, Education Funding, Estate & Legacy Planning, Charitable Planning, 401k Management

**What the firm publishes about itself:**

  - _ria_with_fo_practice_ — "te READ BIO Lisa Bruewer Client Services and Office Manager READ BIO Julie Ring Family Office Services READ BIO Michelle Roth Receptionist READ BIO Bethany Satchell Client Services R"  
    <https://www.wealthdimensions.com/about/>

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```

## WPA FAMILY OFFICE, LLC  ·  CRD 315566

- **Band assigned:** `multi_family_office`
- **Released because:** client mix consistent with the entity claim: 99% of regulatory AUM from high-net-worth clients, 0 non-HNW clients (band requires >=90% and <=15)
- **Location / AUM:** DALLAS, TX · $175M
- **Client mix:** HNW RAUM share **99%** (174,104,386 of 175,198,734) · 21 HNW clients · **0 non-HNW** · 5 employees
- **Gate:** score 85 → `multi_family_office` [name_fo_strong, site_fo_practice, site_fo_selfdesc]
- **Website:** https://wpafamilyoffice.com · says "family office" 8×
- **ADV filing:** 2026-07-02 · https://reports.adviserinfo.sec.gov/reports/ADV/315566/PDF/315566.pdf
- **Stated sectors:** Wealth Management, Private Equity, Tax Planning, Estate Guidance

```
counted_ok  : ?    # is this a qualifying record at all?
category_ok : ?    # is `multi_family_office` the right label?
note        : 
```
