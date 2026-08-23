---
name: controller-rpc-saturation
description: Diagnose a Slurm controller that is pinned and making everything slow — squeue lagging, submissions crawling, scheduling cycles stretching. Use when users report the whole cluster feels slow rather than one job or one node, or when slurmctld CPU is high.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Controller RPC saturation

## The shape of this failure

"Everything is slow" is a different report from "my job is slow". When the
controller is saturated, symptoms appear everywhere at once and none of them
point at a component: `squeue` takes seconds, submissions lag, scheduling
cycles stretch, and every individual node looks healthy.

The usual cause is RPC volume, not a fault — a polling script in a loop, a
monitoring agent scraping `squeue` per user, or a job array whose steps each
call back to the controller.

## Steps

1. Query `diagnostics`. This is the whole diagnosis and most of it is here:
   - **Server thread count** at or near its ceiling means the controller is
     saturated rather than slow.
   - **Agent queue size** climbing means outbound RPCs to slurmd are backing up.
   - **Main schedule last cycle** and **max cycle** stretching shows the
     scheduling loop being starved of controller time.
2. Compare **last cycle** against **max cycle**. A max far above the last is a
   spike that has passed; both high together is a sustained condition.
3. Query `queue` and count jobs. High RPC load with a *small* queue points at a
   client behaviour problem, not cluster scale.
4. Query `config` for `SchedulerParameters`. `max_rpc_cnt` and
   `defer` change how the controller behaves under exactly this load.
5. Look for job arrays in the queue. A large array whose steps poll the
   controller is the most common self-inflicted version.

## What not to conclude

- **Do not conclude the scheduler is broken.** A saturated controller is still
  scheduling; it is being asked to do too much talking. The queue usually still
  drains, slowly.
- **Do not blame the largest job.** RPC load correlates with *job and client
  count*, not with job size. One 512-node job generates less controller traffic
  than five hundred one-node jobs.
- Do not recommend a controller restart as a first move. It clears the symptom,
  loses the evidence, and the load returns.

## Escalate when

Thread count is at ceiling with a small queue and no identifiable polling
client. That combination needs someone who can look at the controller host
directly, which this read-only surface cannot.
