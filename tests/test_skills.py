"""The contract every shipped runbook must satisfy.

A runbook is prose until something checks it. These assert the properties the
README claims, so the claims cannot quietly stop being true.

Skills are discovered by directory and parsed inside each test, so one
malformed SKILL.md fails its own tests instead of breaking collection for the
whole module.
"""

from __future__ import annotations

import json
import tomllib
from importlib import resources
from pathlib import Path

import pytest

import cluster_ops_skills.loader as loader_module
from cluster_ops_skills.loader import (
    MAX_DESCRIPTION,
    MIN_DESCRIPTION,
    REQUIRED_SECTIONS,
    Skill,
    check_claims,
    default_claims_file,
    default_skills_dir,
    figures,
    load_all,
    load_claims,
    parse,
    surface_references,
    validate,
)
from cluster_ops_skills.surface import (
    PERMITTED_ALLOWED_TOOLS,
    TOOLS,
    TOPICS,
    claude_code_tool_name,
)

REPO = Path(__file__).resolve().parent.parent
SKILL_DIRS = sorted(p.parent.name for p in default_skills_dir().glob("*/SKILL.md"))


def _skill(name: str) -> Skill:
    return parse(default_skills_dir() / name / "SKILL.md")


def test_there_are_skills() -> None:
    assert len(SKILL_DIRS) >= 11


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_every_skill_is_valid(name: str) -> None:
    assert validate(_skill(name)) == []


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_name_matches_directory(name: str) -> None:
    """A skill whose name and directory disagree loads under the wrong key."""
    assert _skill(name).name == name


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_description_routes(name: str) -> None:
    """The description is the only thing a model reads when deciding to load."""
    s = _skill(name)
    assert MIN_DESCRIPTION <= len(s.description) <= MAX_DESCRIPTION
    assert "use when" in s.description.lower()


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_has_the_sections_that_make_it_a_runbook(name: str) -> None:
    s = _skill(name)
    for section in REQUIRED_SECTIONS:
        assert section in s.sections(), f"{name} missing {section}"


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_declares_only_read_only_tools(name: str) -> None:
    """These runbooks recommend; they do not act.

    ``allowed-tools`` is a pre-approval, not a restriction, so this guards what
    a skill pre-approves. The tools must be named the way Claude Code names them
    (``mcp__<server>__<tool>``), or the pre-approval matches nothing.
    """
    s = _skill(name)
    assert s.allowed_tools
    assert set(s.allowed_tools) <= PERMITTED_ALLOWED_TOOLS, s.allowed_tools
    raw = s.frontmatter["allowed-tools"]
    assert isinstance(raw, str) and "," not in raw  # spec: space-separated string


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_only_asks_for_topics_filters_and_tools_that_exist(name: str) -> None:
    """A runbook must not send the agent to a topic slurm-mcp does not have."""
    for doc, text in _skill(name).documents().items():
        topics, filters, tools = surface_references(text)
        assert topics <= set(TOPICS), (doc, topics - set(TOPICS))
        assert all(f in TOPICS[t] for t, f in filters), (doc, filters)
        assert tools <= set(TOOLS), (doc, tools)


@pytest.mark.parametrize("name", SKILL_DIRS)
def test_stays_within_the_spec_size_guidance(name: str) -> None:
    """agentskills.io: keep SKILL.md under 500 lines; move detail to references/."""
    assert len(_skill(name).body.splitlines()) < 500


def test_names_are_unique() -> None:
    names = [s.name for s in load_all()]
    assert len(names) == len(set(names))


def test_every_figure_is_in_the_claims_ledger() -> None:
    """The regression test for the audit's headline finding.

    Scheduler figures were once quoted as "measured on a replayed sacct trace"
    when they came from a synthetic workload in a simulator. Every number in a
    runbook now needs a ledger entry saying what kind of claim it is and, if it
    was measured or documented, where it came from.
    """
    assert check_claims(load_all(), load_claims(default_claims_file())) == []


def test_the_loader_docstring_quotes_no_figures() -> None:
    """Figures belong in runbooks, where the ledger checks them, not in code prose."""
    assert loader_module.__doc__ is not None
    assert figures(loader_module.__doc__) == []


def test_state_save_runbook_does_not_call_every_state_save_failure_loud() -> None:
    """Regression: a hung StateSaveLocation mount is expected to be silent.

    Only the unwritable (permission) case was measured, and only it is loud.
    The runbook must not send a silent failure to the accounting runbook.
    """
    body = _skill("state-save-unwritable").body
    assert "not measured" in body.lower()
    assert "which commands hang" in body.lower()
    assert '"Loud and immediate" versus "silent and hanging"' not in body


def test_partition_runbook_does_not_ask_config_for_partition_limits() -> None:
    """Regression: `config` is `scontrol show config`, which has no partitions."""
    body = _skill("partition-limit-starvation").body
    assert "Query `config` for the partition definition" not in body
    assert "not partition definitions" in body


def test_slinky_runbook_leads_with_the_recorded_failure() -> None:
    body = _skill("slinky-authkey-rotation").body
    assert "does not currently succeed on Slinky v1.2" in body
    assert "compare pod ages" not in body.lower()
    assert "slurm.jwks" in body


def _flat(text: str) -> str:
    """Collapse whitespace, so a regression test survives re-wrapping."""
    return " ".join(text.split())


def _section(body: str, heading: str) -> str:
    """The text under ``heading`` up to the next ``## `` heading."""
    after = body.split(heading, 1)[1]
    return after.split("\n## ", 1)[0]


