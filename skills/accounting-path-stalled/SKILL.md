---
name: accounting-path-stalled
description: Diagnose a hanging or empty sacct, a climbing DBD Agent queue, or a suspected storage stall on a Slurm cluster. Use when accounting queries block, when job history is missing, or when someone claims a storage problem has halted scheduling. Carries Slurm's documented caching behaviour and its limits, and an emulated run that contradicts that claim.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Accounting path stalled

## What Slurm documents, and what an emulated run showed

The widely repeated chain is:

```
shared filesystem → accounting DB → slurmdbd → slurmctld → scheduling halts
```

Slurm's accounting guide describes a different mechanism: "If SlurmDBD is
configured for use but not responding then slurmctld will utilize an internal
cache until SlurmDBD is returned to service"
([accounting.html](https://slurm.schedmd.com/accounting.html)). A stalled
accounting path should therefore degrade reporting, not stop scheduling — under
the default `max_dbd_msg_action`; see the limits below.

[slurm-rca-bench S01](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S01-storage-stall-scheduling-halt/scenario.yaml)
built a scenario around the chain above and then ran it. What its fully probed
run recorded:

```
t+0s      baseline — sacct ok, node idle, DBD Agent queue size 0
t+5s      sacct BLOCKS (no return, no error); sinfo still fine
t+60s     DBD Agent queue size 1
t+840s    DBD Agent queue size 6 and climbing; sbatch still accepted
t+900s    submitted jobs reach the node and run; queue drains
heal+10s  sacct returns; queued records flush — jobs COMPLETED
```

Queue growth follows accounting traffic, not elapsed time: a second run reached
the same depth of 6 at t+180s. Job start latency degraded to tens of seconds,
which is real, but the two jobs submitted *during* the stall ran to completion.

**Scope of that observation.** One Docker Compose cluster with a single CPU
worker
([docker-compose.yml](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/cluster/docker-compose.yml)),
Slurm 25.11.4, the database container paused with `docker pause` (an emulated
stall, not a real filesystem fault), about 16 minutes, two jobs submitted during
the stall, and `AccountingStorageEnforce=none` (measured in
[S08](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S08-partition-limit-starvation/scenario.yaml)).
Scheduling was observed in that one run; S01 records its second run only for
the queue depth. The queue stayed nowhere near `MaxDBDMsgs`, and S01 does not
record `max_dbd_msg_action`, so it says nothing about what happens at the cap.
It refutes "a stalled accounting path halts scheduling" as a rule. It does not
show what a large cluster does over a long outage.

**Documented limits on "scheduling carries on":**

- **Only a first start has no cache.** Slurm's full passage: "The cached data is
  written by slurmctld to local storage upon shutdown and recovered at startup.
  If SlurmDBD is not available when slurmctld starts, a cache of valid accounts,
  user limits, etc. based upon their state when the daemons were last
  communicating will be used. Note that SlurmDBD must be responding when
  slurmctld is first started since no cache of this critical data will be
  available" ([accounting.html](https://slurm.schedmd.com/accounting.html)). So
  a restart recovers the cache slurmctld wrote at shutdown; only a first start,
  with no saved cache, has none.
- **The cache is bounded.** slurmctld "will only queue so many messages" for
  slurmdbd: `MaxDBDMsgs`, default 10000 or `MaxJobCount * 2 + Node Count * 4`,
  whichever is greater
  ([slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html)).
- **What happens at the cap is a setting, and one choice stops the
  controller.** `SlurmctldParameters=max_dbd_msg_action` takes "'discard'
  (default) and 'exit'"
  ([slurm.conf.html](https://slurm.schedmd.com/slurm.conf.html#OPT_max_dbd_msg_action)).
  Under `discard`, slurmctld purges pending step start and complete messages
  first, then job start messages; once job completions and node state changes
  fill the freed space, "no new message is tracked creating data loss and
  potentially runaway jobs". Under `exit`, "the slurmctld will exit
  instead of discarding any messages". So "scheduling carries on" holds under
  the default only: with `exit`, a stall long enough to fill the queue stops the
  controller.

**So a blocked `sacct` is evidence about slurmdbd, not about the scheduler.**
Diagnosing "scheduling has stopped" from a hanging accounting query is, in the
author's judgement (not measured), the most common wrong turn here.

## Steps

1. Query `diagnostics` first. **DBD Agent queue size** is the direct signal: a
   climbing value means accounting is backing up.
2. Query `config` and read `MaxDBDMsgs`, `SlurmctldParameters` and
   `AccountingStorageEnforce`. The first is the ceiling for the queue in the
   previous step. In the second, `max_dbd_msg_action=exit` means slurmctld will
   exit when that ceiling is reached; if the option is absent, the action is the
   default, `discard`. The third tells you whether accounting limits are being
   enforced at all.
3. Query `nodes` and `queue`. If jobs are still starting and completing,
   scheduling is alive regardless of what `sacct` is doing. Say so explicitly.
4. Attempt `accounting`. A **timeout is a finding**, not an error to retry
   (slurm-mcp times the call out and says so) — it distinguishes a blocked path
   from an empty result.
5. Discriminate by **which commands hang**, the pattern S01 recorded. If only
   `sacct` hangs while `sinfo`, `squeue` and `sbatch` respond, look at the
   accounting path. If `sbatch`, `squeue` or `sinfo` hang as well, the
   controller itself is blocked or saturated: go to `state-save-unwritable` and
   `controller-rpc-saturation`.
6. Separate the accounting failure shapes: an unbounded wait (the path is
   stalled) versus an immediate error (the path is broken or misconfigured).

## When the storage problem is the controller's own

A controller that cannot write `StateSaveLocation` is a different failure. When
that directory was made unwritable in
[slurm-rca-bench S06](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S06-state-save-unwritable/scenario.yaml)
(`chmod 500`), `sbatch` was rejected with an I/O error at t+12s. A state-save
filesystem that *hangs* instead of failing is expected to block slurmctld
silently — that is S06's own caveat — and has not been measured. See
`state-save-unwritable`.

## What not to conclude

- **Do not report "storage stall halted scheduling"** without showing jobs
  failing to start. Slurm documents the cache, and S01's fully probed run
  observed scheduling continue. The documented exception is
  `max_dbd_msg_action=exit`, under which reaching the cap stops slurmctld.
- Missing job history is a reporting problem, not an availability problem.
  State the user-visible impact accurately.
- **Do not suggest restarting slurmctld to clear an accounting stall.** The
  stall is on the slurmdbd side, and restarting slurmctld does nothing about it
  (the author's reasoning, not measured). Slurm documents how a start goes
  wrong while slurmdbd is down: a first start, with no saved cache, needs
  slurmdbd responding; and under `max_dbd_msg_action=exit`, "It will be
  impossible to start the slurmctld with this option where the slurmdbd is down
  and the slurmctld is tracking more than MaxDBDMsgs" (slurm.conf.html, above).
  An ordinary restart does recover the cache slurmctld wrote at shutdown, so do
  not claim otherwise to justify the advice.

## Escalate when

- The DBD Agent queue is climbing and not draining after the underlying storage
  recovers — queued records should flush on their own.
- The DBD Agent queue is approaching `MaxDBDMsgs`: under `discard` accounting
  records will be dropped, under `exit` slurmctld will stop. The decision about
  the backend belongs to a human.
- Anyone proposes restarting slurmctld while slurmdbd is not responding.
