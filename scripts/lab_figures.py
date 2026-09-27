"""Reproduce the slurm-scheduler-lab figures quoted in the scheduler runbooks.

The runbooks quote ranges across seeds rather than one run, because a single
seed of a synthetic workload is one draw, not a measurement of backfill. This
script is how those ranges were produced, so a reader can rerun it rather than
believe it.

It drives the lab's own CLI (``schedlab``) and only summarises its output.
Pin the lab to the commit the runbooks cite before running::

    git clone https://github.com/Zhanyl-tech/slurm-scheduler-lab
    git -C slurm-scheduler-lab checkout c02b52fd0ccdd2b748f2599574f97f68d92248cb
    python -m venv lab-venv && lab-venv/bin/pip install ./slurm-scheduler-lab
    python scripts/lab_figures.py --schedlab lab-venv/bin/schedlab

Everything it prints is simulator output on a seeded *synthetic* workload
(300 jobs, 16 simulated nodes of 8 CPUs and 2 GPUs, the lab's defaults for the
rest). It is not a Slurm measurement and not a replayed site trace.
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
from collections.abc import Sequence

JOBS = "300"
SEEDS = tuple(range(10))
FACTORS = ("age", "fairshare", "jobsize", "qos")


def _run(schedlab: str, *args: str) -> str:
    return subprocess.run([schedlab, *args], capture_output=True, text=True, check=True).stdout


def _metric(block: str, label: str) -> float:
    m = re.search(re.escape(label) + r"\s+([\d.]+)", block)
    if m is None:
        raise ValueError(f"schedlab output has no {label!r}; is this the pinned lab commit?")
    return float(m.group(1))


def compare_backfill(schedlab: str) -> list[tuple[int, float, float, float, float]]:
    """(seed, util_off, wait_off, util_on, wait_on) for every seed."""
    rows = []
    for seed in SEEDS:
        out = _run(schedlab, "--compare-backfill", "--jobs", JOBS, "--seed", str(seed))
        off, on = out.split("backfill ON")
        rows.append(
            (
                seed,
                _metric(off, "cpu utilization"),
                _metric(off, "mean wait"),
                _metric(on, "cpu utilization"),
                _metric(on, "mean wait"),
            )
        )
    return rows


def sweep(schedlab: str, factor: str) -> tuple[list[float], list[float]]:
    """Per seed: utilization span (points) and mean-wait max/min ratio across weights."""
    spans, ratios = [], []
    pat = re.compile(r"util\s+([\d.]+)%\s+mean wait\s+([\d.]+)")
    for seed in SEEDS:
        out = _run(schedlab, "--sweep", factor, "--jobs", JOBS, "--seed", str(seed))
        points = [(float(u), float(w)) for u, w in pat.findall(out)]
        if not points:
            raise ValueError(f"no sweep rows for {factor} seed {seed}")
        utils = [p[0] for p in points]
        waits = [p[1] for p in points]
        spans.append(max(utils) - min(utils))
        ratios.append(max(waits) / min(waits))
    return spans, ratios


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schedlab", required=True, help="path to the lab's schedlab CLI")
    args = parser.parse_args(argv)

    rows = compare_backfill(args.schedlab)
    for seed, u_off, w_off, u_on, w_on in rows:
        print(f"seed {seed}: OFF {u_off:.1f}% {w_off:.1f} min | ON {u_on:.1f}% {w_on:.1f} min")
    gain = [r[3] - r[1] for r in rows]
    cut = [1 - r[4] / r[2] for r in rows]
    print(f"backfill OFF utilization {min(r[1] for r in rows)}-{max(r[1] for r in rows)}%")
    print(f"backfill ON  utilization {min(r[3] for r in rows)}-{max(r[3] for r in rows)}%")
    print(f"backfill OFF mean wait {min(r[2] for r in rows)}-{max(r[2] for r in rows)} min")
    print(f"backfill ON  mean wait {min(r[4] for r in rows)}-{max(r[4] for r in rows)} min")
    print(
        f"utilization gain: {min(gain):.1f}-{max(gain):.1f} points, in {sum(g > 0 for g in gain)}"
        f"/{len(gain)} seeds"
    )
    print(
        f"mean-wait cut: {min(cut):.0%}-{max(cut):.0%}, in {sum(c > 0 for c in cut)}"
        f"/{len(cut)} seeds"
    )

    for factor in FACTORS:
        spans, ratios = sweep(args.schedlab, factor)
        print(
            f"sweep {factor:<9} utilization span up to {max(spans):.1f} points "
            f"(median {statistics.median(spans):.1f}); mean-wait max/min up to "
            f"{max(ratios):.2f}x (median {statistics.median(ratios):.2f}x)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
