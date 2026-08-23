---
name: fabric-degraded-collectives
description: Investigate multi-node training jobs that run far slower than expected while single-node jobs are fine. Use when distributed training throughput drops without any job failing, when NCCL performance degrades, or when someone reports the interconnect feels slow.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Fabric degraded collectives

## The signature

**Multi-node jobs crawl; single-node jobs are fine.** That asymmetry is the
diagnosis. Compute is healthy — every GPU is doing its work — and the loss is
in the collective operations between nodes, so nothing fails and nothing is
logged as an error. The job simply takes longer, and the user notices before
any alert does.

A degraded link does not usually go down. It retrains at a lower width or
speed, or accumulates symbol errors, and everything keeps working slowly. Link
*down* is easy; link *degraded* is the one that wastes weeks of GPU time
quietly.

## Steps

1. Query `queue` and separate multi-node from single-node jobs. If single-node
   throughput is normal, the compute path is fine and this is a fabric
   question.
2. Query `nodes` for the node set the slow jobs share. A degraded link is
   usually confined to specific nodes or a specific switch.
3. Establish whether the slow jobs share a **common node**. One node appearing
   in every slow multi-node job and no fast one is a strong localisation.
4. Fabric counters themselves are outside this read-only Slurm surface.
   Attributing them to the job that owns them is what
   [ib-slurm-exporter](https://github.com/Zhanyl-tech/ib-slurm-exporter) is
   for — and note it refuses to attribute a device two jobs share, rather than
   guessing.
5. Record which collective pattern is affected if the user knows it. All-reduce
   degradation across a rail points somewhere different from point-to-point.

## What not to conclude

- **Do not attribute a shared device to one job.** If two jobs are on the same
  node and the counter is per-device, the attribution is genuinely ambiguous
  and reporting a guess is worse than reporting the ambiguity.
- **Do not conclude "the network is fine" from a healthy link state.** Up and
  healthy are different. A link retrained to a lower width reports up.
- Do not assume the slowest job is the affected one. It may just be the
  largest.

## Escalate when

Slow multi-node jobs share no common node. That points at a switch or a rail
rather than a host, and needs fabric tooling this surface does not have.
