---
name: slinky-authkey-rotation
description: Verify or troubleshoot Slurm auth-key rotation on Slinky (Slurm on Kubernetes). Use when rotating the slurm auth key, when slurmd cannot authenticate to slurmctld after a rotation, or when a rotation reported success but the cluster cannot run jobs. Records that the delete-and-recreate rotation was observed not to reach slurmd.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview
---

# Slinky auth-key rotation

## Status first: this rotation was observed to fail

Everything below comes from
[slinky-gitops](https://github.com/Zhanyl-tech/slinky-gitops/blob/c51903a03d668dbafc48d8e5494aed744ac10af0/README.md),
which ran it on a KinD cluster (Slinky operator v1.2.0, Slurm 26.05). Its
status line: "the rotation does not currently succeed on Slinky v1.2".

What it recorded: Slinky ships the auth Secret `immutable: true`, so the only
way to change it is delete-and-recreate. After that, a slurmd pod deleted and
recreated from scratch came up mounting the **previous** key while slurmctld
held the new one, and slurmd logged `Protocol authentication error` until the
node went down. The cause was not pinned down there — a kubelet-cached copy of
the Secret is suspected, not established. Plan a rotation expecting this.

## Checks that looked like success and were not

All observed in slinky-gitops:

- `kubectl rollout restart` exits zero and restarts nothing on the slurmd side:
  slurmd pods are owned by Slinky's `NodeSet` CRD, which `rollout restart` does
  not handle.
- **New pods are not new keys.** The recreated slurmd pod was brand new and
  still held the old key, so comparing pod ages proves nothing.
- `sinfo` exiting zero never leaves the controller pod. A "no `*` on any node"
  check passed 130 ms after the rollout, before the new key applied. And
  `idle*` — the `*` means slurmctld cannot reach the node — matches a pattern
  anchored only at the start.

The only check slinky-gitops found that crossed the boundary a rotation can
break was reading the key file inside each slurmd pod and comparing its hash
with the Secret.

## The upstream mechanism: `slurm.jwks`

Slurm documents multi-key auth: "Beginning with version 24.05, you may
alternatively create a slurm.jwks file with multiple keys defined ... the
cluster does not need to be restarted at once when a key is rotated. Instead, an
scontrol reconfigure is sufficient"
([authentication.html](https://slurm.schedmd.com/authentication.html)). Each
key has a unique `kid`, and at most one carries `"use": "default"`. An overlap
rotation built from those documented fields (the page describes the fields, not
this sequence):

1. add the new key under a new `kid`, not default; distribute; `scontrol reconfigure`;
2. make the new key the default; `scontrol reconfigure`;
3. once every daemon holds the new file, remove the old `kid`; `scontrol reconfigure`.

slinky-gitops used a single `slurm.key` and says "`auth/slurm` has no key
versioning"; for Slurm itself the `slurm.jwks` feature says otherwise. **Whether
the Slinky chart can deliver a `slurm.jwks` to every daemon is unverified.**

## Steps

This surface reads Slurm state only. Steps marked **operator** need `kubectl`
and cluster-admin access; they are for a human, not the agent.

1. Before rotating, query `nodes` and record every node's state verbatim. This
   is the baseline.
2. **Operator:** rotate by a documented path — `slurm.jwks` overlap if the
   deployment can deliver it, or slinky-gitops' script, which verifies and
   rolls back on failure — never by `kubectl rollout restart`.
3. **Operator:** verify the key, not the pods: hash the key file inside every
   slurmd pod and compare it with the Secret.
4. **Operator:** after any slurmd pod replacement, slinky-gitops found the node
   left DOWN with reason `slurm-operator: Pod`, with no self-heal in ninety
   seconds of watching — and found that one resume is not enough: "a resume
   fired before the pod comes back is simply lost"
   ([`resume_until_schedulable`](https://github.com/Zhanyl-tech/slinky-gitops/blob/c51903a03d668dbafc48d8e5494aed744ac10af0/scripts/rotate-auth-key.sh#L149-L173)).
   So **only after the hashes in the previous step match**, re-issue
   `scontrol update nodename=<node> state=resume` until the node shows a
   schedulable state (`idle`, `mix` or `alloc`, with no trailing `*`), as that
   function does, before judging the rotation. Never resume a node whose key
   hash does not match: that only turns a red node green.
5. Query `nodes` again. Every node must be back at its baseline state, with no
   trailing `*` and no `down` or `drain`. Anchor any pattern at both ends. A node
   still `down` with reason `slurm-operator: Pod` and a matching hash has not
   taken a resume yet: go back to the resume step rather than calling the
   rotation failed.
6. **Operator:** submit a real job to each node set and see it complete. Until
   that passes, the rotation is unverified.

## What not to conclude

- **Do not treat a zero exit code as verification.** That is the exact failure
  mode above.
- **Do not treat new pods as new keys.** Hash the key.
- Do not assume all node types restarted because one did. The controller and
  the compute nodes are managed by different mechanisms, and that asymmetry is
  the whole problem.

## Escalate when

- The key hash in any slurmd pod differs from the Secret after a recreate. That
  is the failure slinky-gitops recorded; roll back to the previous key (its
  script keeps it as `slurm-auth-slurm-previous`) rather than resuming nodes
  that hold the wrong key. Rolling back replaces the slurmd pods again, so the
  nodes go DOWN again: once their hashes match the restored Secret, resume them
  as in the resume step above, re-issued until schedulable. That is what the
  script's rollback does
  ([`restore_previous_and_settle`](https://github.com/Zhanyl-tech/slinky-gitops/blob/c51903a03d668dbafc48d8e5494aed744ac10af0/scripts/rotate-auth-key.sh#L175-L197)),
  because a drained, unschedulable cluster is "a worse outcome than not having
  rotated".
- Some nodes authenticate and others do not after a rotation. A partially
  rotated cluster is worse than an unrotated one, because it looks healthy in
  aggregate.
