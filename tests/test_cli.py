"""The command line, driven the way a user or CI drives it.

Regression focus: one malformed SKILL.md used to make every subcommand raise an
uncaught exception, including `show` of a perfectly good skill.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cluster_ops_skills.cli import main
from conftest import TOOLS, WriteSkill

Capture = pytest.CaptureFixture[str]


@pytest.fixture
def skills_dir(write_skill: WriteSkill, tmp_path: Path) -> Path:
    write_skill("alpha", name="alpha", extra=f"allowed-tools: {TOOLS}\n")
    write_skill("beta", name="beta")
    return tmp_path / "skills"


@pytest.fixture
def empty_ledger(tmp_path: Path) -> Path:
    p = tmp_path / "claims.yaml"
    p.write_text("claims: []\n", encoding="utf-8")
    return p


def test_list(skills_dir: Path, capsys: Capture) -> None:
    assert main(["--skills-dir", str(skills_dir), "list"]) == 0
    out = capsys.readouterr().out
    assert "alpha" in out and "beta" in out
    assert "tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview" in out
    assert "tools: -" in out


def test_index_is_json_with_a_stable_shape(skills_dir: Path, capsys: Capture) -> None:
    assert main(["--skills-dir", str(skills_dir), "index"]) == 0
    index = json.loads(capsys.readouterr().out)
    assert [e["name"] for e in index] == ["alpha", "beta"]
    assert set(index[0]) == {"name", "description", "allowed-tools"}
    assert index[0]["allowed-tools"] == TOOLS.split()


def test_show_known(skills_dir: Path, capsys: Capture) -> None:
    assert main(["--skills-dir", str(skills_dir), "show", "alpha"]) == 0
    assert "## Steps" in capsys.readouterr().out


def test_show_unknown_goes_to_stderr(skills_dir: Path, capsys: Capture) -> None:
    assert main(["--skills-dir", str(skills_dir), "show", "gamma"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown skill 'gamma'; have alpha, beta" in captured.err


def test_validate_ok(skills_dir: Path, empty_ledger: Path, capsys: Capture) -> None:
    code = main(["--skills-dir", str(skills_dir), "--claims", str(empty_ledger), "validate"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "2 skills, 0 with problems" in out
    assert "0 problems" in out


def test_validate_without_ledger_says_so(skills_dir: Path, capsys: Capture) -> None:
    assert main(["--skills-dir", str(skills_dir), "validate"]) == 0
    assert "claims ledger: not checked" in capsys.readouterr().out


def test_validate_reports_a_bad_skill(
    write_skill: WriteSkill, skills_dir: Path, capsys: Capture
) -> None:
    write_skill("gamma", name="not-gamma")
    assert main(["--skills-dir", str(skills_dir), "validate"]) == 1
    out = capsys.readouterr().out
    assert "FAIL not-gamma" in out and "does not match directory" in out


def test_validate_reports_uncovered_figures(
    write_skill: WriteSkill, skills_dir: Path, empty_ledger: Path, capsys: Capture
) -> None:
    write_skill(
        "gamma",
        name="gamma",
        body="# T\n## Steps\n## What not to conclude\n## Escalate when\nIt took 42 minutes.\n",
    )
    code = main(["--skills-dir", str(skills_dir), "--claims", str(empty_ledger), "validate"])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL claims: gamma/SKILL.md" in out and "figure '42'" in out


def test_validate_reports_a_broken_ledger(
    skills_dir: Path, tmp_path: Path, capsys: Capture
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("nope: []\n", encoding="utf-8")
    assert main(["--skills-dir", str(skills_dir), "--claims", str(bad), "validate"]) == 1
    assert "FAIL claims:" in capsys.readouterr().out


def test_malformed_skill_is_a_fail_line_not_a_traceback(
    write_skill: WriteSkill, skills_dir: Path, capsys: Capture
) -> None:
    write_skill("broken", text="no frontmatter here\n")
    assert main(["--skills-dir", str(skills_dir), "validate"]) == 1
    out = capsys.readouterr().out
    assert "ok   alpha" in out and "ok   beta" in out
    assert "FAIL" in out and "missing YAML frontmatter" in out
    assert "3 skills, 1 with problems" in out


def test_malformed_sibling_does_not_break_show(
    write_skill: WriteSkill, skills_dir: Path, capsys: Capture
) -> None:
    write_skill("broken", text="---\nname: [unclosed\n---\nbody\n")
    assert main(["--skills-dir", str(skills_dir), "show", "alpha"]) == 0
    captured = capsys.readouterr()
    assert "## Steps" in captured.out
    assert "not valid YAML" in captured.err


@pytest.mark.parametrize("cmd", ["list", "index"])
def test_malformed_sibling_fails_list_and_index_loudly(
    write_skill: WriteSkill, skills_dir: Path, capsys: Capture, cmd: str
) -> None:
    """Still prints the good skills, but exits non-zero so a script cannot miss one."""
    write_skill("broken", text="no frontmatter\n")
    assert main(["--skills-dir", str(skills_dir), cmd]) == 1
    captured = capsys.readouterr()
    assert "alpha" in captured.out
    assert "broken" in captured.err


@pytest.mark.parametrize("cmd", [["list"], ["index"], ["show", "x"], ["validate"]])
def test_missing_skills_dir(tmp_path: Path, capsys: Capture, cmd: list[str]) -> None:
    assert main(["--skills-dir", str(tmp_path / "none"), *cmd]) == 1
    captured = capsys.readouterr()
    assert "no skills found" in captured.out + captured.err


def test_shipped_skills_validate_with_the_shipped_ledger(capsys: Capture) -> None:
    """Exactly what CI runs: the default skills against the default ledger."""
    code = main(["validate"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "claims ledger" in out and ": 0 problems" in out


def test_module_entry_point() -> None:
    """`python -m cluster_ops_skills.cli` works, in a real interpreter process."""
    proc = subprocess.run(
        [sys.executable, "-m", "cluster_ops_skills.cli", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "queue-not-draining" in proc.stdout
