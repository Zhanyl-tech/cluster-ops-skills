# Changelog

All notable changes to this project. Dates are commit dates; no version has
been tagged yet.

## [Unreleased]

Applies the fixes from an audit. The theme: several runbooks said more
than their evidence supports, and the validator could not tell.

### Corrected claims

- **Scheduler figures were mislabelled.** `backfill-not-running`,
  `queue-not-draining` and the `loader.py` docstring called 72.2% → 83.6%
  utilization and 1,913 → 374 min mean wait "measured on a replayed `sacct`
  trace". They are simulator output from slurm-scheduler-lab on a seeded
  *synthetic* workload. Re-running the lab at commit c02b52f reproduces them
  exactly with `--jobs 300 --seed 5` (a setting its README does not show). The
  runbooks now quote the range across seeds 0–9, labelled as simulated, with the
  exact command and `scripts/lab_figures.py` to reproduce it.
- **"Sweeping the priority weights barely moved queue behaviour" was wrong.** In
  the same simulator a single weight moved utilization by up to 20.7 points and
  mean wait by up to 4.27x. The runbooks now say weights *trade* wait against
  utilization, which is why they are not the first fix.
- **"Time limits are the dominant lever"** is now presented as an argument from
  Slurm's documented mechanism, pinned by one lab unit test (two otherwise
  identical three-job workloads), not as a measured ranking.
- **README: "each encodes a failure that has been reproduced"** was true of
  three runbooks, each on a single test cluster: two bench scenarios on the
  emulated Compose cluster (S01, an emulated stall; S06, a real permission
  failure) and the Slinky rotation on KinD. Replaced with a per-runbook evidence
  table (measured / blocked / not measured / designed only).
- **`state-save-unwritable` reversed its source's caveat.** It called every
  `StateSaveLocation` failure "loud and immediate" and made that the first
  discriminator, which would misroute a hung mount to the accounting runbook.
  Now: unwritable (measured, loud) versus hung (expected silent, not measured),
  discriminated by *which commands hang*.
- **`accounting-path-stalled`** now states the scope of the run behind it,
  cites Slurm's documented cache, and adds its documented limits: only a
  *first* slurmctld start has no cache (a restart recovers the one written at
  shutdown), the `MaxDBDMsgs` cap, and what `max_dbd_msg_action` does at the cap.
- **`slinky-authkey-rotation`** now leads with its source's status — the
  rotation "does not currently succeed on Slinky v1.2" — verifies by key hash
  instead of pod age, marks the kubectl steps as operator-only, resumes nodes
  only after the hashes match (re-issuing the resume until schedulable), and
  describes Slurm's `slurm.jwks` multi-key rotation (Slinky chart support
  unverified).
- **`partition-limit-starvation`** asked the `config` topic for partition limits
  it cannot return. It now says which limits this surface cannot read, checks
  `AccountingStorageEnforce`, and no longer filters `queue` by account.
- **`gpu-allocated-but-idle`** asked for GPU counts the surface does not return.
  It now uses `ReqTRES` as a labelled proxy and points at Slurm's native
  `gres/gpuutil` before DCGM, read as a high-water mark (see below).
- **`backfill-not-running`** compared sdiag's `Last cycle` (microseconds,
  execution time only) with `bf_max_time` (seconds, including sleeps). It now
  uses `Last depth cycle` against `Last queue length`, and checks `bf_window`
  and `bf_continue`.
- **`queue-not-draining`** now uses Slurm's definitions of `Priority` and
  `ReqNodeNotAvail`, reads `Resources` and `Priority` together as the capacity
  signal, checks reservations, and gates escalation on ruling out limits,
  reservations, GRES and time-limit fit.
- **`gpu-node-drained`** separated DOWN (`SlurmdTimeout`, `ReturnToService`)
  from DRAIN (validator, human, Prolog/Epilog failure) and gained an operator
  hand-off with NVIDIA-documented commands.
- **`fabric-degraded-collectives`** no longer calls the multi-node asymmetry "the
  diagnosis": it lists NCCL on sockets, a straggler and placement as
  alternatives, notes the bench scenario is designed only, and adds an
  InfiniBand/NCCL hand-off that forbids resetting counters.
- **`controller-rpc-saturation`** reads sdiag's per-user and per-type RPC tables
  before escalating, and labels the job-size comparison as reasoning.
- **Superlatives and "Production"** are gone or marked as the author's
  judgement. The "no runbook set treats stopping as a skill" claim was false and
  is replaced by a sourced comparison.

### Corrected again after a second verification pass

The fixes above were themselves audited against their sources. What that found:

- **`accounting-path-stalled` reversed accounting.html.** It said a slurmctld
  start has no cache and that "a restart during the outage walks straight into
  that case". The page says the cache is "written by slurmctld to local storage
  upon shutdown and recovered at startup"; only a *first* start has none. The
  runbook now quotes the whole passage, and keeps the "do not restart" advice on
  a basis that holds (a restart does nothing about slurmdbd, and the two
  documented failure cases).
