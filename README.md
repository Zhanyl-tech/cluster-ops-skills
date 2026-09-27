# cluster-ops-skills

**Operator runbooks for self-managed Slurm and GPU clusters, packaged as
[Agent Skills](https://agentskills.io/specification).** Each one encodes a
diagnosis an operator performs, and — more importantly — the wrong conclusion
that diagnosis invites.

> **v0.2.0, plus unreleased changes** (see [CHANGELOG](CHANGELOG.md)). Eleven
> runbooks, a validator, a claims ledger, and the contract they must satisfy.
> Requires no cluster to inspect or test.

---

## Why the "what not to conclude" section exists

The expensive mistakes on a cluster are not missing information. They are
**wrong confident diagnoses**: recommending a priority-weight change as the fix
for low utilization, or reporting that a storage stall halted scheduling when
jobs were completing throughout.

So every skill here carries three mandatory sections, enforced by the
validator:

- `## Steps` — the diagnosis.
- `## What not to conclude` — the plausible wrong answer, and why it is wrong.
- `## Escalate when` — the point at which an agent should stop and hand off.

An agent that never hands off is worse than one that never starts.

## The runbooks

| skill | the wrong turn it exists to prevent |
|---|---|
| `queue-not-draining` | Treating a full cluster as a broken scheduler, misreading `Priority` and `ReqNodeNotAvail`, and reaching for priority weights first |
| `gpu-node-drained` | Reading the state column instead of the reason — and calling a DOWN node "drained" |
| `accounting-path-stalled` | Diagnosing "scheduling has halted" from a hanging `sacct`. Slurm documents a cache, and its limits; an emulated run saw scheduling continue |
| `state-save-unwritable` | Assuming every state-save failure is loud. The unwritable case was measured loud; a hung mount is expected to be silent and is unmeasured |
| `backfill-not-running` | Comparing sdiag's `Last cycle` (microseconds, execution only) with `bf_max_time` (seconds, including sleeps), and tuning weights before time limits |
| `partition-limit-starvation` | Reporting "no partition limit binds" from a surface that cannot read partition, QOS or association limits |
| `controller-rpc-saturation` | Blaming the largest job, or escalating before reading sdiag's per-user RPC table |
| `fabric-degraded-collectives` | Blaming the fabric for a multi-node slowdown before ruling out NCCL on sockets, a straggler, and placement |
| `gpu-allocated-but-idle` | Concluding the cluster needs more GPUs from allocation figures. Allocated is not utilized |
| `evidence-is-gone` | Naming the most plausible cause after the evidence window has closed |
| `slinky-authkey-rotation` | Trusting a zero exit code or new pods. The recorded rotation on Slinky v1.2 failed; verify by key hash |

## What each runbook rests on

A runbook is only as good as the evidence under it, and that evidence varies a
lot. The benchmark scenarios are in
[slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench): a single-worker
Docker Compose cluster on Slurm 25.11.4, with faults injected into its
containers and no real GPUs.

| runbook | rests on | status of that evidence |
|---|---|---|
| `accounting-path-stalled` | bench S01; Slurm [accounting.html](https://slurm.schedmd.com/accounting.html) | S01 **measured** on an emulated stall (database container paused): one fully probed run, plus a second run that confirmed the queue-depth signal. Mechanism and its limits documented upstream |
| `state-save-unwritable` | bench S06 | **measured**, one run, for a real permission failure only (`chmod 500`). The hung-mount case is not measured |
| `partition-limit-starvation` | bench S08; Slurm accounting.html | S08 **blocked**: the injection was measured *not* to work, because the cluster runs `AccountingStorageEnforce=none` |
| `controller-rpc-saturation` | bench S03; Slurm [sdiag.html](https://slurm.schedmd.com/sdiag.html) | S03 **not measured** |
| `gpu-node-drained` | bench S04, S09; [slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html); [epilog-gpu-validator](https://github.com/Zhanyl-tech/epilog-gpu-validator) | S04, S09 **not measured**; bench GPU telemetry is synthetic |
| `fabric-degraded-collectives` | bench S07; [ib-slurm-exporter](https://github.com/Zhanyl-tech/ib-slurm-exporter); NCCL and linux-rdma docs | S07 **designed, not observed** |
| `evidence-is-gone` | bench S05, S10 | scoring design (abstention earns full credit); **not measured** |
| `queue-not-draining` | Slurm [job_reason_codes.html](https://slurm.schedmd.com/job_reason_codes.html); [slurm-scheduler-lab](https://github.com/Zhanyl-tech/slurm-scheduler-lab) | reason codes documented; lab figures are **simulator output on synthetic workloads**, not Slurm |
| `backfill-not-running` | Slurm sched_config, sdiag and slurm.conf docs; slurm-scheduler-lab | as above: documented mechanism, simulated magnitude |
| `gpu-allocated-but-idle` | Slurm [gres.html](https://slurm.schedmd.com/gres.html); [gpu-reaper](https://github.com/Zhanyl-tech/gpu-reaper) | no bench scenario |
| `slinky-authkey-rotation` | [slinky-gitops](https://github.com/Zhanyl-tech/slinky-gitops); Slurm [authentication.html](https://slurm.schedmd.com/authentication.html) | **measured** on a KinD cluster: the rotation was observed to fail on Slinky v1.2 |

Three runbooks rest on a failure that was actually observed, each on a single
test cluster:

- `accounting-path-stalled`: bench S01, an emulated stall (the database
  container paused), with one fully probed run and a second run that confirmed
  the queue-depth signal.
- `state-save-unwritable`: bench S06, a real `chmod 500` permission failure on
  the emulated single-worker Compose cluster, one run.
- `slinky-authkey-rotation`: slinky-gitops, the rotation observed to fail on
  KinD with Slinky operator v1.2.0 and Slurm 26.05; its CI asserts that
  `make rotate` fails.

The rest encode documented behaviour, a designed scenario, or a tool's design —
which is useful, and is not the same thing.

## What is different here

The Slurm Agent Skills found when this was written —
[pu-shd/slurm-skill](https://github.com/pu-shd/slurm-skill) and
[TianyuDu/SLURM-HPC-AGENT-SKILL](https://github.com/TianyuDu/SLURM-HPC-AGENT-SKILL)
— centre on running work on a cluster: discovering it, validating and
submitting jobs, and monitoring and diagnosing one's own jobs. This set is for
the **operator diagnosing the cluster itself**, and every runbook names the
plausible wrong conclusion next to the right steps.

Treating "stop and hand off" as part of the skill is not unique to this set:
[medzin/sre-runbook-agent-skills](https://github.com/medzin/sre-runbook-agent-skills)
tells its executor to "Stop when steps are ambiguous, required access is
missing, or observed state diverges from the runbook." What this set adds is the
Slurm-specific version: `evidence-is-gone` exists because
[slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench) awards full
credit for abstaining on its deliberately undiagnosable scenarios.

## Quickstart

```bash
make install          # needs Python >= 3.11; on stock macOS: make install PY=python3.12
make list             # the index, as a model would see it
make validate         # every skill against the contract and the claims ledger
make check            # ruff, ruff format, mypy --strict, pytest (coverage >= 90%), validate
make wheel-check      # build the wheel, install it in a throwaway venv, validate from it
```

```bash
cluster-ops-skills show accounting-path-stalled
cluster-ops-skills index                        # JSON: name, description, allowed-tools
cluster-ops-skills --skills-dir ./my-skills validate   # check your own skills
```

## Using the skills

### Claude Code

Skills live in `~/.claude/skills/<name>/SKILL.md` (personal),
`.claude/skills/<name>/SKILL.md` (one project), or a plugin's `skills/`
directory ([Claude Code skills docs](https://code.claude.com/docs/en/skills)).
Either copy them in:

```bash
mkdir -p ~/.claude/skills && cp -R skills/* ~/.claude/skills/
```

(`cp` with several sources needs the target directory to exist already, and a
first-time Claude Code user may not have `~/.claude/skills` yet.)

or install this repository as a plugin. It carries a
`.claude-plugin/plugin.json` and a `marketplace.json` whose single entry points
at the repository root:

```
/plugin marketplace add Zhanyl-tech/cluster-ops-skills
/plugin install cluster-ops-skills@cluster-ops-skills
```

Plugin skills are namespaced, e.g. `/cluster-ops-skills:queue-not-draining`.
The manifests follow the documented format; they have not yet been run through
`claude plugin validate` or installed end to end.

**Install slurm-mcp, and register it under the name `slurm-mcp`.** The runbooks
query the cluster through [slurm-mcp](https://github.com/Zhanyl-tech/slurm-mcp).
Install it from a checkout with its `server` extra, which the `serve`
subcommand needs. Do not `pip install slurm-mcp`: that name on PyPI is a
different package.

```bash
git clone https://github.com/Zhanyl-tech/slurm-mcp && cd slurm-mcp
python3.12 -m venv .venv && .venv/bin/pip install -e ".[server]"   # needs Python >= 3.11

# Against a live cluster, on a host where the Slurm client commands work:
claude mcp add --transport stdio slurm-mcp -- "$PWD/.venv/bin/slurm-mcp" serve
# Or against slurm-mcp's recorded fixtures, with no cluster:
claude mcp add --transport stdio slurm-mcp -- "$PWD/.venv/bin/slurm-mcp" --fixtures serve
```

`--fixtures` is an option of slurm-mcp's top-level parser, so it goes
**before** `serve`: `slurm-mcp serve --fixtures` exits with "unrecognized
arguments", which would register a server that dies on start-up. `$PWD` makes
the command an absolute path, so it does not depend on the virtualenv being on
`PATH` when Claude Code starts the server. Checked on 2026-09-26 from a git
archive of slurm-mcp's pinned commit: installed with `uv pip install -e
".[server]"` (which resolved mcp 2.2.0), `serve --fixtures` exited with that
error, and `--fixtures serve` answered an MCP client that listed its three
tools. The `claude mcp add` lines themselves have not been run.

Claude Code names MCP tools `mcp__<server>__<tool>` after the name you register
([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)), and the skills'
`allowed-tools` use that form with `slurm-mcp`. Registered under any other
name, the skills still work, but their `allowed-tools` match no tool and Claude
Code asks before every call.

Even under the right name the pre-approval is short-lived: `allowed-tools`
"grants permission for the listed tools during the turn that invokes the
skill", and "The grant clears when you send your next message"
([skills docs](https://code.claude.com/docs/en/skills)). So in a multi-turn
diagnosis, later slurm-mcp calls prompt again. To pre-approve them for the
whole session, add an allow rule for the server's tools to your permission
settings, e.g. `.claude/settings.json`
([permissions docs](https://code.claude.com/docs/en/permissions)):

```json
{ "permissions": { "allow": ["mcp__slurm-mcp__*"] } }
```

### claude.ai and the Claude API

Custom skills are uploaded per skill as a zip (claude.ai: Settings > Features;
API: the Skills API), per the
[Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).
The same page says API skills run with **no network access**, and claude.ai's
access varies with settings — so there is no slurm-mcp to query. There the
runbooks are reference guidance only: the `Query` steps cannot run.

## The contract

Enforced by `cluster-ops-skills validate`
([`loader.py`](src/cluster_ops_skills/loader.py)), which CI runs, and tested:

- **Frontmatter is spec-conformant.** Only the keys the
  [spec](https://agentskills.io/specification) defines (claude.ai and the API
  reject any other key); `name` is at most 64 characters of lowercase letters,
  digits and single hyphens, **matches its directory**, and contains no reserved
  word; `name` and `description` contain no XML tags.
- **The description routes.** 80–500 characters and contains "Use when" — the
  description is the only thing a model reads when deciding whether to load the
  skill.
- **All three required sections are present.**
- **The runbook only asks for what exists.** Every topic (`` Query `x` ``),
  filter (`` `x` filtered by `y` ``) and tool name it uses exists on the slurm-mcp
  surface, vendored in [`surface.py`](src/cluster_ops_skills/surface.py) from a
  pinned slurm-mcp commit.
- **Bundled links resolve.** Relative links (e.g. to `references/`) must exist
  and stay inside the skill directory, which is what gets uploaded.
- **Every figure is in the claims ledger.** [`claims.yaml`](claims.yaml) lists
  each number a runbook or reference file quotes, as *measured* (a
  commit-pinned permalink plus the method, and the runbook must link that
  permalink), *documented* (an upstream doc URL the runbook links), or
  *illustrative* (a note saying so). A figure with no entry, a stale entry, or
  an unsourced one fails validation. "Number" means digits, and spelled-out
  cardinals from "two" upward ("ninety seconds", "tens of seconds"). Numbers
  inside code spans, URLs and step markers are not treated as claims. **Not
  checked:** the word "one", which is far more often a pronoun ("the one
  check") than a figure, and ordinals ("a second run"). A figure written that
  way escapes the check.
- **`allowed-tools` pre-approves only the three read-only slurm-mcp tools**, as
  a space-separated string in Claude Code's `mcp__slurm-mcp__<tool>` form.

What the validator **cannot** check: that the prose is right, or that a source
says what the runbook says it says. The ledger makes each figure's source
explicit so a human can check it; it does not check it for them.

### What `allowed-tools` does, and does not, do

In Claude Code, `allowed-tools` **pre-approves** the listed tools, and only for
the turn that invokes the skill: the grant clears at your next message (see
[Using the skills](#claude-code)). It "does not restrict which tools are
available" ([skills docs](https://code.claude.com/docs/en/skills)). The field
is also marked experimental in the spec. So it is not a safety boundary. What
keeps these runbooks read-only is slurm-mcp's **server-side allowlist**, which
refuses mutating commands whatever the agent asks for.

If the agent also has a shell on a host with Slurm credentials, the skills
cannot help you. Claude Code deny rules can add a speed bump, for example in
`.claude/settings.json`:

```json
{
  "permissions": {
    "deny": [
      "Bash(scontrol *)",
      "Bash(scancel *)",
      "Bash(sacctmgr *)",
      "Bash(sdiag *)"
    ]
  }
}
```

Deny whole programs, not subcommands. Claude Code "matches everything before
the first `*` as written", so `Bash(scontrol update *)` would block only
`scontrol update` and leave `scontrol requeue`, `hold`, `delete`, `create`,
`reboot` and `shutdown` open ([scontrol](https://slurm.schedmd.com/scontrol.html)).
`Bash(sdiag *)` covers `sdiag --reset`, which erases the counters
`controller-rpc-saturation` reads. The agent reads Slurm through slurm-mcp, so
it loses nothing here, and you cannot re-allow read-only subcommands anyway:
"An allow rule can't carve an exception out of a deny rule". The permissions
docs also note that a deny rule "doesn't match the same program by path or
inside `sh -c`"
([permissions docs](https://code.claude.com/docs/en/permissions)). The dependable
control is not giving the agent that shell.

## Limitations

- **These are runbooks, not automation.** Nothing here executes anything. They
  are instructions for an agent or a human that has read access to a cluster.
- **Not scored.** Whether loading these changes an agent's diagnostic accuracy
  is an open question, and the harness for answering it is
  [slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench). No such
  measurement has been run, so no claim is made.
- **Thin evidence.** Three runbooks rest on an observed failure, each on a
  single test cluster (the bench's Docker Compose cluster for two, KinD for the
  Slinky rotation); see the evidence table above. Nothing here has been checked
  against a production cluster.
- **Slurm-shaped, on-prem.** These target a self-managed cluster: the
  controller, the accounting path, the fabric, and the fleet. Cloud-managed
  Slurm and the Kubernetes side of a hybrid estate are not covered, beyond the
  Slinky rotation runbook.
- **Written against one tool surface.** Steps name slurm-mcp's topics. Anything
  that surface cannot read — partition and QOS limits, reservations, per-job GPU
  allocation, fabric counters — is handed to a human, not guessed.

## Related

- [slurm-mcp](https://github.com/Zhanyl-tech/slurm-mcp) — the read-only tool
  surface these runbooks are written against.
- [cluster-sre-agent](https://github.com/Zhanyl-tech/cluster-sre-agent) — the
  agent that would load them.
- [slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench) — where
  "does this help?" would have to be proven.

## License

MIT.
