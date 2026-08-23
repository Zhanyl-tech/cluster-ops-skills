---
name: gpu-allocated-but-idle
description: Investigate GPUs held by a running job that is not using them — hung training runs, jobs that finished work but never exited, or allocations sitting at zero utilization. Use when GPU capacity is scarce while the cluster reports itself fully allocated, or when reclaiming wasted allocations.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# GPU allocated but idle

## Waste is not a fault

Every other runbook here is about something broken. This one is about the
cluster working perfectly while delivering nothing: a job holds eight GPUs at
0% utilization for eleven hours because the training loop deadlocked, or the
work finished and the process never exited, or someone allocated an
interactive session on Friday afternoon.

From Slurm's point of view nothing is wrong. The node is `allocated`, the job
is `RUNNING`, no error exists anywhere. **Scarcity shows up as a queue, and the
queue looks like a capacity problem** — which is why the usual response is to
buy more GPUs.

## Steps

1. Query `overview`. Note total allocated GPUs against the pending queue depth.
   A full cluster with a deep queue is the condition worth investigating.
2. Query `queue` and list long-running jobs by elapsed time. Sort attention by
   `GPUs × elapsed` — that product is the waste if the job is idle.
3. Query `accounting` for the same user's recent history. A user whose jobs
   habitually run to their full time limit with short actual work is a pattern,
   not an incident.
4. GPU utilization itself is not in this Slurm surface. Correlating DCGM
   telemetry with the owning job, classifying by failure signature, and
   escalating alert → drain → cancel is what
   [gpu-reaper](https://github.com/Zhanyl-tech/gpu-reaper) does.
5. Distinguish the three shapes before recommending anything: **hung** (was
   working, stopped), **never started** (allocated, never used a GPU), and
   **idle by design** (an interactive session, legitimately).

## What not to conclude

- **Do not conclude a job is idle from missing telemetry.** A gap in DCGM
  samples is a collector fault, not an idle GPU. `gpu-reaper` treats it that
  way specifically so a monitoring outage can never cancel a healthy job, and
  that guarantee is worth more than the capacity it might reclaim.
- **Do not recommend cancelling a user's job.** This surface reads; the
  decision to kill someone's twelve-hour training run belongs to a human with
  the authority to defend it.
- **Do not conclude the cluster needs more GPUs** from allocation figures
  alone. Allocated is not utilized, and that gap is the entire subject here.

## Escalate when

The waste is systemic rather than incidental — many users, many jobs. That is a
policy conversation about time limits and interactive sessions, not an incident
to triage.
