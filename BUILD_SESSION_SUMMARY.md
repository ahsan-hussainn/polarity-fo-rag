# Build session summary

**Approximate build time:** ~TODO hours of focused work across the 48-hour window. <!-- fill in your real number before sending; do not pad -->

**Main sessions** (times are from the real commit history, not reconstructed):

1. **Jul 11 ~23:00 → Jul 12 08:00** — ADR system, stack decisions, SEC ADV discovery (23.5k firms →
   439 candidates), Supabase medallion schemas, website fetch → bronze, extraction seam → silver.
2. **Jul 12 ~19:30 → 21:15** — validation layer: email inference + grading, ground-truth labelling and
   measured FP/FN for `is_principal`, gold build, MillionVerifier API run (88 verified emails).
3. **Jul 13 ~00:00 → 02:00** — FO-MAX parity enrichment (LinkedIn, address, URL quality), RAG:
   embeddings + hybrid retrieval + grounded answering, FastAPI UI, Render deploy.
4. **Jul 13 (final hours)** — adversarial review of my own dataset against the brief; found and fixed
   the biggest problem myself (see below).

**What the AI produced vs. what I changed, corrected, or decided:**

- AI (Claude Code) generated most pipeline code, the SQL migrations, and the extraction/answer prompts.
  I decided the architecture: public regulatory sourcing over scraping, medallion layers, the pluggable
  verifier/extractor seams, and the two-axis email grading in which a catch-all is never "valid".
- I reversed my own locked stack decision (local sentence-transformers → OpenAI embeddings) when the
  deploy constraint made it untenable — recorded as ADR-0013 rather than papered over.
- The extractor's `is_principal` looked right and wasn't: I built the blind ground-truth harness, which
  measured precision at only 0.49–0.78 (over-inclusion). Reported honestly instead of tuning to the test.
- The most important correction: a final review found the gold file contained records that are **not
  family offices** (institutional managers pulled in by ADV free-text) and wrong-entity records
  (SpiderRock's ADV website is blackrock.com). My own crosscheck had flagged Oak Hill and I had not
  acted on it. I added a code-level curation gate with per-firm written reasons (ADR-0015,
  `gold.excluded_firms`), cut the file to exactly 50 defensible records, and re-indexed the RAG.
