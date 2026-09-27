---
name: backfill-not-running
description: Investigate poor Slurm cluster utilization, small jobs not filling gaps, or a backfill scheduler that appears ineffective. Use when utilization is low despite a full queue, or when asked how to improve throughput.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Backfill not running

## What backfill is worth, and how sure that is

Slurm documents the mechanism: without backfill "each partition is scheduled
strictly in priority order, which typically results in significantly lower
system utilization and responsiveness than otherwise possible", and backfill
starts a lower-priority job only "if doing so does not delay the expected start
time of any higher priority jobs"
([sched_config.html](https://slurm.schedmd.com/sched_config.html)).

For a sense of scale there is a **simulator, not a cluster**:
[slurm-scheduler-lab @ c02b52f](https://github.com/Zhanyl-tech/slurm-scheduler-lab/tree/c02b52fd0ccdd2b748f2599574f97f68d92248cb)
models EASY backfill, which protects only the highest-priority blocked job (a
simplification of Slurm's backfill), on a seeded **synthetic** 300-job workload
across 16 simulated nodes. Across seeds 0–9:

| simulated, seeds 0–9 | backfill off | backfill on |
|---|---|---|
| CPU utilization | 49.5–82.6% | 77.1–92.5% |
| mean job wait | 1,235.6–2,144.8 min | 236.5–943.8 min |

Backfill raised utilization in 10 of 10 seeds (by 7.6 to 32.5 points) and cut
mean wait in 10 of 10 (by 56% to 84%). The lab README's headline pair, 72.2% →
83.6% and 1,913.0 → 373.7 min, is seed 5 of this range. Reproduce with
`schedlab --compare-backfill --jobs 300 --seed N` at that commit, summarised by
`scripts/lab_figures.py` in the cluster-ops-skills repository. None of this is a
Slurm measurement or a replayed site trace: it says backfill matters in the
model, not how much it will gain on your cluster.

## Why priority weights are not the first fix

In the same simulator, sweeping one priority weight at a time (0, 1,000, 10,000
and 100,000, backfill on, seeds 0–9) moved utilization by up to 20.7 points and
mean wait by up to 4.27x, both for the jobsize weight; the age weight moved them
least (at most 4.9 points and 1.28x). So the weights are not inert. What they do
is trade one outcome for another: in the lab README's own jobsize sweep the
setting with the highest utilization (93.4%) also had the worst mean wait
(496.7 min). A weight change is a policy decision about who waits, not a repair
for low utilization.

## Why time limits come first

Backfill plans against each job's *requested* limit, not its real runtime.
Slurm says so directly: "reasonably accurate time limits are important for
backfill scheduling to work well" (sched_config.html, above). The lab pins the
mechanism with a unit test that runs two otherwise identical three-job
workloads,
[`test_backfill_plans_against_time_limit_not_true_runtime`](https://github.com/Zhanyl-tech/slurm-scheduler-lab/blob/c02b52fd0ccdd2b748f2599574f97f68d92248cb/tests/test_scheduling.py#L188-L206):
the same 50-second job backfills at once when it requests 50 seconds and does
not when it requests 500. That demonstrates the mechanism. It does not measure
how much time-limit accuracy is worth at cluster scale — the lab has no
time-limit sweep — so "fix the time limits first" is an argument from the
documented mechanism, not a measured ranking of levers.

## Steps

1. Query `config` and confirm `SchedulerType = sched/backfill`. If it is
   `sched/builtin`, backfill is off and that is the finding.
2. Read `SchedulerParameters` from the same output: `bf_window`,
   `bf_resolution`, `bf_max_job_test`, `bf_max_time`, `bf_interval`,
   `bf_continue`. An absent key means the default
   ([slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html)):
   `bf_max_job_test` defaults to 500 jobs, `bf_interval` to 30 seconds,
   `bf_max_time` to the value of `bf_interval`, and `bf_window` to 1440 minutes.
3. Query `diagnostics` and read the backfill block. **Mind the units and the
   meaning** ([sdiag.html](https://slurm.schedmd.com/sdiag.html)): backfill
   `Last cycle` is in **microseconds** and "counts only execution time,
   removing sleep time"; `bf_max_time` is in **seconds** and includes "time
   spent sleeping when locks are released". A `Last cycle` well under
   `bf_max_time` therefore does *not* prove the cycle finished. Do not compare
   the two directly.
4. Use depth instead, which has no such ambiguity. `Last depth cycle` is the
   number of jobs processed in the last backfill cycle; `Last queue length` is
   the number pending for backfill. Depth far short of the queue length, and
   pinned at `bf_max_job_test`, means backfill is not reaching most of the
   queue. `Last depth cycle (try sched)` counts only jobs that had a chance to
   start.
5. Note whether `bf_continue` is set. slurm.conf: it makes the backfill
   scheduler "continue processing pending jobs from its original job list after
   releasing locks even if job or node state changes". On a busy cluster its
   absence is a candidate reason deep jobs are never reached — an inference from
   that text, not a measurement.
6. Compare `bf_window` (minutes) with the longest partition `MaxTime`. slurm.conf
   advises a window "at least as long as the highest allowed time limit" to
   prevent starvation. Partition `MaxTime` is **not** on this tool surface:
   `config` is `scontrol show config`, which prints global parameters, not
   partitions. Ask a human for `scontrol show partition`, or report the gap.
7. Query `accounting` and compare `Elapsed` against `Timelimit` across recent
   jobs. A large, consistent gap is the time-limit accuracy problem.

## What not to conclude

- **Do not recommend changing priority weights to fix utilization** before the
  steps above. In the simulator they do move utilization, but by trading it
  against wait time; they encode policy, they do not repair backfill.
- **Do not read `Last cycle` against `bf_max_time`** as if they shared units or
  meaning. They share neither.
- **Do not quote the simulator's figures as this cluster's expected gain.** They
  come from a synthetic workload in a model of EASY backfill.
- Do not raise `bf_max_job_test` or `bf_max_time` without noting the cost:
  slurm.conf warns that higher values bring "more overhead and less
  responsiveness", and that a longer backfill cycle can keep Slurm from
  "responding to client requests in a timely manner".

## Escalate when

Backfill is on, its depth reaches the queue, `bf_window` covers the longest
partition time limit, time limits are accurate, and utilization is still low.
That is not a backfill problem.
