---
name: partition-limit-starvation
description: Diagnose one account or user whose jobs never start while the cluster sits partly idle. Use when a specific group reports they can never get resources, when jobs pend indefinitely with idle nodes visible, or when someone suspects unfair scheduling.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# Partition limit starvation

## The shape

**One account's jobs never start while the cluster sits half idle.** Idle nodes
plus pending jobs looks like a broken scheduler and usually is not. It is
usually a limit doing exactly what it was configured to do, years ago, for a
reason nobody remembers.

The candidates (listed in no measured order):

- a **QOS** limit — `MaxJobsPerUser`, `MaxTRESPerUser`, `GrpTRES`;
- an **association** limit on the account in `sacctmgr`;
- a **partition** limit — `MaxTime` shorter than the job's request, `MaxNodes`
  smaller than the job, or an `AllowAccounts` list the account is not on;
- **fairshare** having driven the account's share factor to near zero.

These look the same from the queue view alone. The reason code usually tells
them apart.

## What this tool surface cannot read

slurm-mcp's `config` topic is `scontrol show config`, which prints global
`slurm.conf` parameters, **not partition definitions**. There is no topic for
QOS or association limits (`sacctmgr`). So `MaxTime`, `MaxNodes`,
`AllowAccounts`, `AllowQos`, QOS limits and association limits cannot be read
here. Absence of a limit in `config` output is **not** evidence that no limit
binds. Say which limits you could not read.

## Steps

1. Query `queue` filtered by `user` for an affected user, and read the reason.
   Slurm's reason codes name many limits outright — `QOSMaxJobsPerUserLimit`,
   `AssocMaxJobsLimit`, `AssocGrp…`, `PartitionTimeLimit`, `PartitionNodeLimit`
   ([job_reason_codes.html](https://slurm.schedmd.com/job_reason_codes.html)) —
   and that often ends the investigation. The `queue` topic has no account
   filter; list the account's users from `fairshare` filtered by `account`, then
   query each.
2. Query `config` and read `AccountingStorageEnforce`. Slurm's accounting guide:
   "To enable any limit enforcement you must at least have
   AccountingStorageEnforce=limits in your slurm.conf. Otherwise, even if you
   have limits set, they will not be enforced"
   ([accounting.html](https://slurm.schedmd.com/accounting.html)). If limits are
   not enforced, QOS and association limits cannot be what is binding.
   [slurm-rca-bench S08](https://github.com/Zhanyl-tech/slurm-rca-bench/blob/469ea760de677295a833f709b7713f06e36abff2/scenarios/S08-partition-limit-starvation/scenario.yaml)
   hit exactly this: with `AccountingStorageEnforce = none`, an association set
   to `GrpJobs=0` still accepted a job.
3. Query `nodes`. Confirm the idle nodes are in a partition the account may use.
   Idle capacity in a partition it cannot reach is not available to it, and the
   cluster-wide view hides this. Whether the account is *allowed* in a partition
   (`AllowAccounts`, `AllowQos`) is not readable here — ask a human for
   `scontrol show partition <name>`.
4. If the reason code does not name the limit, report that partition, QOS and
   association limits are outside this surface, and ask a human for
   `scontrol show partition`, `sacctmgr show qos` and `sacctmgr show assoc`.
5. Query `fairshare`. A share factor near zero starves without any limit being
   hit, and looks identical from the queue.
6. Query `priority` for the pending jobs and read the fairshare factor
   specifically, to separate "limited" from "deprioritised".

## What not to conclude

- **Do not report "no partition limit binds" from `config` output.** Partition
  limits are not in it.
- **Do not conclude the scheduler is unfair.** Fairshare working as designed
  looks exactly like starvation to the account being de-prioritised. Whether
  the configured shares are the *right* shares is a policy question for a
  human, not a fault.
- **Do not read idle nodes as available capacity** without checking partition
  membership and limits. In the author's judgement (not measured) this is the
  most common wrong turn here.
- Do not recommend raising a limit before establishing which limit binds.
  Raising the wrong one changes nothing and erodes trust in the next
  recommendation.

## Escalate when

- The reason code does not name the limit and partition, QOS or association
  limits are needed to finish the diagnosis. Hand over what you ruled out and
  which reads you could not make.
- No limit is binding, the share factor is healthy, nodes are idle and
  reachable, and jobs still do not start. That is not a limits problem.
