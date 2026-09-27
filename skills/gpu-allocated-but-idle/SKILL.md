---
name: gpu-allocated-but-idle
description: Investigate GPUs held by a running job that is not using them — hung training runs, jobs that finished work but never exited, or allocations sitting at zero utilization. Use when GPU capacity is scarce while the cluster reports itself fully allocated, or when reclaiming wasted allocations.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
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

## What this tool surface can and cannot see

- **Allocated GPUs per job are not on it.** The `queue` topic's columns are job,
  partition, user, state, elapsed, nodes and reason — no GPUs. The `nodes`
  topic's GRES column is each node's *configured* GRES, not what is allocated.
- **The nearest proxy is `ReqTRES`** from the `accounting` topic: the TRES each
  job *requested*, including `gres/gpu`. It is requested, not allocated, and it
  comes from slurmdbd, so it can hang if the accounting path is degraded.
- **GPU utilization is not on it either. Slurm may record a peak of it, which
  is not the same thing.** "If AccountingStorageTRES=gres/gpu is configured,
  gres/gpumem and gres/gpuutil will automatically be configured and gathered
  from GPU jobs", for NVIDIA GPUs with `AutoDetect=nvml` (AMD with
  `AutoDetect=rsmi`), and not for MIG devices
  ([gres.html](https://slurm.schedmd.com/gres.html)). This surface's
  `accounting` topic does not request that field, so a human reads it.
- **What `sacct` reports is a high-water mark.** For `TRESUsageInAve`,
  [sacct.html](https://slurm.schedmd.com/sacct.html) says the values "represent
  the average/total of the highest watermarks over all ranks in the step", and
  gres.html reads gpuutil with `sacct` "After the job has finished" as
  "highwater marks". A training job that ran flat out and then deadlocked still
  reports its earlier peak. So `sacct -j <job>.<step> --format=TRESUsageInAve`
  can confirm **never started** (a peak of zero) and cannot rule out **hung**.
- **For a running step, `sstat` is the point-in-time read.** The same sacct.html
  entry says "When using sstat they represent the average/total at the moment
  the command was run": `sstat -j <job>.<step> --format=TRESUsageInAve`, read
  several times, minutes apart. Whether `sstat` carries `gres/gpuutil` is not
  shown on sacct.html, gres.html or
  [sstat.html](https://slurm.schedmd.com/sstat.html) (unverified).

## Steps

1. Call `slurm_overview`. A full cluster (nodes `allocated` or `mixed`) with a
   deep pending queue is the condition worth investigating.
2. Query `config` and read `AccountingStorageTRES`. If it includes `gres/gpu`,
   Slurm is likely gathering `gres/gpuutil` already (subject to the AutoDetect
   and MIG conditions above). Before anyone reaches for DCGM, ask a human for
   the suspect jobs' readings: the `sacct` peak for finished steps, where a peak
   of zero means **never started**, and repeated `sstat` reads for running
   steps. A non-zero peak clears nothing.
3. Query `queue` for long-running jobs by elapsed time, then `accounting` for
   the same jobs' `ReqTRES`. Sort attention by requested GPUs × elapsed — that
   product is the waste if the job is idle.
4. Query `accounting` filtered by `user` for a suspect user's recent history. A
   user whose jobs habitually run to their full time limit with short actual
   work is a pattern, not an incident.
5. Where Slurm does not record utilization, correlating DCGM telemetry with the
   owning job, classifying by failure signature, and escalating alert → drain →
   cancel is what [gpu-reaper](https://github.com/Zhanyl-tech/gpu-reaper) does.
   For a one-off check, hand the node to an operator with
   [references/operator-handoff.md](references/operator-handoff.md).
6. Distinguish the three shapes before recommending anything: **hung** (was
   working, stopped), **never started** (allocated, never used a GPU), and
   **idle by design** (an interactive session, legitimately).

## What not to conclude

- **Do not conclude a job is idle from missing telemetry.** A gap in DCGM
  samples is a collector fault, not an idle GPU. `gpu-reaper` treats it that
  way specifically so a monitoring outage can never cancel a healthy job, and
  that guarantee is worth more than the capacity it might reclaim.
- **Do not treat `ReqTRES` as proof of allocation or of use.** It is what the
  job asked for.
- **Do not read a non-zero `gres/gpuutil` from `sacct` as the GPUs being in use
  now.** It is the step's high-water mark: a job that worked and then hung
  still reports the peak from before it hung.
- **Do not recommend cancelling a user's job.** This surface reads; the
  decision to kill someone's twelve-hour training run belongs to a human with
  the authority to defend it.
- **Do not conclude the cluster needs more GPUs** from allocation figures
  alone. Allocated is not utilized, and that gap is the entire subject here.

## Escalate when

- The waste is systemic rather than incidental — many users, many jobs. That is
  a policy conversation about time limits and interactive sessions, not an
  incident to triage.
- A specific job looks idle and someone wants it reclaimed. Cancelling is a
  human decision, made on utilization evidence, never on missing telemetry.
