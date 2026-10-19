"""readmit check encounter.json | readmit note summary.txt [--llm] [--age N ...]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import encounter_from_text, load_encounter, run
from .report import to_markdown


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="readmit", description="30-day readmission risk (LACE, HOSPITAL) and plan.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Assess a structured encounter JSON file")
    c.add_argument("encounter")
    c.add_argument("--format", choices=["markdown", "json"], default="markdown")
    n = sub.add_parser("note", help="Extract inputs from a discharge summary, then assess")
    n.add_argument("note")
    n.add_argument("--llm", action="store_true")
    n.add_argument("--age", type=int)
    n.add_argument("--los-days", type=float)
    n.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = p.parse_args(argv)

    assumptions = []
    if args.cmd == "check":
        enc = load_encounter(args.encounter)
    else:
        try:
            enc, assumptions = encounter_from_text(
                Path(args.note).read_text(), Path(args.note).stem, use_llm=args.llm,
                overrides={"age": args.age, "los_days": args.los_days})
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    a = run(enc)
    if args.format == "json":
        print(json.dumps({**a.to_dict(), "assumptions": assumptions}, indent=2))
    else:
        print(to_markdown(a, assumptions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
