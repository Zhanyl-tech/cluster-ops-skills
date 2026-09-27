---
name: fabric-degraded-collectives
description: Investigate multi-node training jobs that run far slower than expected while single-node jobs are fine. Use when distributed training throughput drops without any job failing, when NCCL performance degrades, or when someone reports the interconnect feels slow.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Fabric degraded collectives

## The signature, and what else produces it

**Multi-node jobs crawl; single-node jobs are fine.** That asymmetry says the
loss is on the path *between* nodes. It does not yet say the fabric is at fault:
the same asymmetry comes from how a job uses the path. Nothing fails and nothing
is logged as an error, so the user tends to notice before any alert does.

The differential, in no measured order:

- **A degraded link.** A link that retrains at a lower width or speed, or
  accumulates errors, keeps working slowly. `ibstat` reports port state and
  "link width active" as separate fields
  ([ibstat(8)](https://github.com/linux-rdma/rdma-core/blob/master/infiniband-diags/man/ibstat.8.in.rst)),
  so a port can look up while running narrow. Read the width, not the state.
- **NCCL not using RDMA at all.** NCCL picks its network transport, and can run
  over IP sockets instead of IB/RoCE; the NCCL docs describe that fallback when
  the IB transport is disabled
  ([NCCL environment variables](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html),
  `NCCL_IB_DISABLE`). A job whose ranks cannot see the RDMA devices (a container
  without them, or an `NCCL_IB_HCA` filter that excludes the right adapter) would
  be slow across nodes on a healthy fabric. That trigger list is reasoning, not
  a measurement.
- **A straggler.** A collective finishes when its slowest rank does, so one slow
  GPU or node slows every multi-node job it joins while single-node jobs
  elsewhere look fine (reasoning).
- **Placement.** Jobs spread across leaf switches cross more of the fabric than
  jobs packed under one switch.

This scenario is designed but not observed in slurm-rca-bench
([S07](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S07-fabric-degraded-collectives/scenario.yaml)):
its injection is `tc netem` on a Docker network, which "cannot reproduce per-QP
or per-HCA counter signatures". Nothing here has been checked on real fabric.

## Steps

1. Query `queue` and separate multi-node from single-node jobs. If single-node
   throughput is normal, the compute path on those nodes is fine and the
   question is the path between nodes.
2. Query `nodes` for the node set the slow jobs share.
3. Establish whether the slow jobs share a **common node**. One node appearing
   in every slow multi-node job and in no fast one is a strong localisation — a
   bad link on that host, or a straggler GPU on it.
4. Ask whether the slow jobs run inside containers or with custom NCCL
   environment variables. If so, the transport question comes before the fabric
   one.
5. Fabric counters and NCCL's transport choice are outside this read-only Slurm
   surface. Hand the node set to an operator with
   [references/operator-handoff.md](references/operator-handoff.md). Attributing
   counters to the job that owns them is what
   [ib-slurm-exporter](https://github.com/Zhanyl-tech/ib-slurm-exporter) is for —
   and note it refuses to attribute a device two jobs share, rather than
   guessing.
6. Record which collective pattern is affected if the user knows it. All-reduce
   degradation across a rail points somewhere different from point-to-point.

## What not to conclude

- **Do not conclude "the fabric is degraded" from the asymmetry alone.** Rule
  out the transport (NCCL on sockets), a straggler and placement first.
- **Do not conclude "the network is fine" from a healthy port state.** A port
  can be up at reduced width; read the width.
- **Do not attribute a shared device to one job.** If two jobs are on the same
  node and the counter is per-device, the attribution is genuinely ambiguous
  and reporting a guess is worse than reporting the ambiguity.
- Do not assume the slowest job is the affected one. It may just be the
  largest.

## Escalate when

- Slow multi-node jobs share no common node and the transport is confirmed to be
  RDMA. That points at a switch or a rail rather than a host, and needs fabric
  tooling this surface does not have.
- Any check in the hand-off needs node or switch access.
