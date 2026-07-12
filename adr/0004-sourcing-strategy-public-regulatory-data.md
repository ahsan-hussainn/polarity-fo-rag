# ADR-0004: Sourcing family offices from public regulatory + disclosure data

- **Date:** 2026-07-12
- **Status:** Accepted (scope extended by [ADR-0012](./0012-fo-max-parity-enrichment.md): a bounded,
  provenance-tracked search-assisted lookup for corporate LinkedIn is now allowed alongside regulatory +
  on-site data)

## Context

The pipeline must *discover* real family offices automatically (manual compilation is forbidden) from public,
verifiable sources. We ran a live feasibility check on 2026-07-12 before committing. Findings (fact, verified
live, not assumed):

- **SEC Form ADV bulk feed** is reachable and real: gzipped XML via a dated manifest at
  `reports.adviserinfo.sec.gov/reports/CompilationReports/`, ~23,519 firm records. Exposes legal/business
  name, full address, phone, website, **regulatory AUM (Item 5.F)**, employee counts, and client-type mix
  (Item 5.D). "FAMILY OFFICE" appears in 82 firm names, 308 filings. (Historical <=2024 is CSV on the FOIA page.)
- **IRS 990-PF via ProPublica Nonprofit Explorer API** is reachable, JSON, no auth: gives foundation name,
  EIN, address, assets, financials; `formtype==2` isolates private foundations.
- **SEC 13F via EDGAR** (efts full-text search + data.sec.gov submissions + info-table XML) gives real,
  dated holdings for entities that file.

Definition of "family office" for this dataset is deliberately broad (single-family, multi-family,
family-run LLCs, and family foundations), matching the client's own sample and the actionability test:
a capital allocator does not care about the legal form, only whether the entity invests family wealth.

## Decision

Two-track automated discovery, both public and free:

1. **SEC Form ADV** -> candidate family offices: name/DBA regex (`family office`, `MFO`, `family capital/
   wealth/partners`), Item 5.G "other services" free-text match, and an HNW client-mix heuristic (Item 5.D).
   Yields multi-family offices and registered/non-exempt single-family offices.
2. **IRS 990-PF (ProPublica)** -> family foundations: `formtype==2` + name terms + granular NTEE `T2*`.

Enrich both with firm websites (thesis, description, team) and, where the entity files, **13F holdings** for
the "recent activity / signals" columns.

## Options considered

- **Public regulatory + disclosure data (chosen).**
- **Scrape "top family office" listicles / directories:** rejected. Unverifiable, no provenance, likely stale.
- **Buy a commercial family-office database:** rejected. Costs money, and it would not be *our* sourced data.
- **ADV only:** rejected. Misses family foundations, which are in the client's own sample.
- **Manual research into a sheet:** rejected. The task forbids manual compilation.

## Why this over the others

These sources are real, machine-ingestible, and carry their own provenance (a filing URL), which is exactly
what the per-cell verification requirement needs. They also span the broad FO definition we agreed on.

## Assumptions and risks

- **Coverage gap (honest, stated):** genuine single-family offices are *exempt* from SEC registration under
  rule 202(a)(11)(G)-1, so the wealthiest pure SFOs are largely absent from ADV. Our universe skews
  multi-family offices, registered/non-exempt SFOs, and family foundations. Acceptable given the broad
  definition; we state it plainly rather than imply a census.
- **Principal names are NOT in the ADV bulk feed** (Schedule A owners live only in individual PDF filings /
  the separate individuals feed). So principal name + title needs a separate enrichment step: firm website
  team pages, 990-PF raw XML (foundations), or ADV individual filings. This is a real cost, not free.
- 990-PF officer names require parsing raw IRS e-file XML (6-18 month publication lag).
- SEC requires a declared User-Agent and <=10 req/s; ProPublica has no documented limit (be conservative).

## What would change this

If principal-identity enrichment proves too costly to do at quality within the window, we narrow scope to
firm-level intelligence plus the best publicly available principal, and say so, rather than guessing names.
