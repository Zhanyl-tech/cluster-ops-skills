"""Command line entry point."""

from __future__ import annotations

import argparse
import json

from .loader import load_all, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cluster-ops-skills", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the skill index, as a model would see it")
    sub.add_parser("validate", help="check every skill against the contract")
    p_show = sub.add_parser("show", help="print one skill")
    p_show.add_argument("name")
    sub.add_parser("index", help="machine-readable index as JSON")

    args = parser.parse_args(argv)
    skills = load_all()

    if args.cmd == "list":
        for s in skills:
            tools = ", ".join(s.allowed_tools) or "-"
            print(f"  {s.name}")
            print(f"      {s.description[:96]}{'...' if len(s.description) > 96 else ''}")
            print(f"      tools: {tools}")
        return 0

    if args.cmd == "index":
        print(
            json.dumps(
                [
                    {
                        "name": s.name,
                        "description": s.description,
                        "allowed-tools": list(s.allowed_tools),
                    }
                    for s in skills
                ],
                indent=2,
            )
        )
        return 0

    if args.cmd == "show":
        for s in skills:
            if s.name == args.name:
                print(s.body.strip())
                return 0
        print(f"unknown skill {args.name!r}; have {', '.join(s.name for s in skills)}")
        return 1

    if args.cmd == "validate":
        bad = 0
        for s in skills:
            problems = validate(s)
            if problems:
                bad += 1
                print(f"  FAIL {s.name}")
                for p in problems:
                    print(f"       {p}")
            else:
                print(f"  ok   {s.name}")
        print(f"\n{len(skills)} skills, {bad} with problems")
        return 1 if bad else 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
