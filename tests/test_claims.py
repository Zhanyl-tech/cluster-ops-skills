"""The claims ledger: every figure in a runbook is accounted for, and sourced.

The ledger is the fix for figures that drifted from "synthetic workload in a
simulator" to "measured on a replayed trace" without anything noticing. These
tests show each ledger rule rejecting the thing it exists to reject.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cluster_ops_skills.loader import (
    Claim,
    InvalidSkill,
    Skill,
    check_claims,
    figures,
    load_claims,
    parse,
)
from conftest import GOOD_BODY, WriteSkill

PERMALINK = (
    "https://github.com/Zhanyl-tech/slurm-rca-bench/blob/"
    "469ea760de677295a833f709b7713f06e36abff2/scenarios/S01/scenario.yaml"
)
DOC = "https://slurm.schedmd.com/sdiag.html"


def _tokens(text: str) -> list[str]:
    return [t for _, t in figures(text)]


# --- what counts as a figure ----------------------------------------------------


def test_finds_the_figures_a_reader_would_take_as_claims() -> None:
    text = "Utilization went 72.2% → 83.6%; wait 1,913 → 374 min; queue size 6 at t+840s."
    assert _tokens(text) == ["72.2", "83.6", "1,913", "374", "6", "840"]


def test_ignores_code_urls_man_pages_list_markers_and_identifiers() -> None:
    text = (
        "1. Run `dcgmi diag -r 3` and read ibstat(8).\n"
        "2. See https://example.org/v2/page?id=7 and [x](https://a.b/c/9).\n"
        "Scenario S01 on Slinky v1.2, commit c02b52f.\n"
    )
    assert _tokens(text) == []


def test_keeps_fenced_timelines() -> None:
    """The measured timelines live in fenced blocks, so those are not skipped."""
    assert _tokens("```\nt+60s  DBD Agent queue size 1\n```\n") == ["60", "1"]


def test_finds_spelled_out_numbers() -> None:
    """Regression: "ninety seconds of watching" was a measured figure the ledger missed.

    Spelling a number out must not be a way round the check.
    """
    text = (
        "No self-heal in ninety seconds. Latency rose to tens of seconds; the two "
        "jobs ran. Three failures out of forty; a twelve-hour run; hundreds of jobs."
    )
    assert _tokens(text) == ["ninety", "tens", "two", "Three", "forty", "twelve", "hundreds"]


def test_spelled_out_and_digit_figures_come_back_in_text_order() -> None:
    assert _tokens("two runs reached 6 at t+180s") == ["two", "6", "180"]


@pytest.mark.parametrize(
    "text",
    [
        "the one check that crossed the boundary",  # "one" is excluded: mostly a pronoun
        "a second run; first started; read it twice",  # ordinals and multiplicatives
        "often, attend, tenses, tension, network",  # number words inside other words
        "tens, but not followed by of",  # "tens" only counts in "tens of"
        "Run `dcgmi diag -r two` and see [x](https://a.b/three).",  # code and link targets
        "the node-two label and seven_up",  # parts of identifiers
    ],
)
def test_ignores_one_ordinals_and_lookalikes(text: str) -> None:
    assert _tokens(text) == []


# --- check_claims ------------------------------------------------------------------


def _skill_with(write_skill: WriteSkill, extra_body: str) -> list[Skill]:
    return [parse(write_skill(body=GOOD_BODY + "\n" + extra_body + "\n"))]


def test_uncovered_figure_is_a_problem(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Utilization reached 83.6%.")
    problems = check_claims(skills, [])
    assert any("figure '83.6' has no claims-ledger entry" in p for p in problems)


def test_uncovered_spelled_out_figure_is_a_problem(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "No self-heal in ninety seconds of watching.")
    problems = check_claims(skills, [])
    assert any("figure 'ninety' has no claims-ledger entry" in p for p in problems)


def test_covered_spelled_out_figure_passes(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, f"No self-heal in ninety seconds ([src]({PERMALINK})).")
    claim = Claim("x", "ninety seconds", "measured", source=PERMALINK, method="watched it")
    assert check_claims(skills, [claim]) == []


def test_covered_measured_figure_passes(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, f"Queue size 6 at t+840s ([S01]({PERMALINK})).")
    claim = Claim("x", "Queue size 6 at t+840s", "measured", source=PERMALINK, method="ran it")
    assert check_claims(skills, [claim]) == []


def test_matching_ignores_line_wrapping(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, f"Queue size\n6 at t+840s ([S01]({PERMALINK})).")
    claim = Claim("x", "Queue size 6 at t+840s", "measured", source=PERMALINK, method="ran it")
    assert check_claims(skills, [claim]) == []


def test_measured_needs_a_commit_pinned_permalink(write_skill: WriteSkill) -> None:
    """A branch link lets the number change underneath the runbook that quotes it."""
    unpinned = "https://github.com/Zhanyl-tech/slurm-scheduler-lab"
    skills = _skill_with(write_skill, f"Reached 83.6% ([lab]({unpinned})).")
    claim = Claim("x", "Reached 83.6%", "measured", source=unpinned, method="ran it")
    problems = check_claims(skills, [claim])
    assert any("commit-pinned permalink" in p for p in problems)


def test_measured_needs_a_method(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, f"Reached 83.6% ([S01]({PERMALINK})).")
    claim = Claim("x", "Reached 83.6%", "measured", source=PERMALINK)
    problems = check_claims(skills, [claim])
    assert any("needs 'method'" in p for p in problems)


def test_source_must_be_linked_from_the_runbook(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Reached 83.6% somewhere.")
    claim = Claim("x", "Reached 83.6%", "measured", source=PERMALINK, method="ran it")
    problems = check_claims(skills, [claim])
    assert any("must link its source" in p for p in problems)


def test_documented_needs_an_upstream_doc(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Default is 500 (https://example.com/doc).")
    claim = Claim("x", "Default is 500", "documented", source="https://example.com/doc")
    problems = check_claims(skills, [claim])
    assert any("upstream doc URL" in p for p in problems)


def test_documented_with_upstream_doc_passes(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, f"Default is 500 ({DOC}).")
    claim = Claim("x", "Default is 500", "documented", source=DOC)
    assert check_claims(skills, [claim]) == []


def test_illustrative_needs_a_note(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Say a 512-node job.")
    problems = check_claims(skills, [Claim("x", "a 512-node job", "illustrative")])
    assert any("needs a 'note'" in p for p in problems)


def test_unknown_kind_is_a_problem(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Say a 512-node job.")
    claim = Claim("x", "a 512-node job", "vibes", note="n")
    problems = check_claims(skills, [claim])
    assert any("kind 'vibes'" in p for p in problems)


def test_stale_entry_is_a_problem(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "No figures here.")
    claim = Claim("x", "a 512-node job", "illustrative", note="n")
    problems = check_claims(skills, [claim])
    assert any("text not found" in p for p in problems)


def test_ambiguous_entry_is_a_problem(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "Up to 5 jobs. Up to 5 jobs.")
    claim = Claim("x", "Up to 5 jobs", "illustrative", note="n")
    problems = check_claims(skills, [claim])
    assert any("occurs 2 times" in p for p in problems)


def test_entry_for_missing_skill_or_file(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "No figures here.")
    claims = [
        Claim("nope", "x", "illustrative", note="n"),
        Claim("x", "x", "illustrative", file="references/none.md", note="n"),
    ]
    problems = check_claims(skills, claims)
    assert sum("missing skill or file" in p for p in problems) == 2


def test_reference_files_are_covered_too(write_skill: WriteSkill) -> None:
    p = write_skill()
    (p.parent / "references").mkdir()
    (p.parent / "references" / "r.md").write_text("Takes 35 minutes.\n", encoding="utf-8")
    problems = check_claims([parse(p)], [])
    assert any("x/references/r.md:1: figure '35'" in q for q in problems)


def test_reports_the_file_line_of_an_uncovered_figure(write_skill: WriteSkill) -> None:
    p = write_skill(body="# T\n\nline three has 42 in it\n")
    problems = check_claims([parse(p)], [])
    # frontmatter is 4 lines, so the body's third line is line 7 of SKILL.md
    assert any("x/SKILL.md:7: figure '42'" in q for q in problems)


# --- load_claims -------------------------------------------------------------------


def _ledger(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "claims.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_a_ledger(tmp_path: Path) -> None:
    p = _ledger(tmp_path, "claims:\n  - {skill: x, text: '5 jobs', kind: illustrative, note: n}\n")
    assert load_claims(p) == [Claim("x", "5 jobs", "illustrative", note="n")]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("claims: [unclosed\n", "cannot load"),
        ("- just a list\n", "must be a mapping with a 'claims' list"),
        ("claims:\n  - not a mapping\n", "must be a mapping"),
        ("claims:\n  - {skill: x, text: t, kind: measured, colour: red}\n", "unknown keys"),
        ("claims:\n  - {skill: x, kind: measured}\n", "non-empty string 'text'"),
        ("claims:\n  - {skill: x, text: t, kind: measured, method: 5}\n", "must be a string"),
    ],
)
def test_rejects_malformed_ledgers(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(InvalidSkill, match=message):
        load_claims(_ledger(tmp_path, text))


def test_missing_ledger_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidSkill, match="cannot load"):
        load_claims(tmp_path / "absent.yaml")


def test_whitespace_only_entry_matches_nothing(write_skill: WriteSkill) -> None:
    skills = _skill_with(write_skill, "No figures here.")
    problems = check_claims(skills, [Claim("x", "   ", "illustrative", note="n")])
    assert any("text not found" in p for p in problems)
