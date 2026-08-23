---
name: state-save-unwritable
description: Diagnose a Slurm controller rejecting every new job submission while already-running jobs continue normally. Use when sbatch fails cluster-wide, when submissions error immediately rather than pending, or when a storage problem is suspected of halting scheduling.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# StateSaveLocation unwritable

## This is the storage failure that really does stop things

There are two storage-shaped failures on a Slurm cluster and they behave
oppositely. Getting them the wrong way round wastes the whole investigation.

| | accounting path degraded | `StateSaveLocation` unwritable |
|---|---|---|
| symptom | `sacct` hangs, history missing | **new submissions rejected** |
| running jobs | unaffected, complete normally | unaffected, complete normally |
| new jobs | still start | **cannot be submitted** |
| failure style | silent, unbounded wait | **loud, immediate error** |

The accounting version does **not** halt scheduling — measured, with a
timeline, in [slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench).
The `StateSaveLocation` version genuinely does block slurmctld, because the
controller must persist state before accepting work.

**"Loud and immediate" versus "silent and hanging" is the fastest
discriminator you have.** Use it before anything else.

## Steps

1. Establish what actually fails. A rejected `sbatch` with an error is a
   different fault from a job that pends. Get the exact error text.
2. Query `nodes` and `queue`. Running jobs continuing normally is expected in
   **both** failure modes and rules out neither — do not treat it as evidence.
3. Query `config` and read `StateSaveLocation`. Note which filesystem it is on
   and whether that filesystem is shared with anything else.
4. Query `diagnostics`. Distinguish a controller that is *blocked* from one
   that is *saturated* — see the `controller-rpc-saturation` runbook, which
   looks similar from the user's side and is a different problem.
5. If submissions are rejected and the state path is on a filesystem under
   pressure, that is the finding. Say so plainly and stop.

## What not to conclude

- **Do not report that a storage stall halted scheduling** unless submissions
  are actually being rejected. The widely-repeated chain through the accounting
  database has been measured and it does not hold.
- **Do not conclude the controller is healthy because running jobs are fine.**
  Running jobs are fine in every failure mode listed here.

## Escalate when

`StateSaveLocation` is unwritable. Fixing it is a storage operation with
consequences for controller state, and it is not a diagnosis anyone should act
on alone.
