# ADR-0018: Presentation layer — the "Coverage Desk" UI, designed around grade and routing

- **Date:** 2026-07-14
- **Status:** Accepted

## Context

The original UI was a competent generic dark-SaaS search page: blue accent, one answer block,
plain source cards. Two observations argued for a redesign:

- The two most distinctive things this system produces — the **A–F contactability grade** and the
  **deterministic outreach routing** ("email the founder" / "route via the CIO" / "call the office")
  — were rendered as small badges and a text line, visually indistinguishable from any other
  metadata. The product's differentiators did not look like differentiators.
- The buyer persona is a fund manager building a call list, not a consumer searching a catalog. The
  mental model is a research desk's coverage brief: a verdict, ranked targets, and per-target
  instructions — which is also exactly the answer shape ADR-0016 already produces.

## Decision

Reframe the single page as a private-markets **"Coverage Desk"** (`pipeline/rag/index.html`, still
one static file, no build step, no framework):

- **Information design around the differentiators.** Each target renders as a coverage entry with a
  circular **grade seal** (A–F, color-coded, labelled "contact") on its rail, and a bordered
  **"how to reach them" bar** that surfaces `best_channel` in plain language — verified email /
  plausible (catch-all) / route via the secondary contact / call the office / LinkedIn. The grade
  legend in the footer states explicitly that a grade rates the *email*, nothing else (the honesty
  rule from ADR-0005, carried to the pixel).
- **An intent readout** above the brief shows how the query was parsed ("read as aggregate · state
  NY · AUM ≥ $1B") — the system shows its reasoning instead of hiding the routing (ADR-0016) behind
  magic.
- **Full-record cards**: AUM, location, phone, corporate LinkedIn, website, and the SEC ADV filing
  link, so provenance is one click away from every claim.
- **Identity**: warm-ink palette with a single brass accent (deliberately away from default
  dark-SaaS blue); Newsreader serif for masthead/verdict/firm names, IBM Plex Sans for prose, IBM
  Plex Mono for all data values (emails, AUM, phones, grades). Light/dark theme-aware, keyboard
  focus rings, `prefers-reduced-motion` respected, responsive to small screens.
- **Works with streaming (ADR-0017)**: the meta event renders the readout + coverage cards at ~2s;
  the serif brief then streams in above them. The desk metaphor absorbs this naturally — targets
  land first, the analyst's brief "writes itself" after.

## Options considered

- **Keep the generic dark-SaaS page.** Rejected: it presented the dataset's differentiators as
  afterthoughts, and read as a template — the exact "could apply to any company" signal to avoid.
- **A JS framework + component library.** Rejected: one static HTML file has no build step, no
  dependency surface, and same-origin serving (ADR-0014); the page is one search box and a list.
- **Web-safe system fonts only.** Considered (zero external requests); accepted Google Fonts as the
  one external dependency because the editorial identity carries real information hierarchy
  (serif = judgment, mono = data). Degrades gracefully to system fonts if the CDN is unreachable.

## Assumptions and risks

- Google Fonts is the page's only external request; if blocked, fallback stacks keep it readable.
- The grade-seal metaphor assumes the A–F scale is explained nearby — the footer legend is
  load-bearing, not decorative.
- Authored by the developer directly (commit `ac0ad06`); the streaming integration that followed
  (ADR-0017) preserved the design and only replaced the fetch path.

## What would change this

Real users would justify filters as UI (state/AUM dropdowns feeding the typed-filter leg directly,
skipping intent extraction), saved target lists, and CSV export of a coverage run — all of which fit
the desk metaphor without changing the serving contract.