- **`accounting-path-stalled` called the behaviour at `MaxDBDMsgs` unverified.**
  slurm.conf documents it under `SlurmctldParameters=max_dbd_msg_action`:
  `discard` (default) purges step, then job-start messages, then loses records;
  `exit` makes slurmctld exit. The runbook now reads that setting, and says
  "scheduling carries on" holds under the default only.
- **`gpu-allocated-but-idle` treated sacct's `gres/gpuutil` as a utilization
  reading.** sacct.html says `TRESUsageInAve` is an average of "the highest
  watermarks" in the step, so a job that ran and then hung still shows its
  peak. It can confirm "never started" and cannot rule out "hung". `sstat` is
  now the point-in-time read for running steps (whether it carries
  `gres/gpuutil` is unverified), and the hand-off file no longer says the page
  is silent on the window.
- **`slinky-authkey-rotation` implied one resume, and "roll back rather than
  resuming nodes".** Its source re-issues the resume until a node is
  schedulable ("a resume fired before the pod comes back is simply lost"), and
  its rollback cycles slurmd and resumes again. The runbook now does both.
- **README evidence summary** left out the Slinky rotation (which its own table
  marks measured), said S01 ran once (it records a second run for the queue
  depth), and called S06 emulated (S06: "a real permission failure rather than
  an emulation of one"). `state-save-unwritable` and the ledger's methods now
  say the same.
- **DCGM level-3 run times** now carry NVIDIA's "measured on Hopper GPU
  systems" scope, in the hand-off file and the ledger entry.
- **README slurm-mcp registration** failed as its comment suggested:
  `slurm-mcp serve --fixtures` exits with "unrecognized arguments", because the
  flag belongs before the subcommand. The README now shows both forms, an
  install step (from a checkout, with the `server` extra; the `slurm-mcp` name
  on PyPI is a different package), and an absolute command path.
- **README: `allowed-tools` pre-approves only for the turn that invokes the
  skill**, per the skills docs, not "while the skill is active". It now suggests
  a session-wide `mcp__slurm-mcp__*` allow rule instead.
- **README deny rules** named subcommands (`Bash(scontrol update *)`), which
  left `scontrol requeue`, `delete`, `hold`, `shutdown` and `sdiag --reset`
  open. The example now denies `scontrol` and `sdiag` outright.
- **README copy-in install** failed when `~/.claude/skills` did not exist yet;
  it now runs `mkdir -p` first.
- New `tests/test_readme.py` pins these README commands and the evidence
  summary against the table, and new runbook regression tests pin the rest.

### Validator and CLI

- Frontmatter now checked against the Agent Skills spec: only spec keys, name
  at most 64 characters, no reserved words, no XML tags, typed optional fields.
- `allowed-tools` is now checked by `validate()` itself (it was only in a test),
  must be space-separated, and uses Claude Code's `mcp__slurm-mcp__<tool>` names
  — the bare `slurm_query` form matched no tool, so it pre-approved nothing. The
  README now says plainly that the field pre-approves and does not restrict.
- New: every topic, filter and tool a runbook names must exist on a vendored,
  commit-pinned copy of the slurm-mcp surface (`surface.py`).
- New: relative links must resolve and stay inside the skill directory.
- New: `claims.yaml`, a ledger every quoted figure must appear in, as measured
  (commit-pinned permalink and method), documented (upstream URL) or
  illustrative. The old "any percentage plus any GitHub link" rule accepted
  `99.9%` cited to an unrelated repository; the floor now requires a recognised
  source.
- The ledger check now detects spelled-out numbers from "two" upward ("ninety
  seconds", "tens of seconds"). Before, writing a figure in words got it past
  the check: "no self-heal in ninety seconds of watching" and S01's "tens of
  seconds" had no entry. Both now have measured entries, and every other
  spelled-out count has an illustrative one. "One" and ordinals are still not
  detected, and the README says so.
- One malformed SKILL.md no longer crashes every command: `validate` reports it
  as a FAIL line, `show` still serves the good skills, `list`/`index` exit
  non-zero. YAML errors are caught. Errors go to stderr.
- New `--skills-dir` and `--claims` options.

### Packaging, CI and tooling

- The wheel shipped no skills, so an installed `cluster-ops-skills list`
  crashed. Skills and the ledger are now package data, found via
  `importlib.resources` with a fallback to the repo root.
- CI: `permissions: contents: read`, actions pinned by SHA, a coverage floor of
  90%, the upstream `skills-ref` validator, a job that builds the wheel and runs
  the CLI from a clean venv, and a weekly link check.
- `make install` checks for Python 3.11+ before doing anything and rebuilds a
  venv left behind by a too-old interpreter; new `make wheel-check`.
- Claude Code plugin and marketplace manifests (`.claude-plugin/`), and README
  instructions for Claude Code, claude.ai and the API.
- Operator hand-off references for the GPU and fabric runbooks
  (`references/operator-handoff.md`), each command linked to NVIDIA or
  linux-rdma documentation.

## [0.2.0] — 2026-08-23

- Six more runbooks targeting on-prem Slurm operations, for eleven in total
  (commit e8673a8).

## [0.1.0] — 2026-08-23

- Five cluster runbooks as loadable Agent Skills, the validator and its tests
  (commit 0aec3e9).
