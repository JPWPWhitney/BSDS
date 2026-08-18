"""Generate the committed web decoder test fixture.

Run from repo root:  python sims/tests/make_web_fixtures.py
Writes web/test/fixtures/sample.bsd1 + sample.expected.json. The vitest
suite decodes the binary and compares against the JSON — proving the
TypeScript decoder matches the Python writer byte-for-byte.
"""

import json
from pathlib import Path

import numpy as np

from bsds_sims import bsd1

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "test" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

n = 50
t = np.linspace(0.0, 490.0, n)
r = np.stack(
    [
        7.0e6 * np.cos(t / 1000.0),
        7.0e6 * np.sin(t / 1000.0),
        1.0e5 * np.sin(t / 500.0),
    ],
    axis=1,
)
sigma = np.stack([0.1 * np.sin(t / 200.0), np.full(n, 0.25), np.linspace(-0.4, 0.4, n)], axis=1)

path = OUT / "sample.bsd1"
bsd1.write_run(
    path,
    scenario="fixture",
    run="sample",
    title="Fixture run",
    epoch="2026-01-01T00:00:00Z",
    params={"k": 2.0},
    time_s=t,
    channels=[
        bsd1.Channel("r_BN_N", r, unit="m", frame="inertial", dtype="f32"),
        bsd1.Channel("sigma_BN", sigma, dtype="i16"),
    ],
    bodies=[{"name": "earth", "mu": 3.986004415e14, "radius_km": 6378.1366}],
    metrics={"score": 1.5},
)

back = bsd1.read_run(path)
expected = {
    "header_subset": {
        "scenario": "fixture",
        "run": "sample",
        "epoch": "2026-01-01T00:00:00Z",
        "n": n,
        "params": {"k": 2.0},
        "metrics": {"score": 1.5},
    },
    "time_first5": back.time_s[:5].tolist(),
    "time_last": back.time_s[-1],
    "r_BN_N_first3": back.channel("r_BN_N")[:3].tolist(),
    "r_BN_N_last": back.channel("r_BN_N")[-1].tolist(),
    "sigma_BN_first3": back.channel("sigma_BN")[:3].tolist(),
    "sigma_scale_bound": [
        (sigma[:, c].max() - sigma[:, c].min()) / 65534.0 / 2.0 for c in range(3)
    ],
    "sigma_BN_raw_first3": sigma[:3].tolist(),
}
(OUT / "sample.expected.json").write_text(json.dumps(expected, indent=1))
print("fixtures written to", OUT)