def test_slinky_runbook_reissues_the_resume_and_resumes_after_rollback() -> None:
    """Regression: the runbook read as one resume, and as "roll back, leave nodes down".

    slinky-gitops@c51903a: "a resume fired before the pod comes back is simply
    lost", so the resume is re-issued until schedulable; and its rollback
    replaces slurmd pods again and resumes them, because a drained cluster is
    "a worse outcome than not having rotated".
    """
    body = _flat(_skill("slinky-authkey-rotation").body)
    assert "re-issue `scontrol update nodename=<node> state=resume` until" in body
    assert "resume_until_schedulable" in body
    assert "restore_previous_and_settle" in body
    escalate = _flat(_section(_skill("slinky-authkey-rotation").body, "## Escalate when"))
    assert "rather than resuming nodes that hold the wrong key" in escalate
    assert "the nodes go DOWN again" in escalate


def test_accounting_runbook_quotes_the_cache_passage_without_reversing_it() -> None:
    """Regression: "first" was dropped, turning "a restart uses the cache" into its opposite.

    accounting.html: the cache is "written by slurmctld to local storage upon
    shutdown and recovered at startup"; only a *first* start has none.
    """
    body = _flat(_skill("accounting-path-stalled").body)
    assert "written by slurmctld to local storage upon shutdown and recovered at startup" in body
    assert "SlurmDBD must be responding when slurmctld is first started" in body
    assert "The cache does not cover a slurmctld start" not in body
    assert "no cache of that data is available at start-up" not in body


def test_accounting_runbook_states_what_happens_at_the_message_cap() -> None:
    """Regression: slurm.conf documents max_dbd_msg_action; the runbook called it unverified.

    Its `exit` option stops slurmctld at the cap, the one documented way an
    accounting stall stops the controller.
    """
    skill = _skill("accounting-path-stalled")
    body = _flat(skill.body)
    assert "is not stated on that page (unverified)" not in body
    assert "slurm.conf.html#OPT_max_dbd_msg_action" in body
    assert "the slurmctld will exit instead of discarding any messages" in body
    steps = _flat(_section(skill.body, "## Steps"))
    assert "SlurmctldParameters" in steps
    escalate = _flat(_section(skill.body, "## Escalate when"))
    assert "under `exit` slurmctld will stop" in escalate


def test_gpu_idle_runbook_reads_sacct_gpuutil_as_a_peak() -> None:
    """Regression: sacct's gres/gpuutil is a high-water mark, so it cannot show a hang.

    sacct.html: TRESUsageIn[Ave|Tot] "represent the average/total of the
    highest watermarks over all ranks in the step"; under sstat they are "at
    the moment the command was run".
    """
    skill = _skill("gpu-allocated-but-idle")
    body = _flat(skill.body)
    assert "high-water mark" in body
    assert "cannot rule out **hung**" in body
    assert "sstat -j <job>.<step> --format=TRESUsageInAve" in body
    not_conclude = _flat(_section(skill.body, "## What not to conclude"))
    assert "non-zero `gres/gpuutil`" in not_conclude
    handoff = _flat(dict(skill.references)["references/operator-handoff.md"])
    assert "highest watermarks" in handoff
    assert "does not say over what time window" not in handoff


def test_state_save_runbook_does_not_call_s06_emulated() -> None:
    """Regression: S06 is "a real permission failure rather than an emulation of one"."""
    body = _flat(_skill("state-save-unwritable").body)
    assert "each a single emulated run" not in body
    assert "S06 is a real permission failure" in body


def test_dcgm_run_times_keep_nvidias_hopper_scope() -> None:
    """Regression: NVIDIA's level-3 times are "measured on Hopper GPU systems"."""
    refs = dict(_skill("gpu-node-drained").references)
    assert "measured on Hopper GPU systems" in _flat(refs["references/operator-handoff.md"])


def test_surface_tool_names_use_the_claude_code_form() -> None:
    assert claude_code_tool_name("slurm_query") == "mcp__slurm-mcp__slurm_query"
    assert {claude_code_tool_name(t) for t in TOOLS} == PERMITTED_ALLOWED_TOOLS


# --- where the skills are found ----------------------------------------------


def test_source_checkout_finds_repo_skills() -> None:
    assert default_skills_dir() == REPO / "skills"
    assert default_claims_file() == REPO / "claims.yaml"


def test_installed_package_data_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A wheel ships skills inside the package; they must be found there."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "claims.yaml").write_text("claims: []\n", encoding="utf-8")
    monkeypatch.setattr(resources, "files", lambda _pkg: tmp_path)
    assert default_skills_dir() == tmp_path / "skills"
    assert default_claims_file() == tmp_path / "claims.yaml"


def test_wheel_is_configured_to_ship_skills_and_ledger() -> None:
    """Regression: the wheel once shipped no SKILL.md, and the CLI crashed."""
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    force = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force["skills"] == "cluster_ops_skills/skills"
    assert force["claims.yaml"] == "cluster_ops_skills/claims.yaml"


def test_plugin_manifests_are_consistent() -> None:
    """Claude Code resolves the plugin by these names; they must agree.

    https://code.claude.com/docs/en/plugin-marketplaces: `name` is the only
    required plugin.json key; a marketplace needs `name`, `owner` and `plugins`;
    keep an entry's name equal to its plugin's manifest name.
    """
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "cluster-ops-skills"
    assert {"name", "owner", "plugins"} <= set(market)
    (entry,) = market["plugins"]
    assert entry["name"] == plugin["name"]
    assert entry["source"] == "."  # the repo root is the plugin root
    assert (REPO / "skills").is_dir()  # the default location Claude Code scans
