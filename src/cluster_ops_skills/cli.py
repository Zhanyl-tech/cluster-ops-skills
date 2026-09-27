"""List, show and validate the cluster runbooks shipped as Agent Skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .loader import (
    InvalidSkill,
    Skill,
    check_claims,
    default_claims_file,
    default_skills_dir,
    load_claims,
    load_report,
    validate,
)


def _err(msg: str) -> None:
    print(f"cluster-ops-skills: {msg}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cluster-ops-skills", description=__doc__)
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help="directory of <name>/SKILL.md folders (default: the skills shipped with this package)",
    )
    parser.add_argument(
        "--claims",
        type=Path,
        default=None,
        help="claims ledger to check every quoted figure against (default: the "
        "shipped ledger, used only when --skills-dir is not given)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the skill index, as a model would see it")
    sub.add_parser("validate", help="check every skill against the contract")
    p_show = sub.add_parser("show", help="print one skill")
    p_show.add_argument("name")
    sub.add_parser("index", help="machine-readable index as JSON")
    return parser


def _validate(skills: list[Skill], load_errors: list[str], claims_path: Path | None) -> int:
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
    # A file that does not parse is a failed skill, reported like any other
    # rather than as a traceback that hides the rest of the report.
    for e in load_errors:
        bad += 1
        print(f"  FAIL {e}")

    ledger_failed = False
    if claims_path is None:
        ledger_line = "claims ledger: not checked (pass --claims to check a custom --skills-dir)"
    else:
        try:
            claim_problems = check_claims(skills, load_claims(claims_path))
        except InvalidSkill as exc:
            claim_problems = [str(exc)]
        for p in claim_problems:
            print(f"  FAIL claims: {p}")
        ledger_failed = bool(claim_problems)
        ledger_line = f"claims ledger {claims_path}: {len(claim_problems)} problems"

    print(f"\n{len(skills) + len(load_errors)} skills, {bad} with problems")
    print(ledger_line)
    return 1 if bad or ledger_failed else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    skills_dir: Path = args.skills_dir or default_skills_dir()
    claims_path: Path | None = args.claims
    if claims_path is None and args.skills_dir is None:
        claims_path = default_claims_file()

    skills, load_errors = load_report(skills_dir)

    if args.cmd == "validate":
        return _validate(skills, load_errors, claims_path)

    # For every other command, a malformed skill is reported on stderr and the
    # good ones are still served. The exit code stays non-zero for list/index,
    # so a script consuming the index cannot silently miss a skill.
    for e in load_errors:
        _err(e)

    if args.cmd == "list":
        for s in skills:
            tools = " ".join(s.allowed_tools) or "-"
            print(f"  {s.name}")
            print(f"      {s.description[:96]}{'...' if len(s.description) > 96 else ''}")
            print(f"      tools: {tools}")
        return 1 if load_errors else 0

    if args.cmd == "index":
        index = [
            {
                "name": s.name,
                "description": s.description,
                "allowed-tools": list(s.allowed_tools),
            }
            for s in skills
        ]
        print(json.dumps(index, indent=2))
        return 1 if load_errors else 0

    # show
    for s in skills:
        if s.name == args.name:
            print(s.body.strip())
            return 0
    have = ", ".join(s.name for s in skills) or "none"
    _err(f"unknown skill {args.name!r}; have {have}")
    return 1


if __name__ == "__main__":  # pragma: no cover - exercised in a subprocess by the tests
    raise SystemExit(main())
