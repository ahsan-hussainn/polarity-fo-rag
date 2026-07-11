"""Pipeline CLI. Each stage is a subcommand over the medallion layers (ADR-0007).

Usage:
    python -m pipeline.cli discover-adv        # Stage 1 (ADV track): find FO candidates
    python -m pipeline.cli db-check            # verify Supabase connectivity + schema
    python -m pipeline.cli db-migrate          # apply db/migrations/*.sql (idempotent)
    python -m pipeline.cli load-bronze         # persist local captures into bronze.captures
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

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
