---
name: partition-limit-starvation
description: Diagnose one account or user whose jobs never start while the cluster sits partly idle. Use when a specific group reports they can never get resources, when jobs pend indefinitely with idle nodes visible, or when someone suspects unfair scheduling.
allowed-tools: slurm_query, slurm_overview, slurm_describe
---

# Partition limit starvation

## The shape

**One account's jobs never start while the cluster sits half idle.** Idle nodes
plus pending jobs looks like a broken scheduler and almost never is. It is
usually a limit doing exactly what it was configured to do, years ago, for a
reason nobody remembers.

The candidates, roughly in order of how often they turn out to be the answer:

- a **QOS** limit — `MaxJobsPerUser`, `MaxTRESPerUser`, `GrpTRES`;
- an **association** limit on the account in `sacctmgr`;
- a **partition** limit — `MaxTime` shorter than the job's request, `MaxNodes`
  smaller than the job, or an `AllowAccounts` list the account is not on;
- **fairshare** having driven the account's share factor to near zero.

These are indistinguishable from the queue alone and trivially distinguishable
once you read the reason code and the limits.

## Steps

1. Query `queue` filtered to the affected user or account, and read the reason.
   `QOSMaxJobsPerUserLimit`, `AssocMaxJobsLimit`, `PartitionTimeLimit` and
   friends name the limit outright — this often ends the investigation.
2. Query `nodes`. Confirm the idle nodes are in a partition the account is
   actually allowed to use. Idle capacity in a partition they cannot reach is
   not available to them, and the cluster-wide view hides this.
3. Query `config` for the partition definition: `MaxTime`, `MaxNodes`,
   `AllowAccounts`, `AllowQos`.
4. Query `fairshare`. A share factor near zero starves without any limit being
   hit, and looks identical from the queue.
5. Query `priority` for the pending jobs and read the fairshare factor
   specifically, to separate "limited" from "deprioritised".

## What not to conclude

- **Do not conclude the scheduler is unfair.** Fairshare working as designed
  looks exactly like starvation to the account being de-prioritised. Whether
  the configured shares are the *right* shares is a policy question for a
  human, not a fault.
- **Do not read idle nodes as available capacity** without checking partition
  membership and limits. This is the most common wrong turn here.
- Do not recommend raising a limit before establishing which limit binds.
  Raising the wrong one changes nothing and erodes trust in the next
  recommendation.

## Escalate when

No limit is binding, the share factor is healthy, nodes are idle and reachable,
and jobs still do not start. That is not a limits problem.
