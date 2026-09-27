# Operator hand-off: is this allocation actually using its GPUs?

Outside the slurm-mcp surface; for a human with the relevant access. All
read-only. None of these is grounds on its own to cancel anyone's job.

## From Slurm, if it records GPU utilization

When `AccountingStorageTRES` includes `gres/gpu`, Slurm gathers `gres/gpuutil`
and `gres/gpumem` from GPU jobs on NVIDIA GPUs with `AutoDetect=nvml` (AMD with
`AutoDetect=rsmi`); it does not for MIG devices
([gres.html](https://slurm.schedmd.com/gres.html)).

- `sacct -j <job>.<step> --format=TRESUsageInAve -p` for a finished step. The
  value is a **high-water mark**: `TRESUsageIn[Ave|Tot]` "represent the
  average/total of the highest watermarks over all ranks in the step"
  ([sacct.html](https://slurm.schedmd.com/sacct.html)), and gres.html calls the
  gpuutil values "highwater marks" and reads them "After the job has finished".
  A peak of zero says the step never used its GPUs. A non-zero peak says only
  that it did at some point: a job that ran and then hung still shows the peak
  from before it hung.
- `sstat -j <job>.<step> --format=TRESUsageInAve -p` for a running step. Per the
  same sacct.html entry, under `sstat` these values are "the average/total at
  the moment the command was run". Whether `sstat` reports `gres/gpuutil` is not
  shown on sacct.html, gres.html or
  [sstat.html](https://slurm.schedmd.com/sstat.html) (unverified). Where it
  does, read it several times, minutes apart.

## On the node

- `nvidia-smi -q -d UTILIZATION,PIDS -i <gpu>` — utilization and the processes
  holding the GPU. `UTILIZATION` and `PIDS` are valid `-d` values
  ([nvidia-smi](https://docs.nvidia.com/deploy/nvidia-smi/index.html)).
  A process holding GPU memory at zero utilization is the "hung" or "finished
  but never exited" shape; no process at all is "never started".
- One sample is a moment, not a pattern. Read several, minutes apart, before
  calling anything idle.
