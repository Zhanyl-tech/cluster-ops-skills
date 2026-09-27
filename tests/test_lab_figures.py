"""The reproduction script for the simulator figures, against a fake ``schedlab``.

The real lab is another repository, so CI cannot run it. This checks the part
that lives here: that the script parses the lab's output and summarises it the
way the runbooks and claims.yaml describe.
"""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lab_figures.py"

# Canned output in the lab CLI's format at c02b52f (only the lines the script reads).
FAKE_SCHEDLAB = """#!{python}
import sys
args = sys.argv[1:]
seed = int(args[args.index("--seed") + 1])
if "--compare-backfill" in args:
    print("backfill OFF")
    print(f"  cpu utilization  {{60 + seed}}.0 %")
    print(f"  mean wait  {{1000 + seed}}.0 min")
    print("backfill ON")
    print(f"  cpu utilization  {{80 + seed}}.0 %")
    print(f"  mean wait  {{250 + seed}}.0 min")
else:
    for w, u, m in ((0, 70, 200), (1000, 75, 300), (10000, 80, 400), (100000, 90, 800)):
        print(f"  weight={{w:<7}}  util {{u:5.1f}}%  mean wait {{m:7.1f}} min  p95 1.0 min")
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lab_figures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_schedlab(tmp_path: Path) -> str:
    p = tmp_path / "schedlab"
    p.write_text(FAKE_SCHEDLAB.format(python=sys.executable), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_summarises_backfill_and_sweeps(
    fake_schedlab: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _load().main(["--schedlab", fake_schedlab]) == 0
    out = capsys.readouterr().out
    assert "backfill OFF utilization 60.0-69.0%" in out
    assert "backfill ON  utilization 80.0-89.0%" in out
    assert "utilization gain: 20.0-20.0 points, in 10/10 seeds" in out
    assert "sweep jobsize   utilization span up to 20.0 points" in out
    assert "mean-wait max/min up to 4.00x" in out


def test_refuses_output_it_cannot_parse(tmp_path: Path) -> None:
    p = tmp_path / "schedlab"
    p.write_text(f"#!{sys.executable}\nprint('backfill ON')\n", encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    with pytest.raises(ValueError, match="pinned lab commit"):
        _load().compare_backfill(str(p))
