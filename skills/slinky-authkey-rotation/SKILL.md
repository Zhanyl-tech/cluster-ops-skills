---
name: slinky-authkey-rotation
description: Verify or troubleshoot Slurm auth-key rotation on Slinky (Slurm on Kubernetes). Use when rotating the slurm auth key, when slurmd cannot authenticate to slurmctld after a rotation, or when a rotation reported success but the cluster cannot run jobs.
allowed-tools: slurm_query, slurm_overview
---

# Slinky auth-key rotation

## The failure this exists to prevent

`kubectl rollout restart` **silently skips Slinky's compute nodes.** They are
owned by a `NodeSet` CRD, which `rollout restart` does not understand. It exits
zero having restarted nothing that matters.

Measured in
[slinky-gitops](https://github.com/Zhanyl-tech/slinky-gitops): the controller
picked up a rotated auth key while `slurmd` kept the old one. The rotation
script reported success on a cluster that could not run a job.

**A rotation that reports success is not evidence the rotation worked.** The
only evidence is a job completing afterwards.

## Steps

1. Before rotating, query `nodes` and record which nodes are healthy. This is
   the baseline to compare against.
2. Rotate the key by the documented path, not by `kubectl rollout restart`.
3. Confirm the `NodeSet`-owned pods actually restarted — compare pod ages, not
   the exit code of the restart command.
4. Query `nodes`. Nodes still holding the old key will not be in a healthy
   state; a node that stayed `idle` throughout may simply never have restarted.
5. **Submit and complete a real job.** Nothing before this step distinguishes a
   working rotation from a broken one.

## What not to conclude

- **Do not treat a zero exit code as verification.** That is the exact failure
  mode above.
- Do not assume all node types restarted because one did. The controller and
  the compute nodes are managed by different mechanisms, and that asymmetry is
  the whole problem.

## Escalate when

Some nodes authenticate and others do not after a rotation. A partially rotated
cluster is worse than an unrotated one, because it looks healthy in aggregate.
