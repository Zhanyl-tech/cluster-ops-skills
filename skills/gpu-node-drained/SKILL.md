---
name: gpu-node-drained
description: Investigate a Slurm node in down, drain or drng state on a GPU cluster. Use when a node disappears from the available pool, when capacity drops unexpectedly, or when asked why a specific node is not accepting jobs. Reads the state and the reason before assuming hardware.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# GPU node drained

## DOWN and DRAIN are different mechanisms

Two different things take a node out of the pool, and they recover differently
([slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html)):

- **DOWN** — slurmctld marks a node DOWN when slurmd does not respond within
  `SlurmdTimeout` (default 300 seconds), and for other reasons such as an
  unexpected reboot. Whether it comes back on its own depends on
  `ReturnToService`: with the default, `0`, it stays DOWN "until a system
  administrator explicitly changes its state"; with `1` it returns on a valid
  registration only if it was marked DOWN for not responding; with `2` it
  returns on a valid registration whatever the reason.
- **DRAIN / DRAINING** (`drain`, `drng`) — something asked the node to stop
  taking new work, and left a free-text reason. Candidates: an **epilog
  validator** that found a persistent GPU fault; a **human** draining for
  maintenance who did not undrain; a failed **Prolog** or **Epilog** — Slurm sets
  the node to DRAIN when either returns non-zero, and requeues the job on a
  Prolog failure ([prolog_epilog.html](https://slurm.schedmd.com/prolog_epilog.html)).
  A Prolog failure usually means configuration, not hardware.

In every case the state column says little; the reason says which of these
happened. They need entirely different responses.

## Steps

1. Query `nodes` and collect every node not in `idle`, `mixed`, or `allocated`.
   Note which are `down`, which are `drain`/`drng`, and which carry a trailing
   `*`: the node "is presently not responding" and will be placed DOWN if it
   stays that way ([sinfo.html](https://slurm.schedmd.com/sinfo.html)).
2. Read the reason column verbatim. Do not paraphrase it into a diagnosis.
3. For a DOWN node, query `config` and read `SlurmdTimeout` and
   `ReturnToService`, so you can say whether it will return by itself.
4. If the reason names a GPU and an error class (ECC, Xid, fell off the bus),
   treat it as a suspected hardware fault and record which GPU index — a
   persistent fault on one device is a different ticket from a node-wide
   failure. An Xid alone is not proof of hardware: NVIDIA says it can also be a
   driver or application problem (see the hand-off). GPU state itself is
   not on this surface; hand the node to an operator with
   [references/operator-handoff.md](references/operator-handoff.md).
5. Query `queue` for jobs pending with `ReqNodeNotAvail` that need this node, to
   establish blast radius.
6. Check whether other nodes show the same reason. One node points at hardware;
   several nodes with an identical reason in a short window usually point at a
   driver or configuration change (author's judgement, not measured).

## What not to conclude

- **Do not recommend resuming the node.** This surface is read-only by design,
  and a node drained for a persistent GPU fault should not be returned to
  service because the queue is long.
- **Do not treat a single transient error as a failing device.**
  [epilog-gpu-validator](https://github.com/Zhanyl-tech/epilog-gpu-validator)
  drains on *persistent* faults specifically because transient ECC events are
  common and draining on each one removes healthy capacity.
- **Do not call a DOWN node "drained".** DOWN means slurmctld lost contact or
  marked it for a reason such as a reboot; the fix and the owner differ.
- A failed telemetry query is not evidence of a fault. Absent evidence is not
  evidence of absence — report the gap.

## Escalate when

- A node is drained with an empty or generic reason. That is unattributable and
  a human has to decide.
- The reason names a GPU fault. The checks in
  [references/operator-handoff.md](references/operator-handoff.md) need node
  access this surface does not have.
