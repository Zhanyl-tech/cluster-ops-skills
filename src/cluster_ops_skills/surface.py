"""The slurm-mcp tool surface these runbooks are written against, vendored.

A runbook that says "query `partitions`" when no such topic exists fails
silently at the worst moment: the agent gets an error, or worse, reads a
different topic and reports that no limit binds. So the topics, their filters
and the tool names are copied here and every SKILL.md is checked against them.

Copied from slurm-mcp at a pinned commit, because that is what a reader can
check. To re-verify after slurm-mcp changes::

    git -C slurm-mcp show <commit>:src/slurm_mcp/topics.py   # TOPICS, filters
    git -C slurm-mcp show <commit>:src/slurm_mcp/server.py   # tool names

then update :data:`SLURM_MCP_COMMIT` and the tables below together.
"""

from __future__ import annotations

#: slurm-mcp commit the tables below were copied from (its main at the time).
SLURM_MCP_COMMIT = "b917154ca7a7be01ac6cb457a5869c8f25c2003a"
SLURM_MCP_TOPICS_URL = (
    f"https://github.com/Zhanyl-tech/slurm-mcp/blob/{SLURM_MCP_COMMIT}/src/slurm_mcp/topics.py"
)

#: The three MCP tools slurm-mcp exposes (server.py ``tool_definitions``).
TOOLS: tuple[str, ...] = ("slurm_overview", "slurm_query", "slurm_describe")

#: ``slurm_query`` topics and the filters each accepts (topics.py ``TOPICS``).
#: Anything not listed here -- partition definitions, QOS or association
#: limits, per-job GPU allocation -- is not readable through this surface, and
#: a runbook must say so rather than ask for it.
TOPICS: dict[str, tuple[str, ...]] = {
    "queue": ("user", "partition", "state"),
    "nodes": ("partition", "state"),
    "accounting": ("user", "starttime", "endtime", "state"),
    "priority": ("user", "partition"),
    "fairshare": ("user", "account"),
    "diagnostics": (),
    "config": (),
}

#: The server name the README tells users to register slurm-mcp under in
#: Claude Code. Claude Code names MCP tools ``mcp__<server>__<tool>`` after the
#: name the user registered, so ``allowed-tools`` only pre-approves anything if
#: the registration uses this exact name.
#: https://code.claude.com/docs/en/mcp
CLAUDE_CODE_SERVER_NAME = "slurm-mcp"


def claude_code_tool_name(tool: str) -> str:
    """The name Claude Code gives ``tool`` when slurm-mcp is registered as documented."""
    return f"mcp__{CLAUDE_CODE_SERVER_NAME}__{tool}"


#: The only values a skill's ``allowed-tools`` may contain. All three tools are
#: read-only by slurm-mcp's own server-side guard; ``allowed-tools`` itself
#: restricts nothing (it is a pre-approval), so this list is about not
#: pre-approving anything that could act, not about enforcement.
PERMITTED_ALLOWED_TOOLS: frozenset[str] = frozenset(claude_code_tool_name(t) for t in TOOLS)
