---
name: accounting-path-stalled
description: Diagnose a hanging or empty sacct, a climbing DBD Agent queue, or a suspected storage stall on a Slurm cluster. Use when accounting queries block, when job history is missing, or when someone claims a storage problem has halted scheduling. Contains a measured refutation of that claim.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Accounting path stalled

## The folk model is wrong, and this is the measured evidence

The widely-repeated chain is:

```
shared filesystem → accounting DB → slurmdbd → slurmctld → scheduling halts
```

**Measured against a live cluster, scheduling does not halt.**
[slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench) built this
scenario around the folk model and then tested it:

```
t+0s      baseline — sacct ok, node idle, DBD Agent queue size 0
t+5s      sacct BLOCKS (no return, no error); sinfo still fine
t+60s     DBD Agent queue size 1
t+840s    DBD Agent queue size 6 and climbing; sbatch still accepted
t+900s    submitted jobs reach the node and run; queue drains
heal+10s  sacct returns; queued records flush — jobs COMPLETED
```

slurmctld keeps scheduling on a degraded accounting path. Job start latency
degrades to tens of seconds, which is real — but nothing halts, and jobs
submitted *during* the stall run to completion.

**So a blocked `sacct` is evidence about slurmdbd, not about the scheduler.**
Diagnosing "scheduling has stopped" from a hanging accounting query is the
single most common wrong turn here.

## Steps

1. Query `diagnostics` first. **DBD Agent queue size** is the direct signal: a
   climbing value means accounting is backing up.
2. Query `nodes` and `queue`. If jobs are still starting and completing,
   scheduling is alive regardless of what `sacct` is doing. Say so explicitly.
3. Attempt `accounting`. A **timeout is a finding**, not an error to retry — it
   distinguishes a blocked path from an empty result.
4. Separate the two failure shapes: unbounded wait (the path is stalled) versus
   an immediate error (the path is broken or misconfigured).

## The failure mode that does halt scheduling

`StateSaveLocation` becoming unwritable is different: slurmctld genuinely blocks
on state writes, and it fails loudly and immediately rather than degrading. If
scheduling really has stopped, check that before the accounting path.

## What not to conclude

- **Do not report "storage stall halted scheduling"** without showing jobs
  failing to start. The chain has been measured and it does not hold.
- Missing job history is a reporting problem, not an availability problem.
  State the user-visible impact accurately.

## Escalate when

The DBD Agent queue is climbing and not draining after the underlying storage
recovers — queued records should flush on their own.
