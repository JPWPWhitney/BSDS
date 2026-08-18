import numpy as np
import pytest

from bsds_sims.scenarios import rendezvous

MU_EARTH = 3.986004415e14
R_EARTH_M = 6378.1366e3


@pytest.fixture(scope="module")
def res():
    return rendezvous.run({})


def test_contract_attributes():
    assert rendezvous.ID == "rendezvous"
    assert rendezvous.TITLE == "Orbital Rendezvous"
    assert rendezvous.KIND == "single"


def test_runs_with_finite_two_craft_channels(res):
    n = len(res.time_s)
    assert n > 100
    assert np.all(np.diff(res.time_s) > 0)
    for name, comps in (
        ("r_BN_N", 3), ("v_BN_N", 3), ("sigma_BN", 3), ("omega_BN_B", 3),
        ("r2_BN_N", 3), ("v2_BN_N", 3), ("altitude", 1), ("separation", 1),
    ):
        arr = res.channels[name]
        assert arr.shape == (n, comps), name
        assert np.all(np.isfinite(arr)), name
    assert res.epoch == "2026-01-01T00:00:00Z"
    assert res.bodies[0]["name"] == "earth"


def test_both_craft_stay_above_300km(res):
    alt_chaser_km = res.channels["altitude"][:, 0] / 1e3
    alt_target_km = (np.linalg.norm(res.channels["r2_BN_N"], axis=1) - R_EARTH_M) / 1e3
    assert alt_chaser_km.min() > 300.0
    assert alt_target_km.min() > 300.0


def test_separation_decreases_across_burn_milestones(res):
    sep = res.channels["separation"][:, 0]
    m = res.metrics

    def sep_at(t_s: float) -> float:
        return float(sep[np.argmin(np.abs(res.time_s - t_s))])

    s_start = sep_at(0.0)
    s_burn1 = sep_at(m["burn1_t_s"])
    s_mid = sep_at(0.5 * (m["burn1_t_s"] + m["burn2_t_s"]))
    s_end = float(sep[-1])
    assert s_start > s_burn1 > s_mid > s_end
    assert s_end < 1000.0


def test_final_coorbit_is_stable(res):
    # After the matching burn the standoff holds (no drift) for ~1.5 orbits.
    sep = res.channels["separation"][:, 0]
    tail = sep[res.time_s >= res.metrics["burn3_t_s"]]
    assert len(tail) > 100
    assert tail.max() < 1000.0
    assert tail.max() - tail.min() < 200.0


def test_metrics_match_analytic_design(res):
    m = res.metrics
    assert m["final_separation_m"] < 1000.0
    assert m["final_separation_m"] == pytest.approx(res.channels["separation"][-1, 0])

    d = rendezvous.DEFAULTS
    assert m["initial_separation_km"] == pytest.approx(
        np.hypot(d["behind_km"], d["below_km"]), rel=0.01
    )

    # Two-impulse Hohmann between the two circular radii dominates dv_total.
    r2 = (6378.1366 + d["alt_target_km"]) * 1e3
    r1 = r2 - d["below_km"] * 1e3
    a_h = 0.5 * (r1 + r2)
    dv1 = np.sqrt(MU_EARTH * (2 / r1 - 1 / a_h)) - np.sqrt(MU_EARTH / r1)
    dv2 = np.sqrt(MU_EARTH / r2) - np.sqrt(MU_EARTH * (2 / r2 - 1 / a_h))
    assert m["dv_total_ms"] == pytest.approx(dv1 + dv2, rel=0.01)
    assert m["transfer_time_h"] == pytest.approx(
        np.pi * np.sqrt(a_h**3 / MU_EARTH) / 3600.0, rel=0.01
    )
    assert m["burn1_t_s"] < m["burn2_t_s"] < m["burn3_t_s"] < res.time_s[-1]
