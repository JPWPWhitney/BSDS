import numpy as np
import pytest

from bsds_sims.scenarios import SCENARIOS
from bsds_sims.scenarios import basic_orbit

MU_EARTH = 3.986004415e14
R_EARTH_M = 6378.1366e3


def test_registry_contains_basic_orbit():
    assert "basic_orbit" in SCENARIOS
    assert SCENARIOS["basic_orbit"].KIND == "single"


def test_basic_orbit_runs_and_is_sane():
    res = basic_orbit.run({})
    n = len(res.time_s)
    assert n > 100
    r = res.channels["r_BN_N"]
    v = res.channels["v_BN_N"]
    assert r.shape == (n, 3) and v.shape == (n, 3)
    assert np.all(np.isfinite(r)) and np.all(np.isfinite(v))

    # Default orbit: a = 6878.137 km, e = 0.01 → radius within a(1±e), ±5 km slack
    radius = np.linalg.norm(r, axis=1)
    a, e = 6878.137e3, 0.01
    assert radius.min() > a * (1 - e) - 5e3
    assert radius.max() < a * (1 + e) + 5e3

    # Period metric within 2% of the analytic value
    period_analytic_min = 2 * np.pi * np.sqrt(a**3 / MU_EARTH) / 60.0
    assert res.metrics["period_min"] == pytest.approx(period_analytic_min, rel=0.02)

    # Covers at least one full orbit
    assert res.time_s[-1] >= period_analytic_min * 60.0

    assert res.epoch == "2026-01-01T00:00:00Z"
    assert res.bodies[0]["name"] == "earth"


def test_hohmann_reaches_target_orbit():
    from bsds_sims.scenarios import hohmann

    res = hohmann.run({})
    r = res.channels["r_BN_N"]
    v = res.channels["v_BN_N"]
    radius = np.linalg.norm(r, axis=1)

    r1 = 6878.137e3
    r2 = 42164.0e3

    # Final state: circular-ish orbit at the target radius
    r_f, v_f = r[-1], v[-1]
    rf = np.linalg.norm(r_f)
    assert rf == pytest.approx(r2, rel=0.01)
    # eccentricity from state vector
    h = np.cross(r_f, v_f)
    e_vec = np.cross(v_f, h) / MU_EARTH - r_f / rf
    assert np.linalg.norm(e_vec) < 0.02

    # Metrics match analytic Hohmann
    at = (r1 + r2) / 2
    dv1 = np.sqrt(MU_EARTH * (2 / r1 - 1 / at)) - np.sqrt(MU_EARTH / r1)
    dv2 = np.sqrt(MU_EARTH / r2) - np.sqrt(MU_EARTH * (2 / r2 - 1 / at))
    assert res.metrics["dv1_ms"] == pytest.approx(dv1, rel=0.01)
    assert res.metrics["dv2_ms"] == pytest.approx(dv2, rel=0.01)
    assert res.metrics["dv_total_ms"] == pytest.approx(dv1 + dv2, rel=0.01)
    assert res.metrics["transfer_time_h"] == pytest.approx(np.pi * np.sqrt(at**3 / MU_EARTH) / 3600.0, rel=0.01)

    # Trajectory actually spans LEO to GEO
    assert radius.min() < r1 * 1.02
    assert radius.max() > r2 * 0.99


def test_drag_deorbit_high_drag_comes_down():
    from bsds_sims.scenarios import drag_deorbit

    res = drag_deorbit.run({"ballistic_coeff": 12.5, "alt_km": 250.0})
    alt_km = res.channels["altitude"][:, 0] / 1e3
    # Terminates at the 100 km interface, within 10 days
    assert alt_km[-1] <= 105.0
    assert res.metrics["deorbit_time_h"] < 10 * 24
    assert res.metrics["capped"] is False
    # Apogee trend is downward: last quarter's max well below first quarter's max
    q = len(alt_km) // 4
    assert alt_km[-q:].max() < alt_km[:q].max() - 20.0


def test_drag_deorbit_low_drag_stays_up():
    from bsds_sims.scenarios import drag_deorbit

    res = drag_deorbit.run({"ballistic_coeff": 100.0, "alt_km": 400.0, "max_days": 2.0})
    alt_km = res.channels["altitude"][:, 0] / 1e3
    assert res.metrics["capped"] is True
    assert alt_km[-1] > 350.0


def test_drag_deorbit_sweep_grid_shape():
    from bsds_sims.scenarios import drag_deorbit

    grid = drag_deorbit.sweep_grid()
    assert len(grid) == 16
    assert {"ballistic_coeff", "alt_km"} <= set(grid[0].keys())
    assert len(drag_deorbit.AXES) == 2
