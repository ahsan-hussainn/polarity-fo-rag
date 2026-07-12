# ADR-0008: OpenAI (gpt-4o-mini) as the extraction LLM, behind a provider-agnostic seam

- **Date:** 2026-07-12
- **Status:** Accepted

## Context

Observed (fact): Stage 3 enrichment turns a fetched FO website's text (About / Team / Strategy
pages, captured in bronze) into structured silver fields — investment thesis, sectors, founding
year, and a team list where each person carries a machine-set `is_principal` flag plus contact
hints. The source is unstructured natural-language prose with no fixed layout across firms, so the
task is language understanding, not parsing: rules/regex break the moment the wording or page
structure changes.

Observed (fact): the highest-value judgment in that extraction is principal-vs-staff. The FO-MAX
sample gets this wrong (its Walton contact is an "Accounting Manager," not a principal), so correct
principal targeting is a concrete place we beat the reference. That judgment is exactly what an LLM
is suited to and what regex is not.

Observed (fact): the user has ~$10 of OpenAI credit already on hand. OpenAI `gpt-4o-mini` exposes
native Structured Outputs (strict JSON schema), which is what we need for reliable field extraction.

Assumed (unverified): ~347 enrichment-ready sites (from the ADR-0007 funnel), ~5k input + ~1k output
tokens each ⇒ ~1.7M input + ~0.35M output tokens for a full run ⇒ on the order of ~$0.50 at
gpt-4o-mini rates (pricing taken as an estimate, not verified this session). Even with retries,
ground-truth iterations, and full re-runs the run stays well under the $10 credit.

Inference (not certain): on the nuanced `is_principal` call, a frontier-tier model (e.g. Claude
Haiku 4.5) is somewhat sharper than gpt-4o-mini. We do not need to resolve this by model choice,
because extraction accuracy is *measured* separately by the validation ground-truth set (ADR-0006),
not assumed from the model's reputation.

Constraint context: the locked stack calls for "free-tier LLM grounding." OpenAI is not a free tier,
but at ~$0.50 for the whole run against pre-owned credit it is effectively free-grade, and it removes
the setup friction of standing up a second provider account.

## Decision

Use OpenAI `gpt-4o-mini` with Structured Outputs (strict JSON schema) as the extraction LLM for
Stage 3, and put it behind a thin, provider-agnostic `extract()` seam so the model/provider is a
swappable implementation detail, not a wired-in dependency.

## Options considered

- **OpenAI `gpt-4o-mini` behind a pluggable seam (chosen).**
- **Google Gemini Flash (free tier):** genuinely free with native structured output and ample daily
  limits — the strongest "honors the free-tier constraint" option. Rejected as *primary* only because
  the user already holds OpenAI credit, so OpenAI has zero marginal setup; kept as a first-class
  fallback target behind the seam.
- **Claude Haiku 4.5:** best judgment on principal-vs-staff and most reliable structured output, but
  paid (~$1/$5 per Mtok; ~$3–5 for the run) with no free tier. Rejected as primary on cost/constraint
  grounds; retained as the escalation target for hard/low-confidence sites via the seam.
- **Groq (Llama 3.3 70B, free):** free and fast with JSON mode, but a notch below on principal
  nuance and with tighter rate limits. Rejected as primary; viable seam fallback.
- **Local Ollama (Llama/Qwen 8B):** free and private, but weakest structured-output adherence and
  awkward for the Stage 2 cloud-unattended requirement. Rejected.

## Why this over the others

The user already has the credit, so OpenAI is the lowest-friction path to a working extractor, and
gpt-4o-mini's Structured Outputs give us the schema guarantees the silver layer needs. The seam is
the real insurance: because the choice of model is isolated behind one function, we are not betting
the differentiator on gpt-4o-mini being the sharpest — we can escalate a specific field or a specific
hard site to Claude Haiku, or move the bulk run to Gemini's free tier, without a rewrite. And since
the ground-truth set *measures* FP/FN on the extracted fields, the model decision is reversible on
evidence rather than on vibes. Picking the cheapest capable model first, behind a seam, with accuracy
proven downstream, is the honest ordering.

## Assumptions and risks

- Assumption: gpt-4o-mini's principal-vs-staff accuracy clears the bar once measured against the
  ground-truth set. Risk if not: mitigated by the seam (escalate hard sites to Claude Haiku) and by
  prompt design, not by re-architecting.
- Risk: free/low tiers have rate limits; a several-hundred-site run needs batching + backoff. Low
  impact at this scale but must be built into the runner.
- Risk: provider lock-in. Mitigated structurally — the seam keeps the prompt + schema provider-neutral
  so a swap is a config change.
- Data/privacy: the input is public web text; sending it to a hosted LLM is low-concern. Extracting
  principals' names is PII — we restrict to legitimately public sources and emit honest blanks rather
  than guesses (ADR-0003, ADR-0005). The LLM does not verify emails (SMTP probe) or assign the final
  quality grade (validation layer); it only populates candidate silver fields, each carrying its
  `_source_url`.
- Assumption: the ~$0.50 cost estimate is right to an order of magnitude. Even if it is 5–10× off, it
  stays inside the $10 credit.

## What would change this

Ground-truth FP/FN showing gpt-4o-mini underperforms on principal identification beyond an acceptable
threshold would trigger escalation of hard/low-confidence sites to Claude Haiku 4.5 (or a wholesale
switch) via the seam. A change in OpenAI free-credit availability, pricing, or rate limits that made
the run impractical would push the bulk run to Gemini's free tier. None of these require touching
Stage 3 code beyond the `extract()` implementation.
