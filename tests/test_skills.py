"""The contract every shipped runbook must satisfy.

A runbook is prose until something checks it. These assert the properties the
README claims, so the claims cannot quietly stop being true.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cluster_ops_skills.loader import (
    MAX_DESCRIPTION,
    MIN_DESCRIPTION,
    REQUIRED_SECTIONS,
    InvalidSkill,
    Skill,
    load_all,
    parse,
    validate,
)

SKILLS = load_all()
IDS = [s.name for s in SKILLS]


def test_there_are_skills() -> None:
    assert SKILLS


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_every_skill_is_valid(skill: Skill) -> None:
    assert validate(skill) == []


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_name_matches_directory(skill: Skill) -> None:
    """A skill whose name and directory disagree loads under the wrong key."""
    assert skill.name == skill.slug


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_description_routes(skill: Skill) -> None:
    """The description is the only thing a model reads when deciding to load."""
    assert MIN_DESCRIPTION <= len(skill.description) <= MAX_DESCRIPTION
    assert "use when" in skill.description.lower()


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_has_the_sections_that_make_it_a_runbook(skill: Skill) -> None:
    for section in REQUIRED_SECTIONS:
        assert section in skill.sections(), f"{skill.name} missing {section}"


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_measured_claims_carry_a_source(skill: Skill) -> None:
    """A number without a source is the thing these repos argue against."""
    import re

    if re.search(r"\d+(\.\d+)?\s*%", skill.body):
        assert skill.links(), f"{skill.name} quotes a percentage with no source link"


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_declares_only_read_only_tools(skill: Skill) -> None:
    """These runbooks recommend; they do not act.

    The tool names come from slurm-mcp, whose surface is read-only by
    construction. A skill asking for anything else is a design error.
    """
    permitted = {"slurm_query", "slurm_overview", "slurm_describe"}
    assert set(skill.allowed_tools) <= permitted, skill.allowed_tools


def test_names_are_unique() -> None:
    names = [s.name for s in SKILLS]
    assert len(names) == len(set(names))


# --- validator must actually reject bad input -------------------------------


def _write(tmp: Path, name: str, text: str) -> Path:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(text, encoding="utf-8")
    return p


GOOD_BODY = "\n".join(
    ["# T", "## Steps", "1. x", "## What not to conclude", "- x", "## Escalate when", "- x"]
)
GOOD_DESC = (
    "Diagnose a thing on a Slurm cluster and report the finding. Use when someone "
    "reports the thing, or asks why the thing happened."
)


def test_rejects_missing_frontmatter(tmp_path: Path) -> None:
    p = _write(tmp_path, "x", "# no frontmatter\n")
    with pytest.raises(InvalidSkill):
        parse(p)


def test_rejects_missing_required_keys(tmp_path: Path) -> None:
    p = _write(tmp_path, "x", "---\nname: x\n---\nbody\n")
    with pytest.raises(InvalidSkill):
        parse(p)


def test_rejects_name_directory_mismatch(tmp_path: Path) -> None:
    text = f"---\nname: other-name\ndescription: {GOOD_DESC}\n---\n{GOOD_BODY}\n"
    p = _write(tmp_path, "actual-dir", text)
    assert any("does not match directory" in x for x in validate(parse(p)))


def test_rejects_description_without_use_when(tmp_path: Path) -> None:
    desc = (
        "A description comfortably long enough to clear the length floor "
        "but which never states the trigger condition."
    )
    p = _write(tmp_path, "x", f"---\nname: x\ndescription: {desc}\n---\n{GOOD_BODY}\n")
    assert any("Use when" in x for x in validate(parse(p)))


def test_rejects_missing_sections(tmp_path: Path) -> None:
    p = _write(tmp_path, "x", f"---\nname: x\ndescription: {GOOD_DESC}\n---\n# T\n## Steps\n1. x\n")
    problems = validate(parse(p))
    assert any("What not to conclude" in x for x in problems)
    assert any("Escalate when" in x for x in problems)


def test_rejects_uncited_percentage(tmp_path: Path) -> None:
    body = GOOD_BODY + "\nUtilization went to 83.6% after the change.\n"
    p = _write(tmp_path, "x", f"---\nname: x\ndescription: {GOOD_DESC}\n---\n{body}\n")
    assert any("links no source" in x for x in validate(parse(p)))


def test_accepts_a_well_formed_skill(tmp_path: Path) -> None:
    p = _write(tmp_path, "x", f"---\nname: x\ndescription: {GOOD_DESC}\n---\n{GOOD_BODY}\n")
    assert validate(parse(p)) == []


def test_empty_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidSkill):
        load_all(tmp_path)
