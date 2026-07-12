# Stage 2 findings: website fetch → bronze

**What was built.** `pipeline/bronze/website.py` + `python -m pipeline.cli fetch-websites`. For each
FO candidate with a website, fetch the homepage + a few high-signal internal pages
(team / about / strategy / contact), strip to readable text, land one append-only bronze row per page
(`source='website'`, `entity_key=crd`, provenance URL stamped by us). Stdlib `urllib` + `lxml`,
descriptive UA, per-request delay, TLS-verify fallback, honest failure recording. Known gap: no
robots.txt parsing yet (we fetch a handful of public pages per firm, politely).

## Belief updates from the first live runs

**1. The ADV `WebAddr` field is frequently a *social* URL, not the firm's site.** Measured on the
strong tier: of **211 strong-tier firms with a website, 70 (33%) point at LinkedIn/Facebook/etc.**,
not a real site. Fetching those returns login walls and generic nav — and a naive link classifier
mistakes that nav for "team" pages. We now skip a domain blocklist (`_SKIP_DOMAINS`) and record those
firms as **un-enrichable-by-website**, an honest blank rather than ingested garbage. Implication: the
website-enrichment path covers ~2/3 of strong-tier firms; the social-only third needs another route
(990-PF, ADV brochure PDF) or an honest firm-level-only record.

**2. Order by AUM surfaces institutional managers, not family offices.** The richest "family office"
matches are large asset managers (Schonfeld, Baillie Gifford, Hamilton Lane) that merely mention the
phrase in ADV free-text. Enrichment now prioritizes **name-contains-"family office"** (highest
confidence: Custos, Capitol, Arrowroot, Seneschal…), then the rest of strong, then medium, then the
weak client-mix tier. `name_contains_family_office` matches are unmistakably real FOs.

**3. End-to-end works on real, messy sites.** Fetched + stored Marcuard Family Office (Zurich MFO),
then ran its bronze text through the extraction seam (live gpt-4o-mini): correct thesis, description,
founded year (1998), empty sectors (an honest blank — an MFO lists no sectors), and a 17-person team.
Non-ASCII names (ü/é/ö) stored correctly in Postgres (verified: zero U+FFFD); earlier `�` were a
Windows-console display artifact only.

**4. Open problem for the ground-truth step: `is_principal` over-includes at partner-titled firms.**
At Marcuard the model flagged all 17 people as principals, because a Swiss MFO titles nearly everyone
"Partner" — including Head of HR and Head of Operations. Flagging 17 principals is about as unhelpful
as flagging none: our target is the *actionable* investment principal, which is narrower than "anyone
titled Partner." This is deliberately **not** fixed by prompt-tuning now — it is exactly what the
validation ground-truth set (ADR-0006) exists to measure (FP/FN on principal identification) and what
should drive any refinement. Tuning before we can measure would be guessing.

## Reproduce

```
python -m pipeline.cli fetch-websites --limit 6            # dry-run, richest genuine FOs first
python -m pipeline.cli fetch-websites --limit 50 --write   # persist to bronze.captures
```
`--write` dedupes on (source, content_hash), so re-runs are safe.
