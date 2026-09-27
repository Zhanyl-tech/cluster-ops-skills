---
name: controller-rpc-saturation
description: Diagnose a Slurm controller that is pinned and making everything slow — squeue lagging, submissions crawling, scheduling cycles stretching. Use when users report the whole cluster feels slow rather than one job or one node, or when slurmctld CPU is high.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Controller RPC saturation

## The shape of this failure

"Everything is slow" is a different report from "my job is slow". When the
controller is saturated, symptoms appear everywhere at once and none of them
point at a component: `squeue` takes seconds, submissions lag, scheduling
cycles stretch, and every individual node looks healthy.

The usual suspects are client behaviour rather than a fault — a polling script
in a loop, a monitoring agent scraping `squeue` per user, a job array whose
steps each call back to the controller. That is the author's judgement, not a
measurement; slurm-rca-bench's controller scenario (S03) has not been run. The
per-user RPC table below is how you check it instead of assuming it.

## Steps

1. Query `diagnostics` (`sdiag`). Read, per
   [sdiag.html](https://slurm.schedmd.com/sdiag.html):
   - **Server thread count** — "the number of current active slurmctld
     threads". slurm.conf puts the ceiling on served RPCs at 256 threads
     (`MAX_SERVER_THREADS`,
     [slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html), under
     `max_rpc_cnt`). At or near it, the controller is saturated rather than slow.
   - **Agent queue size** — outgoing RPC requests queued for retry; climbing
     means outbound traffic to slurmd is backing up.
   - **Main schedule** `Last cycle` and `Max cycle` (microseconds) — the
     scheduling loop being starved of controller time.
2. Read the **RPC statistics by message type** and **by user** blocks in the same
   output. sdiag reports, for each type and for each user, the count, the total
   time and the average time per RPC. The user with the most RPCs is the
   polling-client candidate. If `REQUEST_JOB_INFO` or `REQUEST_PARTITION_INFO`
   dominate the by-type table, that suggests `squeue`- or `sinfo`-style polling
   (the mapping from message type to client command is the author's reading,
   unverified against the Slurm source).
3. These counters are cumulative for the life of the slurmctld process unless
   reset, so one read shows history, not a rate. Read `diagnostics` again after
   a few minutes and compare the counts. **Never reset them** (`sdiag --reset`):
   that erases the evidence, and it is outside this read-only surface anyway.
4. Compare main-schedule `Last cycle` against `Max cycle`. A max far above the
   last is a spike that has passed; both high together is a sustained condition.
5. Query `queue` and count jobs. High RPC load with a *small* queue points at
   client behaviour, not cluster scale.
6. Query `config` for `SchedulerParameters`. `max_rpc_cnt` (defer scheduling
   while active threads are at or above it) and `defer` (do not try to schedule
   each job at submit time) change how the controller behaves under exactly this
   load.
7. Look for job arrays in the queue. An array whose steps poll the controller
   multiplies client traffic.

## What not to conclude

- **Do not conclude the scheduler is broken.** A saturated controller is still
  scheduling; it is being asked to do too much talking.
- **Do not blame the largest job.** Reasoning, not a measurement: RPC load
  follows the number of jobs and clients talking to the controller, and a
  512-node job is still one job, so it is unlikely to out-talk hundreds of
  single-node jobs. The by-user table settles it either way.
- Do not recommend a controller restart as a first move. It clears the symptom,
  loses the counters that identify the client, and the load returns.

## Escalate when

The server thread count is at its ceiling with a small queue, and the by-user
and by-type RPC tables — read twice, some minutes apart — show no dominant
client. That combination needs someone who can look at the controller host
directly, which this read-only surface cannot.
