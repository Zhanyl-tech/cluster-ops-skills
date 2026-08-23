"""Load and validate the skills.

A runbook is prose until something checks it. These are loadable Agent Skills,
so the contract is the frontmatter: a name that matches the directory, and a
description written so a model can decide *when* to load it. The validator
enforces both, plus the conventions that make these particular runbooks worth
shipping:

* every skill states what **not** to conclude, because the expensive mistakes on
  a cluster are wrong confident diagnoses rather than missing information;
* every skill says when to **escalate**, because an agent that never hands off
  is worse than one that never starts;
* any measured claim carries a link to the repo that measured it, so a reader
  can check the number rather than take it.

The last rule is the one that matters. These runbooks quote real figures --
72.2% to 83.6%, a DBD queue climbing to 6 -- and a number without a source is
the thing this whole set of repos exists to argue against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"

#: Frontmatter keys a skill must carry.
REQUIRED_KEYS = ("name", "description")
#: Sections every runbook in this repo must have. Not part of the Agent Skills
#: spec -- a local convention, enforced so it cannot quietly lapse.
REQUIRED_SECTIONS = ("## Steps", "## What not to conclude", "## Escalate when")
#: A description short enough to sit in a model's skill index, long enough to
#: say when the skill applies.
MIN_DESCRIPTION = 80
MAX_DESCRIPTION = 500

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.S)


class InvalidSkill(Exception):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    body: str
    allowed_tools: tuple[str, ...] = ()

    @property
    def slug(self) -> str:
        return self.path.parent.name

    def sections(self) -> list[str]:
        return [ln.strip() for ln in self.body.splitlines() if ln.startswith("## ")]

    def links(self) -> list[str]:
        return re.findall(r"https://github\.com/[A-Za-z0-9._/-]+", self.body)


def parse(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise InvalidSkill(f"{path}: missing YAML frontmatter delimited by ---")

    raw: Any = yaml.safe_load(match.group(1))
    if not isinstance(raw, dict):
        raise InvalidSkill(f"{path}: frontmatter must be a mapping")

    missing = [k for k in REQUIRED_KEYS if not raw.get(k)]
    if missing:
        raise InvalidSkill(f"{path}: frontmatter missing {missing}")

    tools = raw.get("allowed-tools") or ""
    if isinstance(tools, str):
        tool_tuple = tuple(t.strip() for t in tools.split(",") if t.strip())
    else:
        tool_tuple = tuple(str(t).strip() for t in tools)

    return Skill(
        name=str(raw["name"]),
        description=str(raw["description"]),
        path=path,
        body=match.group(2),
        allowed_tools=tool_tuple,
    )


def validate(skill: Skill) -> list[str]:
    """Return a list of problems. Empty means the skill is shippable."""
    problems: list[str] = []

    if not NAME_RE.match(skill.name):
        problems.append(f"name {skill.name!r} must be lowercase-with-hyphens")
    if skill.name != skill.slug:
        problems.append(f"name {skill.name!r} does not match directory {skill.slug!r}")

    n = len(skill.description)
    if n < MIN_DESCRIPTION:
        problems.append(
            f"description is {n} chars; under {MIN_DESCRIPTION} it cannot say when to load"
        )
    if n > MAX_DESCRIPTION:
        problems.append(f"description is {n} chars; over {MAX_DESCRIPTION} it bloats the index")
    if "use when" not in skill.description.lower():
        problems.append("description must say 'Use when ...' so a model can route to it")

    present = skill.sections()
    for section in REQUIRED_SECTIONS:
        if section not in present:
            problems.append(f"missing required section {section!r}")

    # Any measured claim needs a citation.
    if re.search(r"\d+(\.\d+)?\s*%", skill.body) and not skill.links():
        problems.append("quotes a percentage but links no source repo")

    return problems


def load_all(directory: Path | None = None) -> list[Skill]:
    root = directory or SKILLS_DIR
    skills = [parse(p) for p in sorted(root.glob("*/SKILL.md"))]
    if not skills:
        raise InvalidSkill(f"no skills found under {root}")
    return skills
