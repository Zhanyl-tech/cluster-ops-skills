---
name: backfill-not-running
description: Investigate poor Slurm cluster utilization, small jobs not filling gaps, or a backfill scheduler that appears ineffective. Use when utilization is low despite a full queue, or when asked how to improve throughput.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Backfill not running

## What backfill is worth, measured

On a replayed `sacct` trace in
[slurm-scheduler-lab](https://github.com/Zhanyl-tech/slurm-scheduler-lab):

| | without backfill | with backfill |
|---|---|---|
| CPU utilization | 72.2% | **83.6%** |
| mean job wait | 1,913 min | **374 min** |

Sweeping the multifactor priority weights across the same trace barely moved
either number. **The dominant lever was users' `--time` limits**, because
backfill plans against the requested limit, not the actual runtime. A user who
requests 24 hours for a 40-minute job makes their job unbackfillable and
everyone else waits.

## Steps

1. Query `config` and confirm `SchedulerType = sched/backfill`. If it is
   `sched/builtin`, backfill is simply off and that is the finding.
2. Read `SchedulerParameters`: `bf_window`, `bf_resolution`,
   `bf_max_job_test`, `bf_max_time`.
3. Query `diagnostics`. Compare backfill **last cycle** duration against
   `bf_max_time`. A cycle hitting the ceiling is being cut off before it
   finishes, so jobs deep in the queue are never tested.
4. Check **last depth cycle** against `bf_max_job_test`. If depth is pinned at
   the limit, backfill is not reaching most of the queue.
5. Query `accounting` and compare `Elapsed` against `Timelimit` across recent
   jobs. A large gap is the time-limit accuracy problem, and it is usually the
   real answer.

## What not to conclude

- **Do not recommend raising priority weights to fix utilization.** Measured, it
  does not. Recommend time-limit accuracy first.
- Do not raise `bf_max_job_test` without noting the cost: backfill cycles get
  longer, and a longer cycle on a busy controller has its own consequences.

## Escalate when

Backfill cycles are completing well inside their limits, time limits are
accurate, and utilization is still low. That is not a backfill problem.
