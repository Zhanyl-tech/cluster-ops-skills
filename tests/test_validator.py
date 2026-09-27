"""The validator must actually reject bad input, one rule at a time.

Each rule the README says is enforced has a test here that feeds it something
that breaks exactly that rule and checks the right problem is reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cluster_ops_skills.loader import InvalidSkill, load_all, load_report, parse, validate
from conftest import GOOD_BODY, GOOD_DESC, TOOLS, WriteSkill, skill_text


def _problems(path: Path) -> list[str]:
    return validate(parse(path))


def _has(problems: list[str], fragment: str) -> bool:
    return any(fragment in p for p in problems)


# --- parse-time failures ------------------------------------------------------


def test_rejects_missing_frontmatter(write_skill: WriteSkill) -> None:
    with pytest.raises(InvalidSkill, match="missing YAML frontmatter"):
        parse(write_skill(text="# no frontmatter\n"))


def test_rejects_missing_required_keys(write_skill: WriteSkill) -> None:
    with pytest.raises(InvalidSkill, match="frontmatter missing"):
        parse(write_skill(text="---\nname: x\n---\nbody\n"))


def test_rejects_invalid_yaml_as_invalid_skill(write_skill: WriteSkill) -> None:
    """A YAML error must surface as InvalidSkill, not an uncaught yaml exception."""
    with pytest.raises(InvalidSkill, match="not valid YAML"):
        parse(write_skill(text="---\nname: [unclosed\n---\nbody\n"))


def test_rejects_non_mapping_frontmatter(write_skill: WriteSkill) -> None:
    with pytest.raises(InvalidSkill, match="must be a mapping"):
        parse(write_skill(text="---\n- a\n- b\n---\nbody\n"))


def test_rejects_non_string_name(write_skill: WriteSkill) -> None:
    with pytest.raises(InvalidSkill, match="must be a string"):
        parse(write_skill(text=f"---\nname: 12\ndescription: {GOOD_DESC}\n---\nbody\n"))


def test_rejects_unreadable_file(write_skill: WriteSkill) -> None:
    p = write_skill()
    p.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(InvalidSkill, match="cannot read"):
        parse(p)


def test_rejects_unreadable_reference(write_skill: WriteSkill) -> None:
    p = write_skill()
    (p.parent / "references").mkdir()
    (p.parent / "references" / "r.md").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(InvalidSkill, match="cannot read"):
        parse(p)


# --- the name -----------------------------------------------------------------


def test_rejects_name_directory_mismatch(write_skill: WriteSkill) -> None:
    p = write_skill("actual-dir", name="other-name")
    assert _has(_problems(p), "does not match directory")


@pytest.mark.parametrize("bad", ["Upper-case", "double--hyphen", "-leading", "under_score"])
def test_rejects_malformed_name(write_skill: WriteSkill, bad: str) -> None:
    p = write_skill(bad, name=bad)
    assert _has(_problems(p), "lowercase letters, digits and single hyphens")


def test_rejects_name_over_64_chars(write_skill: WriteSkill) -> None:
    long = "a" * 70
    assert _has(_problems(write_skill(long, name=long)), "at most 64")


def test_rejects_reserved_word_in_name(write_skill: WriteSkill) -> None:
    assert _has(_problems(write_skill("claude-helper", name="claude-helper")), "reserved word")


# --- the description ------------------------------------------------------------


def test_rejects_description_without_use_when(write_skill: WriteSkill) -> None:
    desc = (
        "A description comfortably long enough to clear the length floor "
        "but which never states the trigger condition."
    )
    assert _has(_problems(write_skill(description=desc)), "Use when")


def test_rejects_short_description(write_skill: WriteSkill) -> None:
    assert _has(_problems(write_skill(description="Use when short.")), "cannot say when to load")


def test_rejects_long_description(write_skill: WriteSkill) -> None:
    desc = "Use when " + "x" * 600
    assert _has(_problems(write_skill(description=desc)), "bloats the index")


def test_rejects_xml_tag_in_description(write_skill: WriteSkill) -> None:
    desc = GOOD_DESC + " <b>bold</b>"
    assert _has(_problems(write_skill(description=desc)), "XML tag")


# --- other frontmatter keys -------------------------------------------------------


def test_rejects_keys_outside_the_spec(write_skill: WriteSkill) -> None:
    """claude.ai upload and the Skills API fail hard on these."""
    p = write_skill(extra="argument-hint: '[node]'\n")
    assert _has(_problems(p), "not in the Agent Skills spec")


def test_rejects_bad_compatibility(write_skill: WriteSkill) -> None:
    p = write_skill(extra=f"compatibility: {'x' * 501}\n")
    assert _has(_problems(p), "compatibility must be")


def test_rejects_non_string_metadata(write_skill: WriteSkill) -> None:
    p = write_skill(extra="metadata:\n  version: 2\n")
    assert _has(_problems(p), "metadata must map")


def test_rejects_non_string_license(write_skill: WriteSkill) -> None:
    p = write_skill(extra="license: [MIT]\n")
    assert _has(_problems(p), "license must be a string")


def test_accepts_the_optional_spec_keys(write_skill: WriteSkill) -> None:
    extra = (
        "license: MIT\ncompatibility: Needs slurm-mcp\n"
        "metadata:\n  version: '1'\n"
        f"allowed-tools: {TOOLS}\n"
    )
    assert _problems(write_skill(extra=extra)) == []


# --- allowed-tools ------------------------------------------------------------------


def test_rejects_non_read_only_tools(write_skill: WriteSkill) -> None:
    """The audit's scratch case: `Bash, kubectl_delete` used to pass."""
    p = write_skill(extra="allowed-tools: Bash kubectl_delete\n")
    problems = _problems(p)
    assert _has(problems, "not the read-only slurm-mcp tools")
    assert _has(problems, "Bash")


