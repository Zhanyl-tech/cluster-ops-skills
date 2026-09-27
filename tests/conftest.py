"""Helpers for building scratch skills, so every rule can be shown to reject something."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

GOOD_BODY = "\n".join(
    ["# T", "## Steps", "1. x", "## What not to conclude", "- x", "## Escalate when", "- x"]
)
GOOD_DESC = (
    "Diagnose a thing on a Slurm cluster and report the finding. Use when someone "
    "reports the thing, or asks why the thing happened."
)
TOOLS = "mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview"

WriteSkill = Callable[..., Path]


def skill_text(
    name: str = "x",
    description: str = GOOD_DESC,
    body: str = GOOD_BODY,
    extra: str = "",
) -> str:
    return f"---\nname: {name}\ndescription: {description}\n{extra}---\n{body}\n"


@pytest.fixture
def write_skill(tmp_path: Path) -> WriteSkill:
    """Write ``<tmp>/skills/<directory>/SKILL.md`` and return its path."""

    def _write(directory: str = "x", text: str | None = None, **kwargs: str) -> Path:
        d = tmp_path / "skills" / directory
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        p.write_text(text if text is not None else skill_text(**kwargs), encoding="utf-8")
        return p

    return _write
