---
name: state-save-unwritable
description: Diagnose a Slurm controller that rejects or hangs on new job submissions while already-running jobs continue. Use when sbatch fails cluster-wide, when submissions error immediately rather than pending, when controller commands hang, or when a storage problem is suspected of halting scheduling.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# StateSaveLocation unwritable, or hung

## Three storage-shaped failures, and what is actually known about each

slurmctld writes each submitted job's script and environment under
`StateSaveLocation`. When that write fails, the submission is refused. When the
accounting database stalls instead, slurmctld keeps scheduling from a cache
(see `accounting-path-stalled`). And when the state-save filesystem *hangs*
rather than failing, the expected behaviour is different again — but nobody in
this set of repos has measured it.

| | accounting path stalled | `StateSaveLocation` **unwritable** | `StateSaveLocation` **hung** |
|---|---|---|---|
| example | database stalled | permissions wrong, read-only, full | stalled NFS or Lustre mount |
| `sbatch` | still accepted | **rejected with an I/O error** | expected to hang |
| `sinfo`, `squeue` | respond | respond | expected to hang if the controller blocks |
| `sacct` | hangs | responds | responds unless slurmdbd shares the mount |
| running jobs | continued | not observed (none running) | not measured |
| failure style | silent, `sacct` only | loud and immediate | expected silent, on the controller |
| evidence | measured, S01 | measured, S06, permission case only | **not measured**; S06's caveat |

Sources:
[S01](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S01-storage-stall-scheduling-halt/scenario.yaml)
and
[S06](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S06-state-save-unwritable/scenario.yaml)
in slurm-rca-bench, both on the bench's single-worker Docker Compose cluster.
S01 is an emulated stall (the database container paused). S06 is a real
permission failure, not an emulation of one, recorded in a single run: it made
the directory unwritable with `chmod 500`, and `sbatch` was
rejected at t+12s with "I/O error writing script/environment to file" and no
job ID was issued, while `sinfo` and `squeue` stayed normal. A read-only
filesystem or a full disk should fail the same write the same way; that was not
measured. S06 states its own limit: "A real parallel filesystem hanging on
StateSaveLocation would block slurmctld rather than return an error, and that
case is not reproduced here."

**So "loud" identifies the unwritable case only.** A hung state-save mount is
expected to be *silent*, which is exactly what the accounting case looks like
from the user's side. Do not send a silent failure to the accounting runbook on
the strength of "state-save failures are loud".

## The discriminator: which commands hang

This is what S01 and S06 actually recorded, and it separates the three:

- Only `sacct` (and `sreport`) hang; `sinfo`, `squeue` and `sbatch` respond →
  the accounting path. Go to `accounting-path-stalled`.
- `sbatch` fails at once with an I/O error; `sinfo` and `squeue` respond →
  `StateSaveLocation` is unwritable.
- `sbatch`, `squeue` and `sinfo` hang, or this surface's own reads time out →
  the controller is blocked or saturated. A hung state-save mount is one
  candidate (unmeasured); RPC saturation is another (`controller-rpc-saturation`).

## Steps

1. Establish what fails and how. A rejected `sbatch` with an error is a
   different fault from a job that pends or a command that never returns. Get
   the exact error text.
2. Call `slurm_overview`, then query `nodes` and `queue`. A timeout from these
   is itself evidence that the controller is not answering. Running jobs
   continuing rules out nothing: they continued through S01, and a controller
   that cannot accept new work need not disturb jobs already on nodes.
3. Query `config` and read `StateSaveLocation`. slurm.conf asks that, with a
   backup controller configured, this location be "readable and writable by
   both systems" ([slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html)),
   so on HA controllers it usually sits on shared storage — where hangs happen.
   The filesystem type and mount health are not visible from this surface; ask
   a human.
4. Query `diagnostics`. A controller that answers with a pinned server thread
   count and heavy RPC tables is *saturated*, not blocked; see
   `controller-rpc-saturation`.
5. If submissions are rejected with an I/O error naming the script or
   environment file, that is the finding. Say so plainly and stop. If controller
   commands hang and the state path is on shared storage, report "consistent
   with a hung `StateSaveLocation` mount, not distinguishable from saturation
   with this surface" and escalate.

## What not to conclude

- **Do not report that a storage stall halted scheduling** unless submissions
  are actually being rejected or controller commands actually hang. The chain
  through the accounting database was observed not to halt scheduling (S01).
- **Do not route a silent, hanging controller to `accounting-path-stalled`**
  because "state-save failures are loud". Only the unwritable case was measured,
  and only it is loud.
- **Do not conclude the controller is healthy because running jobs are fine.**
  Jobs already on nodes kept running through the accounting stall, and nothing
  measured here shows a submission failure touching them.

## Escalate when

`StateSaveLocation` is unwritable or suspected hung. Fixing it is a storage
operation with consequences for controller state, and it is not a diagnosis
anyone should act on alone.
