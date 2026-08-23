---
name: gpu-node-drained
description: Investigate a Slurm node in drain or drng state on a GPU cluster. Use when a node disappears from the available pool, when capacity drops unexpectedly, or when asked why a specific node is not accepting jobs. Reads the drain reason before assuming hardware.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# GPU node drained

## Read the reason, not the state

Every drained node carries a free-text reason written by whatever drained it.
The state column says `drained` for all of them; the reason says which of these
happened:

- an **epilog validator** found a persistent GPU fault between jobs;
- a **human** drained it for maintenance and did not undrain it;
- **slurmd** lost contact and the controller drained it;
- a **prolog** failure, which usually means configuration, not hardware.

These need entirely different responses and are indistinguishable until the
reason is read.

## Steps

1. Query `nodes` and collect every node not in `idle`, `mixed`, or `allocated`.
2. Read the reason column verbatim. Do not paraphrase it into a diagnosis.
3. If the reason names a GPU and an error class (ECC, Xid, fell off the bus),
   treat it as hardware and record which GPU index — a persistent fault on one
   device is a different ticket from a node-wide failure.
4. Query `queue` for jobs pending with `(ReqNodeNotAvail)` naming this node, to
   establish blast radius.
5. Check whether other nodes show the same reason. One node is hardware; five
   nodes with an identical reason in a short window is usually a driver or
   configuration change.

## What not to conclude

- **Do not recommend resuming the node.** This surface is read-only by design,
  and a node drained for a persistent GPU fault should not be returned to
  service because the queue is long.
- **Do not treat a single transient error as a failing device.**
  [epilog-gpu-validator](https://github.com/Zhanyl-tech/epilog-gpu-validator)
  drains on *persistent* faults specifically because transient ECC events are
  common and draining on each one removes healthy capacity.
- A failed telemetry query is not evidence of a fault. Absent evidence is not
  evidence of absence — report the gap.

## Escalate when

A node is drained with an empty or generic reason. That is unattributable and a
human has to decide.
