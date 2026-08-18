import json

import numpy as np

from bsds_sims import bsd1
from bsds_sims.build import build_site_data


def test_build_single_scenario(tmp_path):
    out = tmp_path / "data"
    build_site_data(out, only_scenario="basic_orbit")

    index = json.loads((out / "index.json").read_text())
    assert index["schema"] == 1
    ids = [s["id"] for s in index["scenarios"]]
    assert ids == ["basic_orbit"]

    manifest = json.loads((out / "basic_orbit" / "manifest.json").read_text())
    assert manifest["id"] == "basic_orbit"
    assert manifest["kind"] == "single"
    assert manifest["hero"] in [r["id"] for r in manifest["runs"]]

    run_meta = manifest["runs"][0]
    f = out / "basic_orbit" / run_meta["file"]
    assert f.stat().st_size == run_meta["bytes"]
    run = bsd1.read_run(f)
    assert run.header["n"] > 100
    r = run.channel("r_BN_N")
    assert r is not None and np.all(np.isfinite(r))


def test_build_sweep_scenario_downsampled(tmp_path):
    out = tmp_path / "data"
    # Tiny probe cap keeps the test fast; every sweep member gets capped.
    build_site_data(out, only_scenario="drag_deorbit", sweep_overrides={"max_days": 0.05}, downsample_sweep=200)

    manifest = json.loads((out / "drag_deorbit" / "manifest.json").read_text())
    assert manifest["kind"] == "sweep"
    assert len(manifest["axes"]) == 2
    assert len(manifest["runs"]) == 16
    for run_meta in manifest["runs"]:
        f = out / "drag_deorbit" / run_meta["file"]
        run = bsd1.read_run(f)
        assert run.header["n"] <= 200 or run_meta["id"] == manifest["hero"]
        assert "deorbit_time_h" in run_meta["metrics"]
    # Hero run is full fidelity f32
    hero_meta = next(r for r in manifest["runs"] if r["id"] == manifest["hero"])
    hero = bsd1.read_run(out / "drag_deorbit" / hero_meta["file"])
    assert all(ch["dtype"] == "f32" for ch in hero.header["channels"])


def test_build_exports_lab_templates(tmp_path):
    import json as _json

    out = tmp_path / "data"
    build_site_data(out, only_scenario="basic_orbit")
    tj = _json.loads((out / "templates.json").read_text())
    ids = [t["id"] for t in tj["templates"]]
    assert "basic_orbit" in ids and "drag_deorbit" in ids
    src = (out / "templates" / "basic_orbit.py").read_text()
    assert "def run(" in src and "from bsds_sims.recording import" in src


def test_build_exports_wasm_pylib(tmp_path):
    out = tmp_path / "data"
    build_site_data(out, only_scenario="basic_orbit")
    pylib = out / "pylib" / "bsds_sims"
    for name in ("__init__.py", "bsd1.py", "recording.py"):
        assert (pylib / name).exists()
    assert "BSDS0001" in (pylib / "bsd1.py").read_text()
