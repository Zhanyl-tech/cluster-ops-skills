"""Load and validate the skills.

A runbook is prose until something checks it. These are loadable Agent Skills,
so the first contract is the frontmatter the Agent Skills specification
(https://agentskills.io/specification) and Claude's upload path require: a
name that matches the directory, no keys the spec does not define, and a
description written so a model can decide *when* to load it. On top of that
the validator enforces the conventions that make these particular runbooks
worth shipping:

* every skill states what **not** to conclude, because the expensive mistakes on
  a cluster are wrong confident diagnoses rather than missing information;
* every skill says when to **escalate**, because an agent that never hands off
  is worse than one that never starts;
* every topic, filter and tool a runbook tells the agent to use exists on the
  slurm-mcp surface it is written against (:mod:`cluster_ops_skills.surface`);
* every figure a runbook quotes has an entry in the claims ledger
  (``claims.yaml``) that says whether it was measured, documented upstream, or
  is only an illustration -- and, when measured or documented, links where it
  came from.

The last rule is the one that matters. An earlier version of this docstring
quoted scheduler figures as if they had been measured on a real trace; they came
from a seeded synthetic workload in a simulator. The ledger exists so that kind
of drift fails a test instead of shipping.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .surface import PERMITTED_ALLOWED_TOOLS, TOOLS, TOPICS

_PACKAGE = "cluster_ops_skills"
#: A source checkout keeps ``skills/`` and ``claims.yaml`` at the repo root
#: (the layout Claude Code plugins expect); a wheel ships them inside the
#: package. See :func:`default_skills_dir`.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Frontmatter keys a skill must carry.
REQUIRED_KEYS = ("name", "description")
#: The only keys the Agent Skills spec defines. claude.ai upload and the Skills
#: API reject any other key with a hard error, so an extra key is a defect even
#: where Claude Code would tolerate it (https://code.claude.com/docs/en/skills).
ALLOWED_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)
#: Spec: name is 1-64 characters. Claude's API also reserves these words in it
#: (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).
MAX_NAME = 64
RESERVED_NAME_WORDS = ("anthropic", "claude")
#: Spec limit on ``compatibility``.
MAX_COMPATIBILITY = 500
#: Sections every runbook in this repo must have. Not part of the Agent Skills
#: spec -- a local convention, enforced so it cannot quietly lapse.
REQUIRED_SECTIONS = ("## Steps", "## What not to conclude", "## Escalate when")
#: A description short enough to sit in a model's skill index, long enough to
#: say when the skill applies. Stricter than the spec's 1024-character cap.
MIN_DESCRIPTION = 80
MAX_DESCRIPTION = 500

#: Spec: lowercase letters, digits and single hyphens, not at either end.
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.S)
XML_TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z][^<>]*>")
URL_RE = re.compile(r"https?://[^\s)>\]`]+")
PERCENT_RE = re.compile(r"\d+(\.\d+)?\s*%")

#: Where a quoted figure may point. The portfolio's own repos (whose measured
#: claims must be commit-pinned, see :data:`MEASURED_SOURCE_RE`) and the
#: upstream documentation the runbooks rely on. A link to an arbitrary site is
#: not a citation for the purposes of this check.
PORTFOLIO_PREFIX = "https://github.com/Zhanyl-tech/"
DOC_SOURCE_PREFIXES = (
    "https://slurm.schedmd.com/",
    "https://docs.nvidia.com/",
    "https://github.com/NVIDIA/",
    "https://github.com/linux-rdma/",
    "https://code.claude.com/",
    "https://platform.claude.com/",
    "https://agentskills.io/",
)
SOURCE_PREFIXES = (PORTFOLIO_PREFIX, *DOC_SOURCE_PREFIXES)
#: A measured figure's source must be a permalink to a specific commit, so the
#: number cannot silently change underneath the runbook that quotes it.
MEASURED_SOURCE_RE = re.compile(
    r"^https://github\.com/Zhanyl-tech/[A-Za-z0-9._-]+/(?:blob|tree)/[0-9a-f]{40}"
    r"(?:/[^\s#]*)?(?:#L\d+(?:-L\d+)?)?$"
)
CLAIM_KINDS = ("measured", "documented", "illustrative")

# How a runbook names the slurm-mcp surface. Written as a convention so it can
# be checked: "Query `topic`" (optionally "`a` and `b`"), "`topic` filtered by
# `filter`", and tool names as `slurm_<tool>`.
_TOPIC_REF_RE = re.compile(
    r"\b(?:[Qq]uery|[Aa]ttempt)\s+(`[^`\n]+`(?:(?:\s*,\s*|\s+and\s+|\s+or\s+)`[^`\n]+`)*)"
)
_BACKTICKED_RE = re.compile(r"`([^`\n]+)`")
_FILTER_REF_RE = re.compile(r"`([^`\n]+)`\s+filtered\s+by\s+`([^`\n]+)`")
_TOOL_REF_RE = re.compile(r"`(slurm_[a-z_]+)`")
_RELATIVE_LINK_RE = re.compile(r"\]\((?!https?://|#|mailto:)([^)\s#]+)(?:#[^)]*)?\)")

# Figure extraction for the claims ledger. Inline code, link targets, URLs,
# man-page references such as ``ibstat(8)`` and ordered-list markers are
# blanked (same length, so offsets survive) because a command flag, a manual
# section or a step number is not a claim. Fenced blocks are *not* blanked: the
# measured timelines live there.
_MASK_RE = re.compile(
    r"`[^`\n]+`|\]\([^)\s]*\)|<https?://[^>\s]+>|https?://[^\s)>\]]+|<!--.*?-->"
    r"|\b[A-Za-z][\w.-]*\(\d[a-z]?\)",
    re.S,
)
_LIST_MARKER_RE = re.compile(r"^[ \t]*\d+\.(?=[ \t])", re.M)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_.])\d+(?:[.,]\d+)*")
_WORD_TAIL_RE = re.compile(r"[A-Za-z0-9_]*")
# Spelled-out cardinals. Without these, "no self-heal in ninety seconds of
# watching" -- a measured observation -- passed the ledger check that "90
# seconds" would have failed: spelling a number out was a way round it.
# Deliberately excluded, and said so in the README:
#   * "one", which is far more often a pronoun or determiner ("the one check",
#     "one node") than a figure, so matching it would bury real figures in noise;
#   * ordinals ("a second run", "first started") and multiplicatives ("twice").
# "tens" only counts in "tens of", so a stray "tens" elsewhere is not a figure.
_NUMBER_WORD_RE = re.compile(
    r"(?<![\w-])(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
    r"|hundreds?|thousands?|millions?|billions?|dozens?|tens(?=\s+of\b))(?!\w)",
    re.I,
)


class InvalidSkill(Exception):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    body: str
    allowed_tools: tuple[str, ...] = ()
    #: The raw frontmatter mapping, kept so the validator can check keys and
    #: value types the dataclass fields have already normalised away.
    frontmatter: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)
    #: Supporting Markdown under ``references/``, as (relative path, text).
    references: tuple[tuple[str, str], ...] = field(default=(), compare=False, repr=False)
    #: Line number in SKILL.md at which ``body`` starts, for error messages.
    body_first_line: int = field(default=1, compare=False, repr=False)

    @property
    def slug(self) -> str:
        return self.path.parent.name

    def sections(self) -> list[str]:
        return [ln.strip() for ln in self.body.splitlines() if ln.startswith("## ")]

    def links(self) -> list[str]:
        """Every absolute URL in the body."""
        return URL_RE.findall(self.body)

    def documents(self) -> dict[str, str]:
        """SKILL.md body plus every reference file: everything an agent may read."""
        return {"SKILL.md": self.body, **dict(self.references)}


def _default_path(name: str) -> Path:
    """``name`` shipped inside the installed package, else at the repo root.

    A wheel carries ``skills/`` and ``claims.yaml`` as package data (see
    ``[tool.hatch.build.targets.wheel.force-include]``); an editable install or
    a plain checkout finds them at the repository root instead.
    """
    packaged = Path(str(resources.files(_PACKAGE))) / name
    if packaged.exists():
        return packaged
    return _REPO_ROOT / name


def default_skills_dir() -> Path:
    return _default_path("skills")


def default_claims_file() -> Path:
    return _default_path("claims.yaml")


def _split_tools(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str):
        # The spec says space-separated. Commas are split too so a comma-form
        # list still reads correctly; validate() reports it as non-conforming.
        return tuple(t for t in re.split(r"[\s,]+", raw) if t)
    if isinstance(raw, list):
        return tuple(str(t).strip() for t in raw if str(t).strip())
    return ()


def parse(path: Path) -> Skill:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidSkill(f"{path}: cannot read: {exc}") from exc
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise InvalidSkill(f"{path}: missing YAML frontmatter delimited by ---")

    try:
        raw: Any = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise InvalidSkill(f"{path}: frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise InvalidSkill(f"{path}: frontmatter must be a mapping")

    missing = [k for k in REQUIRED_KEYS if not raw.get(k)]
    if missing:
        raise InvalidSkill(f"{path}: frontmatter missing {missing}")
    for key in REQUIRED_KEYS:
        if not isinstance(raw[key], str):
            raise InvalidSkill(f"{path}: frontmatter {key!r} must be a string")

    references: list[tuple[str, str]] = []
    ref_dir = path.parent / "references"
    for ref in sorted(ref_dir.glob("*.md")) if ref_dir.is_dir() else []:
        try:
            references.append((f"references/{ref.name}", ref.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidSkill(f"{ref}: cannot read: {exc}") from exc

    return Skill(
        name=raw["name"],
        description=raw["description"],
        path=path,
        body=match.group(2),
        allowed_tools=_split_tools(raw.get("allowed-tools")),
        frontmatter=raw,
        references=tuple(references),
        body_first_line=text[: match.start(2)].count("\n") + 1,
    )


def _check_frontmatter(skill: Skill) -> list[str]:
    problems: list[str] = []
    fm = skill.frontmatter

    unknown = sorted(str(k) for k in fm if k not in ALLOWED_KEYS)
    if unknown:
        problems.append(
            f"frontmatter keys {unknown} are not in the Agent Skills spec; "
            f"claude.ai and the Skills API reject them. Allowed: {sorted(ALLOWED_KEYS)}"
        )

    if not NAME_RE.match(skill.name):
        problems.append(f"name {skill.name!r} must be lowercase letters, digits and single hyphens")
    if len(skill.name) > MAX_NAME:
        problems.append(f"name is {len(skill.name)} chars; the spec allows at most {MAX_NAME}")
    for word in RESERVED_NAME_WORDS:
        if word in skill.name.lower():
            problems.append(f"name contains the reserved word {word!r}")
    if skill.name != skill.slug:
        problems.append(f"name {skill.name!r} does not match directory {skill.slug!r}")

    for key in ("name", "description"):
        if XML_TAG_RE.search(str(fm.get(key, ""))):
            problems.append(f"{key} contains an XML tag, which Claude's API rejects")

    n = len(skill.description)
    if n < MIN_DESCRIPTION:
        problems.append(
            f"description is {n} chars; under {MIN_DESCRIPTION} it cannot say when to load"
        )
    if n > MAX_DESCRIPTION:
        problems.append(f"description is {n} chars; over {MAX_DESCRIPTION} it bloats the index")
    if "use when" not in skill.description.lower():
        problems.append("description must say 'Use when ...' so a model can route to it")

    if "compatibility" in fm:
        compat = fm["compatibility"]
        if not isinstance(compat, str) or not 1 <= len(compat) <= MAX_COMPATIBILITY:
            problems.append(f"compatibility must be a string of 1-{MAX_COMPATIBILITY} chars")
    if "license" in fm and not isinstance(fm["license"], str):
        problems.append("license must be a string")
    if "metadata" in fm:
        meta = fm["metadata"]
        if not isinstance(meta, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in meta.items()
        ):
            problems.append("metadata must map string keys to string values")

    problems += _check_allowed_tools(skill)
    return problems


def _check_allowed_tools(skill: Skill) -> list[str]:
    """``allowed-tools`` may only pre-approve the read-only slurm-mcp tools.

    This is not a sandbox: in Claude Code the field pre-approves the listed
    tools and restricts nothing. The check exists so a skill never
    *pre-approves* something that can act. Read-only is enforced by slurm-mcp's
    server-side guard, not here.
    """
    if "allowed-tools" not in skill.frontmatter:
        return []
    raw = skill.frontmatter["allowed-tools"]
    problems: list[str] = []
    if not isinstance(raw, str):
        problems.append("allowed-tools must be a space-separated string, per the spec")
    elif "," in raw:
        problems.append("allowed-tools must be space-separated, not comma-separated")
    extra = sorted(set(skill.allowed_tools) - PERMITTED_ALLOWED_TOOLS)
    if extra:
        problems.append(
            f"allowed-tools {extra} are not the read-only slurm-mcp tools "
            f"{sorted(PERMITTED_ALLOWED_TOOLS)}"
        )
    return problems


def surface_references(text: str) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    """Topics, (topic, filter) pairs and tool names a runbook text asks for."""
    topics: set[str] = set()
    for group in _TOPIC_REF_RE.findall(text):
        topics.update(_BACKTICKED_RE.findall(group))
    filters = set(_FILTER_REF_RE.findall(text))
    tools = set(_TOOL_REF_RE.findall(text))
    return topics, filters, tools


def _check_surface(skill: Skill) -> list[str]:
    problems: list[str] = []
    for doc, text in skill.documents().items():
        topics, filters, tools = surface_references(text)
        for topic in sorted(topics - set(TOPICS)):
            problems.append(
                f"{doc}: asks for topic {topic!r}, which slurm-mcp does not have "
                f"(topics: {', '.join(sorted(TOPICS))})"
            )
        for topic, flt in sorted(filters):
            if topic in TOPICS and flt not in TOPICS[topic]:
                accepts = ", ".join(TOPICS[topic]) or "none"
                problems.append(f"{doc}: filters topic {topic!r} by {flt!r}; it accepts {accepts}")
        for tool in sorted(tools - set(TOOLS)):
            problems.append(f"{doc}: names tool {tool!r}; slurm-mcp has {', '.join(TOOLS)}")
    return problems


def _check_relative_links(skill: Skill) -> list[str]:
    """Links to bundled files must resolve and stay inside the skill directory.

    A skill is uploaded or copied as one directory, so a link that climbs out of
    it (to a sibling skill, say) works in this checkout and breaks everywhere
    else.
    """
    problems: list[str] = []
    root = skill.path.parent.resolve()
    for doc, text in skill.documents().items():
        base = (root / doc).parent
        for target in _RELATIVE_LINK_RE.findall(text):
            resolved = (base / target).resolve()
            if not resolved.is_relative_to(root):
                problems.append(f"{doc}: link {target!r} leaves the skill directory")
            elif not resolved.exists():
                problems.append(f"{doc}: link {target!r} points at a missing file")
    return problems


def validate(skill: Skill) -> list[str]:
    """Return a list of problems. Empty means the skill is shippable."""
    problems = _check_frontmatter(skill)

    present = skill.sections()
    for section in REQUIRED_SECTIONS:
        if section not in present:
            problems.append(f"missing required section {section!r}")

    # A cheap floor that needs no ledger: a percentage must sit in a runbook
    # that links at least one recognised source. The claims ledger
    # (check_claims) is the real, per-figure check.
    if PERCENT_RE.search(skill.body) and not any(
        link.startswith(SOURCE_PREFIXES) for link in skill.links()
    ):
        problems.append(
            "quotes a percentage but links no source repo or upstream doc "
            f"(recognised: {', '.join(SOURCE_PREFIXES)})"
        )

    problems += _check_surface(skill)
    problems += _check_relative_links(skill)
    return problems


def load_report(directory: Path | None = None) -> tuple[list[Skill], list[str]]:
    """Parse every ``*/SKILL.md`` under ``directory`` without stopping at the first bad one.

    Returns the skills that parsed and one error string per file that did not,
    so one malformed runbook cannot take down ``show`` for a good one.
    """
    root = directory or default_skills_dir()
    paths = sorted(root.glob("*/SKILL.md")) if root.is_dir() else []
    if not paths:
        return [], [f"no skills found under {root}"]
    skills: list[Skill] = []
    errors: list[str] = []
    for p in paths:
        try:
            skills.append(parse(p))
        except InvalidSkill as exc:
            errors.append(str(exc))
    return skills, errors


def load_all(directory: Path | None = None) -> list[Skill]:
    """Strict loader: raise on the first malformed skill, or if there are none."""
    skills, errors = load_report(directory)
    if errors:
        raise InvalidSkill(errors[0])
    return skills


# --- the claims ledger -------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    """One figure a runbook quotes, and where it comes from."""

    skill: str
    text: str
    kind: str
    file: str = "SKILL.md"
    source: str = ""
    method: str = ""
    note: str = ""


_CLAIM_FIELDS = frozenset(Claim.__dataclass_fields__)


def load_claims(path: Path) -> list[Claim]:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise InvalidSkill(f"{path}: cannot load claims ledger: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("claims"), list):
        raise InvalidSkill(f"{path}: claims ledger must be a mapping with a 'claims' list")
    claims: list[Claim] = []
    for i, entry in enumerate(raw["claims"]):
        where = f"{path}: claims[{i}]"
        if not isinstance(entry, dict):
            raise InvalidSkill(f"{where} must be a mapping")
        unknown = sorted(str(k) for k in entry if k not in _CLAIM_FIELDS)
        if unknown:
            raise InvalidSkill(f"{where} has unknown keys {unknown}")
        for key in ("skill", "text", "kind"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise InvalidSkill(f"{where} needs a non-empty string {key!r}")
        if not all(isinstance(v, str) for v in entry.values()):
            raise InvalidSkill(f"{where}: every value must be a string")
        claims.append(Claim(**entry))
    return claims


def figures(text: str) -> list[tuple[int, str]]:
    """(offset, token) for every number in ``text`` a reader could take as a claim.

    Finds numbers written in digits and spelled-out cardinals from "two" upward
    (see ``_NUMBER_WORD_RE`` for what is excluded and why), in offset order.
    Skips inline code, URLs, link targets, ordered-list markers, and tokens that
    are really identifiers (``S01``, ``v1.2``, a commit hash like ``c02b52f``).
    """
    masked = _MASK_RE.sub(lambda m: " " * len(m.group(0)), text)
    masked = _LIST_MARKER_RE.sub(lambda m: " " * len(m.group(0)), masked)
    found: list[tuple[int, str]] = []
    for m in _NUMBER_RE.finditer(masked):
        tail = _WORD_TAIL_RE.match(masked, m.end())
        if tail is not None and any(c.isdigit() for c in tail.group(0)):
            continue  # hex-looking identifier, not a number
        found.append((m.start(), m.group(0)))
    found += [(m.start(), m.group(0)) for m in _NUMBER_WORD_RE.finditer(masked)]
    return sorted(found)


def _occurrences(haystack: str, needle: str) -> list[tuple[int, int]]:
    """Spans of ``needle`` in ``haystack``, treating any run of whitespace as equal.

    Whitespace-insensitive so that re-wrapping a paragraph does not orphan the
    ledger entries that anchor its figures.
    """
    pattern = r"\s+".join(re.escape(part) for part in needle.split())
    if not pattern:
        return []
    return [(m.start(), m.end()) for m in re.finditer(pattern, haystack)]


def _check_claim_entry(claim: Claim, text: str) -> list[str]:
    where = f"{claim.skill}/{claim.file}: claim {claim.text!r}"
    problems: list[str] = []
    if claim.kind not in CLAIM_KINDS:
        problems.append(f"{where}: kind {claim.kind!r} is not one of {CLAIM_KINDS}")
    if claim.kind == "measured":
        if not MEASURED_SOURCE_RE.match(claim.source):
            problems.append(
                f"{where}: a measured figure needs a commit-pinned permalink "
                f"({PORTFOLIO_PREFIX}<repo>/blob/<40-hex sha>/...), got {claim.source!r}"
            )
        if not claim.method:
            problems.append(f"{where}: a measured figure needs 'method' (what was run)")
    if claim.kind == "documented" and not claim.source.startswith(DOC_SOURCE_PREFIXES):
        problems.append(
            f"{where}: a documented figure needs an upstream doc URL "
            f"({', '.join(DOC_SOURCE_PREFIXES)}), got {claim.source!r}"
        )
    if claim.kind in ("measured", "documented") and claim.source and claim.source not in text:
        problems.append(f"{where}: the runbook must link its source {claim.source}")
    if claim.kind == "illustrative" and not claim.note:
        problems.append(f"{where}: an illustrative figure needs a 'note' saying what it is")
    count = len(_occurrences(text, claim.text))
    if count == 0:
        problems.append(f"{where}: text not found (stale ledger entry?)")
    elif count > 1:
        problems.append(f"{where}: text occurs {count} times; anchor it with more context")
    return problems


def check_claims(skills: Iterable[Skill], claims: Sequence[Claim]) -> list[str]:
    """Every figure in every runbook document must be covered by a ledger entry.

    Also rejects ledger entries that are stale, ambiguous, or unsourced.
    """
    docs: dict[tuple[str, str], tuple[Skill, str]] = {}
    for skill in skills:
        for doc, text in skill.documents().items():
            docs[(skill.name, doc)] = (skill, text)

    problems: list[str] = []
    spans: dict[tuple[str, str], list[tuple[int, int]]] = {key: [] for key in docs}
    for claim in claims:
        key = (claim.skill, claim.file)
        if key not in docs:
            problems.append(f"{claim.skill}/{claim.file}: ledger names a missing skill or file")
            continue
        text = docs[key][1]
        problems += _check_claim_entry(claim, text)
        spans[key] += _occurrences(text, claim.text)

    for key, (skill, text) in sorted(docs.items(), key=lambda kv: kv[0]):
        first_line = skill.body_first_line if key[1] == "SKILL.md" else 1
        for offset, token in figures(text):
            end = offset + len(token)
            if not any(s <= offset and end <= e for s, e in spans[key]):
                line = first_line + text.count("\n", 0, offset)
                problems.append(
                    f"{key[0]}/{key[1]}:{line}: figure {token!r} has no claims-ledger entry"
                )
    return problems
