"""Pipeline CLI. Each stage is a subcommand over the medallion layers (ADR-0007).

Usage:
    python -m pipeline.cli discover-adv        # Stage 1 (ADV track): find FO candidates
    python -m pipeline.cli db-check            # verify Supabase connectivity + schema
    python -m pipeline.cli db-migrate          # apply db/migrations/*.sql (idempotent)
    python -m pipeline.cli load-bronze         # persist local captures into bronze.captures
    python -m pipeline.cli extract-test        # run the extraction seam on a sample (Stage 3)
    python -m pipeline.cli fetch-websites      # Stage 2: fetch firm websites -> bronze
    python -m pipeline.cli build-silver        # Stage 3: bronze websites -> silver.firms + people
    python -m pipeline.cli validate-emails     # Validation: infer + SMTP-verify + grade emails
"""
from __future__ import annotations
import argparse
import json
import os

from pipeline import config
from pipeline.bronze import adv


def cmd_discover_adv(args):
    result = adv.discover(xml_path=args.xml)
    candidates = result.pop("candidates")

    # write candidates (bronze output) to gitignored data/raw as JSONL
    os.makedirs(config.DATA_RAW, exist_ok=True)
    out = os.path.join(config.DATA_RAW, "adv_candidates.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for c in candidates:
            fh.write(json.dumps({"tier": c.tier, "reasons": c.reasons, **c.firm}) + "\n")

    # report
    print("=" * 64)
    print("STAGE 1 - ADV DISCOVERY")
    print("=" * 64)
    print(json.dumps(result, indent=2))
    print(f"\nwrote {len(candidates)} candidates -> {out}")

    # show a few strong candidates with the fields that matter for actionability
    strong = [c for c in candidates if c.tier == "strong"]
    print(f"\n--- sample of strong candidates ({min(8, len(strong))} of {len(strong)}) ---")
    for c in strong[:8]:
        f = c.firm
        raum = f.get("raum_total")
        raum_s = f"${raum/1e6:.0f}M" if raum else "n/a"
        print(f"  - {f.get('business_name')!r:45} | {f.get('city')},{f.get('state')} "
              f"| AUM {raum_s} | web={bool(f.get('website'))} | {c.reasons}")


def cmd_db_check(args):
    from pipeline import db

    info = db.check()
    print(json.dumps(info, indent=2))
    missing = [x for x in ("vector", "pg_trgm") if x not in info["extensions"]]
    missing += [s for s in ("bronze", "silver", "gold") if s not in info["schemas"]]
    if missing:
        print(f"\n! not yet present: {missing}  -- run: python -m pipeline.cli db-migrate")
    else:
        print("\nOK: extensions + medallion schemas present.")


def cmd_db_migrate(args):
    from pipeline import db

    applied = db.apply_migrations()
    if applied:
        print("applied migrations:")
        for name in applied:
            print(f"  + {name}")
    else:
        print("no pending migrations (schema up to date).")


def _iter_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def cmd_load_bronze(args):
    """Persist the local ADV candidates + domain assessments into bronze.captures."""
    from pipeline import db

    total = 0
    adv_path = os.path.join(config.DATA_RAW, "adv_candidates.jsonl")
    if os.path.exists(adv_path):
        rows = [
            {"source": rec.get("source", "sec_adv"), "source_url": rec.get("source_url"),
             "entity_key": rec.get("crd"), "raw": rec}
            for rec in _iter_jsonl(adv_path)
        ]
        n = db.insert_captures(rows)
        print(f"sec_adv       : {n} new / {len(rows)} read  <- {adv_path}")
        total += n

    dom_path = os.path.join(config.DATA_RAW, "domain_assessment.jsonl")
    if os.path.exists(dom_path):
        rows = [
            {"source": "smtp_probe", "source_url": None,
             "entity_key": rec.get("domain"), "raw": rec}
            for rec in _iter_jsonl(dom_path)
        ]
        n = db.insert_captures(rows)
        print(f"smtp_probe    : {n} new / {len(rows)} read  <- {dom_path}")
        total += n

    print(f"\ninserted {total} new bronze rows (re-runs dedupe to 0).")


def cmd_extract_test(args):
    """Run the Stage 3 extraction seam on a sample (ADR-0008)."""
    from pipeline.silver import extract as ex

    text = open(args.file, encoding="utf-8").read() if args.file else ex.SAMPLE_TEXT
    extractor = ex.get_extractor(args.provider)
    print(f"provider seam -> {extractor.name}\n" + "-" * 64)
    result = extractor.extract(text, source_url=args.source_url)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


def cmd_fetch_websites(args):
    """Stage 2: fetch candidate firm websites into bronze (ADR-0006)."""
    from pipeline.bronze import website

    print("=" * 64)
    print(f"STAGE 2 - WEBSITE FETCH ({'WRITE' if args.write else 'dry-run'}, "
          f"limit={args.limit}, max_pages={args.max_pages})")
    print("=" * 64)
    result = website.run(args.limit, max_pages=args.max_pages, write=args.write,
                         delay=args.delay, timeout=args.timeout)
    failures = result.pop("failures")
    print("-" * 64)
    print(json.dumps(result, indent=2))
    if failures:
        print(f"\n--- {len(failures)} firm(s) with no usable content ---")
        for f in failures[:20]:
            print(f"  {(f['name'] or '')[:38]:38} {f['website'][:32]:32} {f['error']}")


def cmd_build_silver(args):
    """Stage 3: resolve bronze website captures into silver.firms + silver.people (ADR-0009)."""
    from pipeline.silver import load

    print("=" * 64)
    print(f"STAGE 3 - BUILD SILVER ({'WRITE' if args.write else 'dry-run'}, "
          f"provider={args.provider or 'env/default'}, limit={args.limit})")
    print("=" * 64)
    result = load.run(args.provider, limit=args.limit, write=args.write)
    firms = result.pop("firms")
    for f in firms:
        print(f"  {f['crd']:>8} {(f['firm_name'] or '')[:34]:34} "
              f"{f['pages']}p -> {f['team']:>2} people ({f['principals']} principal) "
              f"| {f['founded_year'] or '----'} | {', '.join(f['sectors'][:4])}")
        if f["thesis"]:
            print(f"           thesis: {f['thesis']}")
    print("-" * 64)
    print(json.dumps(result, indent=2))
    if not args.write:
        print("\n(dry-run: nothing persisted. add --write to load silver. "
              "use --provider mock to avoid LLM cost.)")


def cmd_validate_emails(args):
    """Validation layer: infer + SMTP-verify + grade emails into silver.people (ADR-0005)."""
    from pipeline.silver import validate

    scope = "all" if args.all else "principals"
    print("=" * 64)
    print(f"VALIDATION - EMAILS ({'WRITE' if args.write else 'dry-run'}, scope={scope}, "
          f"verifier={args.verifier or 'smtp'}, limit={args.limit})")
    print("=" * 64)
    result = validate.run(scope, limit=args.limit, write=args.write, delay=args.delay,
                          verifier=args.verifier, only_grade=args.only_grade,
                          max_candidates=args.max_candidates)
    rows = result.pop("rows")
    for r in rows:
        print(f"  [{r['grade']:>2}] {(r['person'] or '')[:26]:26} {(r['email'] or '—')[:34]:34} "
              f"{r['code']}")
    print("-" * 64)
    print(json.dumps(result, indent=2))
    if not args.write:
        print("\n(dry-run: nothing persisted. add --write to fill silver.people.)")


def cmd_rag_index(args):
    """Embed the gold dataset into gold.rag_docs for hybrid retrieval (ADR-0013)."""
    from pipeline.rag import embed

    print("=" * 64)
    print(f"RAG INDEX ({'WRITE' if args.write else 'dry-run'})")
    print("=" * 64)
    result = embed.build_index(write=args.write)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.write:
        print("\n(dry-run: nothing embedded. add --write to build the index.)")


def cmd_rag_query(args):
    """Ask the Micro-RAG a question over the gold dataset."""
    from pipeline.rag import answer as ra

    result = ra.answer(args.question, k=args.k)
    print("=" * 64)
    print(f"Q: {result['query']}")
    print("=" * 64)
    print(result["answer"])
    print("\n--- sources ---")
    for s in result["sources"]:
        em = f"{s['email']} [{s['email_grade']}]" if s.get("email") else "—"
        print(f"  {(s['firm'] or '')[:34]:34} {(s['contact'] or '')[:22]:22} {em:34} "
              f"({'+'.join(s['matched'])}, {s['score']})")


def cmd_load_linkedin(args):
    """Apply committed corporate-LinkedIn enrichment results to silver.firms."""
    from pipeline.silver import enrich

    print(json.dumps(enrich.load_corporate_linkedin(), indent=2))


def cmd_entity_evidence(args):
    """ADR-0020: assemble entity evidence sheet with draft category proposals (never decisions)."""
    from pipeline import curate

    print(json.dumps(curate.evidence_sheet(), indent=2))


def cmd_entity_apply(args):
    """ADR-0020: apply human-ratified entity adjudications to gold.entity_adjudications."""
    from pipeline import curate

    kwargs = {"write": args.write}
    if args.path:
        kwargs["path"] = args.path
    print(json.dumps(curate.apply(**kwargs), indent=2))


def cmd_contact_apply(args):
    """ADR-0021/0022: apply human-ratified contact adjudications to gold.contact_adjudications."""
    from pipeline import curate

    kwargs = {"write": args.write}
    if args.path:
        kwargs["path"] = args.path
    print(json.dumps(curate.apply_contacts(**kwargs), indent=2))


def cmd_verify_contacts(args):
    """WS3b: infer + vendor-verify emails for the proven decision-makers lacking a published address."""
    from pipeline import curate

    print(json.dumps(curate.verify_contacts(write=args.write, limit=args.limit), indent=2))


def cmd_build_gold(args):
    """Silver -> gold: assemble decision-grade FO-MAX-shaped records (ADR-0011)."""
    from pipeline.gold import build as gb

    print("=" * 64)
    print(f"BUILD GOLD ({'WRITE' if args.write else 'dry-run'})")
    print("=" * 64)
    result = gb.build(write=args.write)
    rows = result.pop("rows")
    for r in rows:
        print(f"  [{r['score']:>3}] {(r['firm'] or '')[:32]:32} -> "
              f"{(r['primary'] or '(no principal)')[:24]:24} {(r['title'] or '')[:30]:30} "
              f"{r['grade'] or ''}")
    print("-" * 64)
    print(json.dumps(result, indent=2))
    if not args.write:
        print("\n(dry-run: nothing persisted. add --write to build gold.records.)")


def cmd_gold_export(args):
    from pipeline.gold import build as gb

    print(json.dumps(gb.export(), indent=2))


def cmd_gt_export(args):
    from pipeline import eval as ev

    n = ev.export(limit=args.limit)
    print(f"wrote {n} people -> {ev.LABELS_CSV}\nfill in truth_is_principal (1/0), then: gt-score")


def cmd_gt_label(args):
    from pipeline import eval as ev

    print(json.dumps(ev.label(), indent=2))
    print("review data/ground_truth/principal_labels.csv, then: gt-score")


def cmd_gt_score(args):
    from pipeline import eval as ev

    result = ev.score()
    fps = result.pop("false_positives", [])
    fns = result.pop("false_negatives", [])
    print(json.dumps(result, indent=2))
    if fps:
        print(f"\n--- false positives (flagged principal, actually not): {len(fps)} ---")
        for f in fps:
            print(f"  {(f['name'] or '')[:26]:26} {f['title']}")
    if fns:
        print(f"\n--- false negatives (missed real principals): {len(fns)} ---")
        for f in fns:
            print(f"  {(f['name'] or '')[:26]:26} {f['title']}")


def cmd_gt_crosscheck(args):
    from pipeline import eval as ev

    result = ev.crosscheck()
    flagged = result.pop("flagged")
    print(json.dumps(result, indent=2))
    print(f"\n--- firms flagging >={int(result['ratio_threshold']*100)}% of their team as principals "
          f"(over-inclusion signal; ADV employees = authoritative context) ---")
    for f in flagged:
        print(f"  {(f['firm'] or '')[:34]:34} principals={f['website_principals']:>2}/"
              f"{f['website_people']:<2} ({int(f['principal_ratio']*100)}%)  ADV_employees={f['adv_employees']}")


def main():
    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(required=True)

    d = sub.add_parser("discover-adv", help="Stage 1: discover FO candidates from SEC Form ADV")
    d.add_argument("--xml", default=None, help="path to a pre-downloaded feed XML (optional)")
    d.set_defaults(func=cmd_discover_adv)

    sub.add_parser("db-check", help="verify Supabase connectivity + extensions + schemas").set_defaults(
        func=cmd_db_check)
    sub.add_parser("db-migrate", help="apply db/migrations/*.sql (idempotent)").set_defaults(
        func=cmd_db_migrate)
    sub.add_parser("load-bronze", help="persist local captures into bronze.captures").set_defaults(
        func=cmd_load_bronze)

    e = sub.add_parser("extract-test", help="Stage 3: run the extraction seam on a sample")
    e.add_argument("--provider", default=None, help="mock | openai (default: env EXTRACT_PROVIDER or openai)")
    e.add_argument("--file", default=None, help="path to a text file to extract (default: built-in sample)")
    e.add_argument("--source-url", default=None, help="provenance URL to stamp on the result")
    e.set_defaults(func=cmd_extract_test)

    w = sub.add_parser("fetch-websites", help="Stage 2: fetch firm websites into bronze")
    w.add_argument("--limit", type=int, default=10, help="number of firms to fetch (richest first)")
    w.add_argument("--max-pages", type=int, default=5, help="max pages per firm (home + internal)")
    w.add_argument("--write", action="store_true", help="persist to bronze (default: dry-run)")
    w.add_argument("--delay", type=float, default=1.0, help="seconds between firms (politeness)")
    w.add_argument("--timeout", type=int, default=15, help="per-request timeout seconds")
    w.set_defaults(func=cmd_fetch_websites)

    s = sub.add_parser("build-silver", help="Stage 3: bronze websites -> silver.firms + people")
    s.add_argument("--provider", default=None, help="mock | openai (default: env EXTRACT_PROVIDER or openai)")
    s.add_argument("--limit", type=int, default=None, help="max firms to process (default: all)")
    s.add_argument("--write", action="store_true", help="persist to silver (default: dry-run)")
    s.set_defaults(func=cmd_build_silver)

    v = sub.add_parser("validate-emails", help="Validation: infer + SMTP-verify + grade emails")
    v.add_argument("--all", action="store_true", help="all people (default: principals only)")
    v.add_argument("--limit", type=int, default=None, help="max people to process")
    v.add_argument("--write", action="store_true", help="persist to silver.people (default: dry-run)")
    v.add_argument("--delay", type=float, default=1.0, help="seconds between probes (politeness)")
    v.add_argument("--verifier", default=None,
                   help="domain (domain-level grade) | millionverifier | mock (default: SMTP-from-host)")
    v.add_argument("--only-grade", default=None,
                   help="re-verify only people currently at this grade (e.g. C), to save API credits")
    v.add_argument("--max-candidates", type=int, default=3,
                   help="max address patterns probed per person (API credit control)")
    v.set_defaults(func=cmd_validate_emails)

    sub.add_parser("load-linkedin", help="Apply committed corporate-LinkedIn enrichment to silver").set_defaults(
        func=cmd_load_linkedin)

    ri = sub.add_parser("rag-index", help="Embed gold into gold.rag_docs for hybrid retrieval")
    ri.add_argument("--write", action="store_true", help="persist embeddings (default: dry-run)")
    ri.set_defaults(func=cmd_rag_index)
    rq = sub.add_parser("rag-query", help="Ask the Micro-RAG a question over gold")
    rq.add_argument("question", help="the question to ask")
    rq.add_argument("--k", type=int, default=5, help="number of records to retrieve/ground on")
    rq.set_defaults(func=cmd_rag_query)

    ee = sub.add_parser("entity-evidence", help="ADR-0020: assemble per-firm entity evidence + draft proposals for review")
    ee.set_defaults(func=cmd_entity_evidence)
    ea = sub.add_parser("entity-apply", help="ADR-0020: load ratified entity adjudications (refuses unratified rows)")
    ea.add_argument("--write", action="store_true")
    ea.add_argument("--path", default=None)
    ea.set_defaults(func=cmd_entity_apply)
    ca = sub.add_parser("contact-apply", help="ADR-0021/0022: load ratified contact adjudications (refuses unratified rows)")
    ca.add_argument("--write", action="store_true")
    ca.add_argument("--path", default=None)
    ca.set_defaults(func=cmd_contact_apply)
    cv = sub.add_parser("verify-contacts", help="WS3b: vendor-verify inferred emails for proven decision-makers")
    cv.add_argument("--write", action="store_true")
    cv.add_argument("--limit", type=int, default=None)
    cv.set_defaults(func=cmd_verify_contacts)

    g = sub.add_parser("build-gold", help="Silver -> gold: decision-grade FO-MAX-shaped records")
    g.add_argument("--write", action="store_true", help="persist to gold.records (default: dry-run)")
    g.set_defaults(func=cmd_build_gold)
    sub.add_parser("gold-export", help="Export gold.records to a CSV deliverable").set_defaults(
        func=cmd_gold_export)

    ge = sub.add_parser("gt-export", help="Ground truth: export a blind is_principal labelling CSV")
    ge.add_argument("--limit", type=int, default=None, help="max people to export")
    ge.set_defaults(func=cmd_gt_export)
    sub.add_parser("gt-label", help="Ground truth: adjudicate titles -> labelled CSV (rubric)").set_defaults(
        func=cmd_gt_label)
    sub.add_parser("gt-score", help="Ground truth: score model is_principal vs hand labels").set_defaults(
        func=cmd_gt_score)
    sub.add_parser("gt-crosscheck", help="Ground truth: website principals vs ADV employee counts").set_defaults(
        func=cmd_gt_crosscheck)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
