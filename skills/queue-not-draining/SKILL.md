---
name: queue-not-draining
description: Diagnose a Slurm queue where jobs sit PENDING and the cluster looks busy. Use when someone reports "my job has been queued for hours", when pending count climbs without starts, or when asked why a specific job has not started. Distinguishes a genuinely full cluster from a scheduling problem.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Queue not draining

## The distinction that matters first

`squeue` reason codes are the diagnostic payload, and the two most common ones
mean opposite things:

- **`(Resources)`** — the job would fit, the cluster is full. This is capacity,
  not a fault. The queue is working.
- **`(Priority)`** — something ahead of it holds a reservation. The job may be
  waiting behind one large job's backfill reservation.
- **`(ReqNodeNotAvail)`** — nodes the job needs are drained or down. This is a
  fault, and usually one nobody has noticed.

**Read the reason before anything else.** Most "the scheduler is broken"
reports are `(Resources)` on a full cluster, which needs a capacity
conversation, not a scheduler change.

## Steps

1. `slurm_overview` — node states, queue, and scheduler diagnostics together.
2. Count pending jobs by reason code. If the queue is dominated by
   `(Resources)`, stop: the cluster is full. Report utilization and the largest
   pending request rather than hunting a bug.
3. If `(ReqNodeNotAvail)` appears, query `nodes` and read the **reason column**
   on drained nodes. An epilog validator, a human, and a kernel panic all show
   `drained` and differ only in the reason text.
4. If `(Priority)` dominates, query `priority` and read the **factors**, not the
   total. The total gives the order; the factors say which weight produced it.
5. Query `diagnostics`. Check backfill "last cycle" against `bf_max_time` in
   `config` — a backfill pass being cut off before it finishes will leave
   backfillable jobs pending with no other symptom.

## What not to conclude

- **Do not recommend changing priority weights as a first move.** Measured on a
  replayed trace in
  [slurm-scheduler-lab](https://github.com/Zhanyl-tech/slurm-scheduler-lab),
  sweeping the priority weights barely moved queue behaviour, while enabling
  backfill moved CPU utilization from 72.2% to 83.6% and mean wait from 1,913
  to 374 minutes. The dominant lever was users' `--time` limits, not the
  weights everyone tunes first.
- A long queue with high utilization is a working scheduler, not a broken one.

## Escalate when

Pending jobs exist, nodes are `idle`, and backfill is running — that
combination is not explained by capacity and needs a human.
