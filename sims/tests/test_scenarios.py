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
