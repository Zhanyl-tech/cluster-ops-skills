---
name: evidence-is-gone
description: Decide whether a cluster incident is still diagnosable, and abstain when it is not. Use when investigating a node that already rebooted, an intermittent failure with no pattern, or any incident where logs have rotated and the evidence window has closed. Also use to sanity-check a confident diagnosis.
allowed-tools: mcp__slurm-mcp__slurm_query mcp__slurm-mcp__slurm_overview mcp__slurm-mcp__slurm_describe
---

# The evidence is gone

## Abstention is a correct answer

Most runbooks assume the answer is findable. Some incidents are not, and the
skill that matters is recognising it before producing a confident diagnosis
that happens to be wrong.

Two shapes recur:

- **The node rebooted.** Whatever caused it lived in memory and in logs that
  did not survive. What remains is the fact of the reboot and its timing.
- **One job in fifty fails, with no pattern.** No node, user, partition or
  time-of-day correlation. Intermittent at low rate across a large fleet is
  often genuinely undiagnosable from scheduler state alone.

[slurm-rca-bench](https://github.com/Zhanyl-tech/slurm-rca-bench) includes
scenarios that are deliberately undiagnosable, and scores **full credit for
abstaining and zero for naming even the most plausible cause**. That grading
exists because a confident wrong diagnosis is more expensive than an admission
of ignorance: it sends someone to replace healthy hardware, and it stops the
search.

## Steps

1. Establish the **evidence window**. When did the event happen, and what
   retains state across it? A reboot ends most windows.
2. Query `nodes` and read the reason field. After a reboot, this is frequently
   the only surviving artefact.
3. Query `accounting` around the event. Completed-job records outlive the node
   and are often the last remaining evidence.
4. Test for correlation before asserting one. Across the failing set, is there
   a shared node, user, partition, time window, or job shape? **If you cannot
   name the correlation, you do not have one.**
5. If the window has closed, say so. Report what *is* known — timing, blast
   radius, what was ruled out — and state plainly that the cause is not
   recoverable from available evidence.
6. Recommend what to capture *next time*. Turning an undiagnosable incident
   into a diagnosable one is the real deliverable here.

## What not to conclude

- **Do not name the most plausible cause when the evidence is gone.** Plausible
  is not measured. In the author's judgement (not measured) this is among the
  most expensive mistakes in cluster diagnosis, and slurm-rca-bench grades it as
  worse than abstention for that reason.
- **Do not treat absence of evidence as evidence of absence.** "No errors in
  the logs" after a rotation means the logs are gone, not that there were no
  errors.
- **Do not manufacture a correlation from a small sample.** Three failures on
  one node out of a fleet of forty may be chance; say so rather than draining
  it.
- Do not let queue pressure push you into a guess. The cost of being wrong does
  not fall when people are waiting.

## Escalate when

The evidence window has closed on anything with real blast radius. A human
needs to decide whether to accept the unknown or to instrument and wait for a
recurrence.
