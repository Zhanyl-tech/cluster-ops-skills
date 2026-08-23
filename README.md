# cluster-ops-skills

**Production HPC and GPU cluster runbooks, packaged as loadable
[Agent Skills](https://www.anthropic.com/news/skills).** Each one encodes a
diagnosis an operator actually performs, and — more importantly — the wrong
conclusions that diagnosis invites.

> **v0.1.0.** Five runbooks, a validator, and the contract they must satisfy.
> Requires no cluster to inspect or test.

---

## Why the "what not to conclude" section exists

The expensive mistakes on a cluster are not missing information. They are
**wrong confident diagnoses**: recommending a priority-weight change that
measurement shows does nothing, or reporting that a storage stall halted
scheduling when jobs were completing throughout.

So every skill here carries three mandatory sections, enforced by the
validator:

- `## Steps` — the diagnosis.
- `## What not to conclude` — the plausible wrong answer, and why it is wrong.
- `## Escalate when` — the point at which an agent should stop and hand off.

An agent that never hands off is worse than one that never starts.

## The runbooks

| skill | the wrong turn it exists to prevent |
|---|---|
| `queue-not-draining` | Treating a full cluster as a broken scheduler, and tuning priority weights that measurement shows barely matter |
| `gpu-node-drained` | Reading the state column instead of the drain reason — a validator, a human and a kernel panic all look identical there |
| `accounting-path-stalled` | Diagnosing "scheduling has halted" from a hanging `sacct`. Measured: it has not |
| `backfill-not-running` | Recommending priority weights instead of time-limit accuracy |
| `slinky-authkey-rotation` | Trusting a zero exit code. `kubectl rollout restart` silently skips Slinky's `NodeSet`-owned nodes |

Every measured figure in these runbooks links to the repo that measured it. The
validator fails a skill that quotes a percentage without a source, because a
number without a source is the thing this whole set of repos argues against.

## Quickstart

```bash
make install
make list        # the index, as a model would see it
make validate    # every skill against the contract
make check       # ruff, ruff format, mypy --strict, pytest
```

```bash
cluster-ops-skills show accounting-path-stalled
cluster-ops-skills index        # JSON, for loading into an agent
```

## The contract

Enforced in [`loader.py`](src/cluster_ops_skills/loader.py) and tested:

- YAML frontmatter with `name` and `description`;
- `name` is lowercase-with-hyphens and **matches its directory**, or the skill
  loads under the wrong key;
- the description is 80–500 characters and contains "Use when", because the
  description is the only thing a model reads when deciding whether to load the
  skill — a description that does not say *when* is dead weight in the index;
- all three required sections are present;
- any percentage in the body is accompanied by a link to its source;
- `allowed-tools` names only read-only tools from
  [slurm-mcp](https://github.com/Zhanyl-tech/slurm-mcp). These runbooks
  recommend; they do not act.

## Limitations

- **These are runbooks, not automation.** Nothing here executes anything. They
  are instructions for an agent or a human that has read access to a cluster.
- **Not scored.** Whether loading these changes an agent's diagnostic accuracy
  is an open question, and the harness for answering it is
  [slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench). No such
  measurement has been run, so no claim is made.
- **Slurm-shaped.** The Kubernetes side of a hybrid fleet is not covered yet.
- **Five runbooks is a starting set**, chosen because each encodes a failure
  already measured elsewhere in these repos rather than one imagined for the
  purpose.

## Related

- [slurm-mcp](https://github.com/Zhanyl-tech/slurm-mcp) — the read-only tool
  surface these runbooks are written against.
- [cluster-sre-agent](https://github.com/Zhanyl-tech/cluster-sre-agent) — the
  agent that would load them.
- [slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench) — where
  "does this help?" would have to be proven.

## License

MIT.
