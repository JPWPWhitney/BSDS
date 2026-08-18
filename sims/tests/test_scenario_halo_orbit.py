import numpy as np
import pytest

from bsds_sims.scenarios import halo_orbit

A_MOON_KM = 384400.0


@pytest.fixture(scope="module")
def res():
    return halo_orbit.run({})


def test_contract_attributes():
    assert halo_orbit.ID == "halo_orbit"
    assert halo_orbit.TITLE == "Earth–Moon L2 Halo"
    assert halo_orbit.KIND == "single"
    assert "Lyapunov" in halo_orbit.DESCRIPTION  # honest naming of the planar orbit


def test_runs_finite_and_sampled(res):
    n = len(res.time_s)
    assert 2000 <= n <= 4000
    assert np.all(np.diff(res.time_s) > 0)
    for name in ("r_BN_N", "v_BN_N", "r_moon_N", "r_rel_l2"):
        assert res.channels[name].shape == (n, 3)
        assert np.all(np.isfinite(res.channels[name]))
    assert res.channels["altitude"].shape == (n, 1)
    assert np.all(np.isfinite(res.channels["altitude"]))


def test_moon_on_prescribed_circle(res):
    r_moon_km = np.linalg.norm(res.channels["r_moon_N"], axis=1) / 1e3
    assert np.all(r_moon_km > A_MOON_KM * 0.98)
    assert np.all(r_moon_km < A_MOON_KM * 1.02)
    # and it actually revolves: about 1 sidereal month over the 28-day run
    ang = np.unwrap(np.arctan2(res.channels["r_moon_N"][:, 1], res.channels["r_moon_N"][:, 0]))
    moon_revs = (ang[-1] - ang[0]) / (2 * np.pi)
    assert moon_revs == pytest.approx(res.metrics["sim_days"] / 27.2846, rel=0.01)


def test_spacecraft_stays_beyond_the_moon(res):
    radius_km = np.linalg.norm(res.channels["r_BN_N"], axis=1) / 1e3
    assert np.mean(radius_km > A_MOON_KM) > 0.95  # it lives at L2, outside the lunar orbit


def test_stays_in_l2_vicinity(res):
    assert res.metrics["l2_max_excursion_km"] < 100000.0
    exc_km = np.linalg.norm(res.channels["r_rel_l2"], axis=1) / 1e3
    assert res.metrics["l2_max_excursion_km"] == pytest.approx(exc_km.max())


def test_completes_at_least_one_revolution(res):
    assert res.metrics["revolutions_completed"] >= 1.0
    assert res.metrics["sim_days"] == pytest.approx(28.0, rel=0.01)


def test_bodies_and_epoch(res):
    assert [b["name"] for b in res.bodies] == ["earth", "moon"]
    assert res.bodies[1]["mu"] == pytest.approx(4.9028e12)
    assert res.bodies[1]["radius_km"] == pytest.approx(1737.4)
    assert res.epoch == "2026-01-01T00:00:00Z"
