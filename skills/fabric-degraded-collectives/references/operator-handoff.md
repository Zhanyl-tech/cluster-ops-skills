# Operator hand-off: checking the fabric and the transport

These run on the nodes (and, for fabric-wide scans, from a host with access to
the subnet manager's view). They are outside the slurm-mcp surface. An agent
using this skill should hand them to a human with the node set and the job IDs,
not attempt them. Everything below is read-only **as written**; the one way to
destroy evidence is called out.

## Is NCCL using RDMA?

- Rerun a slow job, or a small reproduction, with `NCCL_DEBUG=INFO` and
  `NCCL_DEBUG_SUBSYS=INIT,NET` — `INFO` "prints debug information", and `NET` is
  the network subsystem
  ([NCCL environment variables](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html)).
  Read which network NCCL initialised. The exact log wording is not specified on
  that page, so confirm it against a known-good job on the same cluster rather
  than a remembered string.
- Check `NCCL_IB_HCA`, `NCCL_IB_DISABLE` and `NCCL_NET` in the job's environment.

## Is a link degraded?

- `ibstat` on each suspect host — output "includes LID, SMLID, port state, link
  width active, and port physical state"
  ([ibstat(8)](https://github.com/linux-rdma/rdma-core/blob/master/infiniband-diags/man/ibstat.8.in.rst)).
  Compare width and rate with what the hardware should negotiate, not just the
  state.
- `iblinkinfo` — "reports link info for each port in an IB fabric, node by node"
  ([iblinkinfo(8)](https://github.com/linux-rdma/rdma-core/blob/master/infiniband-diags/man/iblinkinfo.8.in.rst)),
  which finds narrow or slow links you did not already suspect.
- `perfquery <lid> <port>` — the basic PortCounters include the error counters;
  `-x` shows "extended port counters rather than (basic) port counters"
  ([perfquery(8)](https://github.com/linux-rdma/rdma-core/blob/master/infiniband-diags/man/perfquery.8.in.rst)).
  **Never pass `-r` (`--reset_after_read`) or `-R` (`--Reset_only`):** perfquery
  can "reset after read, or just reset the counters", which erases exactly the
  evidence being collected, and anyone else's view of it. Read twice, some
  minutes apart, and compare.

## How far below expected is it?

- nccl-tests `all_reduce_perf` across the suspect nodes and across a known-good
  pair. Compare the `busbw` column: NVIDIA's nccl-tests notes say bus bandwidth
  "should reflect the speed of the hardware bottleneck", which for a multi-node
  run is normally the network (reasoning)
  ([PERFORMANCE.md](https://github.com/NVIDIA/nccl-tests/blob/master/doc/PERFORMANCE.md)).
  Run it only on nodes you have drained or allocated for the purpose; it
  competes with any job sharing the links.
