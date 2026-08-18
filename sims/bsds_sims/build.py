"""Build the site data directory: run scenarios, export BSD1 runs + manifests.

CLI:  python -m bsds_sims.build --out ../data [--scenario ID] [--downsample-sweep 1500]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from pathlib import Path

import numpy as np

from . import bsd1
from .recording import RunResult
from .scenarios import SCENARIOS


def _run_id(params: dict) -> str:
    if not params:
        return "default"
    parts = []
    for key in sorted(params):
        val = params[key]
        s = f"{val:g}" if isinstance(val, (int, float)) else str(val)
        parts.append(f"{key[:3]}{s}")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", "_".join(parts))


def _downsample(res: RunResult, max_samples: int) -> RunResult:
    n = len(res.time_s)
    if n <= max_samples:
        return res
    idx = np.unique(np.round(np.linspace(0, n - 1, max_samples)).astype(int))
    return RunResult(
        time_s=res.time_s[idx],
        channels={k: v[idx] for k, v in res.channels.items()},
        bodies=res.bodies,
        metrics=res.metrics,
        epoch=res.epoch,
        title=res.title,
    )


def _export(res: RunResult, path: Path, scenario_id: str, run_id: str, params: dict, dtype: str) -> int:
    channels = [
        bsd1.Channel(name, data, unit="m" if name in ("r_BN_N", "altitude") else "", frame="inertial" if name.endswith("_N") else "", dtype=dtype)
        for name, data in res.channels.items()
    ]
    return bsd1.write_run(
        path,
        scenario=scenario_id,
        run=run_id,
        title=res.title,
        epoch=res.epoch,
        params=params,
        time_s=res.time_s,
        channels=channels,
        bodies=res.bodies,
        metrics={k: v for k, v in res.metrics.items()},
    )


def build_site_data(
    out_dir: str | Path,
    only_scenario: str | None = None,
    downsample_sweep: int = 1500,
    sweep_overrides: dict | None = None,
) -> dict:
    """Run scenarios and write <out>/index.json plus per-scenario data. Returns the index."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index: dict = {"schema": 1, "scenarios": []}

    for scenario_id, mod in SCENARIOS.items():
        if only_scenario and scenario_id != only_scenario:
            continue
        scenario_dir = out / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        if mod.KIND == "single":
            param_sets = [{}]
            hero_params: dict = {}
        else:
            param_sets = mod.sweep_grid()
            hero_params = {k: v for k, v in mod.DEFAULTS.items() if k in {a["param"] for a in mod.AXES}}

        hero_id = _run_id(hero_params)
        runs_meta = []
        for params in param_sets:
            run_id = _run_id(params)
            is_hero = run_id == hero_id
            run_params = dict(params)
            if sweep_overrides and mod.KIND == "sweep":
                run_params = {**run_params, **sweep_overrides}
            print(f"[build] {scenario_id}/{run_id} ...", flush=True)
            res = mod.run(run_params)
            if not is_hero and mod.KIND == "sweep":
                res = _downsample(res, downsample_sweep)
            fname = f"{run_id}.bsd1"
            nbytes = _export(
                res,
                scenario_dir / fname,
                scenario_id,
                run_id,
                params,
                dtype="f32" if is_hero or mod.KIND == "single" else "i16",
            )
            runs_meta.append({
                "id": run_id,
                "params": params,
                "file": fname,
                "bytes": nbytes,
                "metrics": res.metrics,
            })

        manifest = {
            "schema": 1,
            "id": scenario_id,
            "title": mod.TITLE,
            "kind": mod.KIND,
            "description": mod.DESCRIPTION,
            "hero": hero_id,
            "axes": getattr(mod, "AXES", []),
            "runs": runs_meta,
        }
        (scenario_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
        index["scenarios"].append({
            "id": scenario_id,
            "title": mod.TITLE,
            "kind": mod.KIND,
            "description": mod.DESCRIPTION,
            "path": f"{scenario_id}/manifest.json",
        })

    (out / "index.json").write_text(json.dumps(index, indent=1))
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build BSDS site data from Basilisk scenarios")
    parser.add_argument("--out", required=True, help="output data directory")
    parser.add_argument("--scenario", default=None, help="build only this scenario id")
    parser.add_argument("--downsample-sweep", type=int, default=1500)
    args = parser.parse_args(argv)
    try:
        index = build_site_data(args.out, only_scenario=args.scenario, downsample_sweep=args.downsample_sweep)
    except Exception:
        traceback.print_exc()
        return 1
    if not index["scenarios"]:
        print("[build] ERROR: no scenarios built", file=sys.stderr)
        return 1
    print(f"[build] done: {len(index['scenarios'])} scenario(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
