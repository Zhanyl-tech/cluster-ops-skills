"""The README's copy-paste commands and its evidence summary.

A reader runs what the README shows, verbatim. An audit found a registration
command that dies on start-up when used as its comment suggested, a `cp` that
fails on a fresh machine, deny rules that left `scontrol requeue` open, and an
evidence summary that contradicted its own table. These pin each fix.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from cluster_ops_skills.surface import CLAUDE_CODE_SERVER_NAME

REPO = Path(__file__).resolve().parent.parent
README = (REPO / "README.md").read_text(encoding="utf-8")
CHANGELOG = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")

_FENCE_RE = re.compile(r"^```(\w*)\n(.*?)^```", re.M | re.S)


def _blocks(lang: str) -> list[str]:
    return [body for tag, body in _FENCE_RE.findall(README) if tag == lang]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _section(heading: str) -> str:
    return README.split(heading, 1)[1].split("\n## ", 1)[0]


def _shell_lines() -> list[str]:
    lines = []
    for block in _blocks("bash"):
        for line in block.splitlines():
            code = line.split("#", 1)[0].strip()
            if code:
                lines.append(code)
    return lines


def test_copy_in_install_creates_the_target_directory_first() -> None:
    """`cp` with several sources fails when the target directory does not exist."""
    (line,) = [ln for ln in _shell_lines() if "cp -R skills/*" in ln]
    assert line.startswith("mkdir -p ~/.claude/skills && ")


def test_mcp_registration_matches_allowed_tools_and_slurm_mcp_cli() -> None:
    """Regression: `slurm-mcp serve --fixtures` exits 2 ("unrecognized arguments").

    slurm-mcp's `--fixtures` belongs to its top-level parser and `serve` takes
    no arguments, so the subcommand must be the last word. The server name must
    be the one the skills' `allowed-tools` are written for.
    """
    commands = [ln for ln in _shell_lines() if ln.startswith("claude mcp add")]
    assert commands, "the README must show how to register slurm-mcp"
    fixture_forms = 0
    for line in commands:
        ours, _, server = line.partition(" -- ")
        assert shlex.split(ours)[-1] == CLAUDE_CODE_SERVER_NAME, line
        argv = shlex.split(server)
        assert argv[0].endswith("slurm-mcp"), line
        assert argv[-1] == "serve", f"flags must come before the subcommand: {line}"
        fixture_forms += "--fixtures" in argv
    assert 0 < fixture_forms < len(commands), "show both the live and the fixture form"


def test_readme_never_installs_slurm_mcp_from_pypi() -> None:
    """`slurm-mcp` on PyPI is a different package; install from a checkout."""
    assert not [ln for ln in _shell_lines() if re.search(r"pip install\s+['\"]?slurm-mcp\b", ln)]
    assert any('pip install -e ".[server]"' in ln for ln in _shell_lines())


def test_allowed_tools_grant_is_described_as_lasting_one_turn() -> None:
    """Regression: the docs say the grant "clears when you send your next message"."""
    text = _flat(README)
    assert "while the skill is active" not in text
    assert "during the turn that invokes the skill" in text
    allow_rules = [
        rule
        for block in _blocks("json")
        for rule in json.loads(block).get("permissions", {}).get("allow", [])
    ]
    assert allow_rules == [f"mcp__{CLAUDE_CODE_SERVER_NAME}__*"]


def _deny_rules() -> list[str]:
    rules: list[str] = []
    for block in _blocks("json"):
        parsed: Any = json.loads(block)
        rules += parsed.get("permissions", {}).get("deny", [])
    return rules


def test_deny_example_denies_whole_programs() -> None:
    """Regression: `Bash(scontrol update *)` left requeue, delete and shutdown open.

    Claude Code "matches everything before the first `*` as written", so a
    subcommand-scoped deny rule blocks that subcommand only.
    """
    rules = _deny_rules()
    assert {"Bash(scontrol *)", "Bash(scancel *)", "Bash(sacctmgr *)", "Bash(sdiag *)"} <= set(
        rules
    )
    narrowed = [r for r in rules if re.fullmatch(r"Bash\((scontrol|sdiag) \S+ \*\)", r)]
    assert narrowed == [], narrowed


def test_evidence_summary_names_every_runbook_the_table_marks_measured() -> None:
    """Regression: the table marked the Slinky rotation measured; the summary left it out."""
    section = _section("## What each runbook rests on")
    rows = [ln for ln in section.splitlines() if ln.startswith("| `")]
    measured = []
    for row in rows:
        cell = re.match(r"\| `([a-z0-9-]+)`", row)
        assert cell is not None, row
        if "**measured**" in row:
            measured.append(cell.group(1))
    assert measured, "the table must mark at least one runbook measured"
    summary = section.split(rows[-1], 1)[1]
    for name in measured:
        assert f"`{name}`" in summary, f"{name} is measured in the table but not in the summary"


def test_no_doc_says_a_slurmctld_restart_has_no_cache() -> None:
    """Regression: accounting.html says a restart recovers the cache.

    Only a *first* start has none; the docs once said the opposite.
    """
    docs = {"README.md": README, "CHANGELOG.md": CHANGELOG}
    docs |= {
        str(p.relative_to(REPO)): p.read_text(encoding="utf-8")
        for p in (REPO / "skills").rglob("*.md")
    }
    for name, text in docs.items():
        flat = _flat(text)
        assert "slurmctld must not restart while slurmdbd is down" not in flat, name
        assert "no cache of that data is available at start-up" not in flat, name


def test_readme_states_what_the_ledger_does_not_detect() -> None:
    """The README must not claim the ledger covers every number when "one" escapes it."""
    contract = _flat(_section("## The contract"))
    assert "spelled-out cardinals" in contract
    assert 'the word "one"' in contract
