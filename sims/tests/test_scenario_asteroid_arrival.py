import numpy as np
import pytest

from bsds_sims.scenarios import asteroid_arrival

MU_BENNU = 4.892  # m^3/s^2
R_BENNU_M = 245.0
TARGET_RADIUS_M = 1000.0


@pytest.fixture(scope="module")
def res():
    return asteroid_arrival.run({})


def test_registry_contract(res):
    assert asteroid_arrival.ID == "asteroid_arrival"
    assert asteroid_arrival.TITLE == "Arrival at Bennu"
    assert asteroid_arrival.KIND == "single"
    # The web player switches to the non-Earth renderer off this body name.
    assert res.bodies == [{"name": "bennu", "mu": 4.892, "radius_km": 0.245}]


def test_runs_finite_and_well_shaped(res):
    n = len(res.time_s)
    assert n > 1000
    assert np.all(np.diff(res.time_s) > 0)
    for name in ("r_BN_N", "v_BN_N", "sigma_BN", "omega_BN_B"):
        assert res.channels[name].shape == (n, 3)
        assert np.all(np.isfinite(res.channels[name]))
    assert res.channels["altitude"].shape == (n, 1)
    assert np.all(np.isfinite(res.channels["altitude"]))


def test_altitude_always_positive(res):
    assert np.all(res.channels["altitude"] > 0.0)


def test_final_orbit_radius_bounded_and_constant(res):
    radius = np.linalg.norm(res.channels["r_BN_N"], axis=1)
    period_s = 2 * np.pi * np.sqrt(TARGET_RADIUS_M**3 / MU_BENNU)
    last_orbit = res.time_s >= res.time_s[-1] - period_s
    r_last = radius[last_orbit]
    assert len(r_last) > 100
    # Bounded: within 20% of the 1 km target.
    assert res.metrics["final_orbit_radius_km"] == pytest.approx(1.0, rel=0.2)
    assert TARGET_RADIUS_M * 0.8 < r_last.min()
    assert r_last.max() < TARGET_RADIUS_M * 1.2
    # Roughly constant: max/min over the last orbit stays tight.
    assert r_last.max() / r_last.min() < 1.5


def test_period_metric_matches_analytic(res):
    a = res.metrics["final_orbit_radius_km"] * 1e3
    period_analytic_h = 2 * np.pi * np.sqrt(a**3 / MU_BENNU) / 3600.0
    assert res.metrics["orbit_period_h"] == pytest.approx(period_analytic_h, rel=0.2)


def test_burn_metrics_match_analytic_insertion(res):
    v0 = asteroid_arrival.DEFAULTS["approach_speed_ms"]
    r0 = asteroid_arrival.DEFAULTS["approach_range_km"] * 1e3
    rp = asteroid_arrival.DEFAULTS["orbit_radius_km"] * 1e3
    assert res.metrics["approach_speed_ms"] == pytest.approx(v0)
    # Periapsis speed on the approach hyperbola vs. circular speed at rp.
    v_peri = np.sqrt(v0**2 - 2 * MU_BENNU / r0 + 2 * MU_BENNU / rp)
    dv_analytic = v_peri - np.sqrt(MU_BENNU / rp)
    assert res.metrics["insertion_dv_ms"] == pytest.approx(dv_analytic, rel=0.05)