def test_rejects_bare_tool_names_that_match_nothing(write_skill: WriteSkill) -> None:
    """`slurm_query` alone matches no tool in Claude Code, so it pre-approves nothing."""
    p = write_skill(extra="allowed-tools: slurm_query\n")
    assert _has(_problems(p), "not the read-only slurm-mcp tools")


def test_rejects_comma_separated_tools(write_skill: WriteSkill) -> None:
    p = write_skill(
        extra="allowed-tools: mcp__slurm-mcp__slurm_query, mcp__slurm-mcp__slurm_overview\n"
    )
    assert _has(_problems(p), "space-separated, not comma-separated")


def test_rejects_yaml_list_tools(write_skill: WriteSkill) -> None:
    p = write_skill(extra="allowed-tools:\n  - mcp__slurm-mcp__slurm_query\n")
    s = parse(p)
    assert s.allowed_tools == ("mcp__slurm-mcp__slurm_query",)
    assert _has(validate(s), "must be a space-separated string")


def test_parses_space_separated_tools(write_skill: WriteSkill) -> None:
    s = parse(write_skill(extra=f"allowed-tools: {TOOLS}\n"))
    assert s.allowed_tools == tuple(TOOLS.split())


# --- body ------------------------------------------------------------------------------


def test_rejects_missing_sections(write_skill: WriteSkill) -> None:
    problems = _problems(write_skill(body="# T\n## Steps\n1. x\n"))
    assert _has(problems, "What not to conclude")
    assert _has(problems, "Escalate when")


def test_rejects_uncited_percentage(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\nUtilization went to 83.6% after the change.\n"
    assert _has(_problems(write_skill(body=body)), "links no source")


def test_rejects_percentage_cited_to_an_unrelated_site(write_skill: WriteSkill) -> None:
    """The audit's scratch case: any github.com link used to count as a source."""
    body = GOOD_BODY + "\n99.9% uptime, see https://github.com/torvalds/linux\n"
    assert _has(_problems(write_skill(body=body)), "links no source")


def test_accepts_percentage_cited_to_upstream_docs(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\n50% of the time, per https://slurm.schedmd.com/sdiag.html\n"
    assert _problems(write_skill(body=body)) == []


def test_rejects_unknown_topic(write_skill: WriteSkill) -> None:
    """Regression: a runbook asked `config` for partition limits it cannot return."""
    body = GOOD_BODY + "\nQuery `partitions` for MaxTime.\n"
    assert _has(_problems(write_skill(body=body)), "topic 'partitions'")


def test_rejects_unknown_topic_in_a_chain(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\nQuery `nodes` and `qos`.\n"
    assert _has(_problems(write_skill(body=body)), "topic 'qos'")


def test_rejects_filter_a_topic_does_not_accept(write_skill: WriteSkill) -> None:
    """Regression: `queue` cannot be filtered by account."""
    body = GOOD_BODY + "\nQuery `queue` filtered by `account`.\n"
    assert _has(_problems(write_skill(body=body)), "filters topic 'queue' by 'account'")


def test_rejects_unknown_tool(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\nCall `slurm_exec` to fix it.\n"
    assert _has(_problems(write_skill(body=body)), "names tool 'slurm_exec'")


def test_accepts_known_topics_filters_and_tools(write_skill: WriteSkill) -> None:
    body = (
        GOOD_BODY + "\nCall `slurm_overview`. Query `nodes` and `queue`. "
        "Query `accounting` filtered by `user`.\n"
    )
    assert _problems(write_skill(body=body)) == []


def test_rejects_link_to_missing_reference(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\nSee [the hand-off](references/missing.md).\n"
    assert _has(_problems(write_skill(body=body)), "missing file")


def test_rejects_link_leaving_the_skill(write_skill: WriteSkill) -> None:
    """A link to a sibling skill works here and breaks once the skill is uploaded alone."""
    write_skill("other")
    body = GOOD_BODY + "\nSee [other](../other/SKILL.md).\n"
    assert _has(_problems(write_skill(body=body)), "leaves the skill directory")


def test_checks_reference_files_too(write_skill: WriteSkill) -> None:
    body = GOOD_BODY + "\nSee [the hand-off](references/handoff.md).\n"
    p = write_skill(body=body)
    (p.parent / "references").mkdir()
    (p.parent / "references" / "handoff.md").write_text(
        "Query `partitions` first.\n", encoding="utf-8"
    )
    problems = _problems(p)
    assert _has(problems, "references/handoff.md: asks for topic 'partitions'")
    assert not _has(problems, "missing file")


def test_accepts_a_well_formed_skill(write_skill: WriteSkill) -> None:
    assert _problems(write_skill(extra=f"allowed-tools: {TOOLS}\n")) == []


# --- loading a directory -----------------------------------------------------------


def test_empty_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidSkill, match="no skills found"):
        load_all(tmp_path)


def test_missing_directory_is_reported(tmp_path: Path) -> None:
    skills, errors = load_report(tmp_path / "nope")
    assert skills == [] and "no skills found" in errors[0]


def test_one_bad_skill_does_not_hide_the_others(write_skill: WriteSkill, tmp_path: Path) -> None:
    write_skill("good-one", name="good-one")
    write_skill("broken", text="no frontmatter\n")
    skills, errors = load_report(tmp_path / "skills")
    assert [s.name for s in skills] == ["good-one"]
    assert len(errors) == 1 and "broken" in errors[0]
    with pytest.raises(InvalidSkill):
        load_all(tmp_path / "skills")


def test_skill_text_helper_round_trips(write_skill: WriteSkill) -> None:
    assert parse(write_skill(text=skill_text())).name == "x"
