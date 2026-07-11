"""Pipeline CLI. Each stage is a subcommand over the medallion layers (ADR-0007).

Usage:
    python -m pipeline.cli discover-adv        # Stage 1 (ADV track): find FO candidates
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


def main():
    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(required=True)

    d = sub.add_parser("discover-adv", help="Stage 1: discover FO candidates from SEC Form ADV")
    d.add_argument("--xml", default=None, help="path to a pre-downloaded feed XML (optional)")
    d.set_defaults(func=cmd_discover_adv)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
