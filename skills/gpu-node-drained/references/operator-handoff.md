# Operator hand-off: checking a GPU node

Everything here runs **on the node itself**, with the access a GPU
administrator has. It is outside the slurm-mcp surface. An agent using this
skill should hand these checks to a human with the node name, the drain reason
verbatim and the GPU index, not attempt them. Read-only checks come first; the
one intrusive check is marked.

## Read-only

- `nvidia-smi -q -d ECC,ROW_REMAPPER -i <gpu>` — ECC error counts and, on GPUs
  that remap rows, remapped and pending rows. `ECC` and `ROW_REMAPPER` are both
  valid `-d` values, and `-i` selects the GPU by index, serial, UUID or PCI bus
  ID ([nvidia-smi](https://docs.nvidia.com/deploy/nvidia-smi/index.html)). On
  GPUs that retire pages instead, use `-d PAGE_RETIREMENT`.
- **Xid messages in the kernel log.** "The Xid message is an error report from
  the NVIDIA driver that is printed to the operating system's kernel log or event
  log", and NVIDIA notes it "can be indicative of a hardware problem, an NVIDIA
  software problem, or a user application problem"
  ([Xid errors](https://docs.nvidia.com/deploy/xid-errors/introduction.html)).
  Look each code up in NVIDIA's catalog before calling it hardware
  ([Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html)).
- `dcgmi health -g <group> -c` — reports the health watches previously enabled
  for that group with `dcgmi health -g <group> -s <flags>`; with no watches set
  it has nothing to report
  ([DCGM feature overview](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html)).

## Intrusive: drained nodes only

- `dcgmi diag -r 3` — DCGM's level 3 diagnostic, which includes the Targeted
  Stress and Targeted Power plugins that load the GPUs. NVIDIA lists it, as
  measured on Hopper GPU systems, at under 10 minutes on 4-GPU systems and
  under 35 minutes on 8-GPU systems — plan a drain window on another GPU
  generation from its own timings, not these — and
  describes level 3 and level 4 tests as "to be run by an administrator as
  post-mortem"
  ([DCGM diagnostics](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/dcgm-diagnostics.html)).
  Run it only on a node that is already drained and empty. Never run it on a
  node with jobs to "prove" the node is healthy while the queue waits.

## What these checks do not settle

- A clean result after the fact does not clear a node that logged a fault;
  record both, and let the owner of the node decide.
- Returning the node to service (`scontrol update nodename=<node> state=resume`)
  is a human decision taken after these checks, never a step in them.
