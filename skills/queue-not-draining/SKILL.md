---
name: queue-not-draining
description: Diagnose a Slurm queue where jobs sit PENDING and the cluster looks busy. Use when someone reports "my job has been queued for hours", when pending count climbs without starts, or when asked why a specific job has not started. Distinguishes a genuinely full cluster from a scheduling problem.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Queue not draining

## Read the reason code the way Slurm defines it

`squeue` reason codes are the diagnostic payload. Slurm's own definitions
([job_reason_codes.html](https://slurm.schedmd.com/job_reason_codes.html)),
paraphrased:

- **`Resources`** — the resources the job requested are not available, for
  example because other jobs are using them.
- **`Priority`** — higher-priority jobs exist for the job's partition or
  advanced reservation.
- **`ReqNodeNotAvail`** — a node the job specifically requires is not
  available. It "may currently be in use, reserved for another job, in an
  advanced reservation, DOWN, DRAINED, or not responding".
- **`Reservation`** — the job is waiting for its advanced reservation to become
  available.

Two things follow from those definitions (reasoning, not a measurement):

- **On a full cluster, most pending jobs show `Priority`, not `Resources`.** The
  jobs at the front wait for resources; everything behind them waits for them.
  Read `Resources` and `Priority` *together* as the capacity signal.
- **`ReqNodeNotAvail` is not automatically a fault.** A maintenance reservation
  or a node busy with another job produces it too. Find which of the documented
  causes applies before calling it one.

## Steps

1. Call `slurm_overview` — node states, the queue, and scheduler diagnostics
   together.
2. Count pending jobs by reason code. If `Resources` and `Priority` together
   dominate and the nodes are `allocated` or `mixed`, the cluster is full:
   report utilization and the largest pending request rather than hunting a bug.
3. If `ReqNodeNotAvail` or `Reservation` appears, query `nodes` and read the
   state and the **reason column** for the nodes involved. A drained, down or
   not-responding node is a fault; a reservation is a schedule. Reservations are
   not on this tool surface: ask a human for `scontrol show reservation`.
4. If pending jobs carry limit reasons (`QOS…`, `Assoc…`, `Partition…`), switch
   to `partition-limit-starvation`.
5. If `Priority` dominates *and* nodes are idle, query `priority` and read the
   **factors**, not the total. The total gives the order; the factors say which
   weight produced it.
6. If nodes are idle while jobs pend, check whether the jobs can use them. Two
   common reasons they cannot: a GRES or feature the idle nodes lack (the `nodes`
   topic shows each node's configured GRES; `accounting` returns `ReqTRES`,
   each job's requested TRES including GPUs, for jobs in its time window; node
   features and job constraints are not on this surface, so ask), and a
   requested time limit too long to fit before the nodes are needed by a
   higher-priority job (compare `Elapsed` with `Timelimit` in `accounting`; see
   `backfill-not-running`).
7. Query `diagnostics` for backfill health using the method in
   `backfill-not-running`: compare `Last depth cycle` with `Last queue length`.
   Do not compare the backfill `Last cycle` (microseconds, execution time only)
   with `bf_max_time` (seconds, including lock-release sleeps).

## What not to conclude

- **Do not recommend changing priority weights as a first move.** In
  [slurm-scheduler-lab](https://github.com/Zhanyl-tech/slurm-scheduler-lab/tree/c02b52fd0ccdd2b748f2599574f97f68d92248cb)'s
  simulator — a seeded synthetic workload, not Slurm and not a site trace —
  one-weight sweeps did move utilization and wait (by up to 20.7 points and
  4.27x), but by trading one against the other, while enabling backfill improved
  both in all 10 seeds tried. Weights encode who waits; they are not a repair.
  Provenance for these figures is in `backfill-not-running`.
- **Do not treat `ReqNodeNotAvail` alone as a fault.** Check for a reservation
  or a busy node first.
- A long queue with high utilization is a working scheduler, not a broken one.

## Escalate when

Jobs pend while nodes sit idle, and you have ruled out, in order: limits (reason
codes), reservations (asked a human), GRES or feature mismatch, time-limit fit,
and backfill depth. What remains is not explained by capacity or configuration
visible here, and needs a human with controller access.
