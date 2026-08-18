import numpy as np
import pytest

from bsds_sims.scenarios import ground_pointing

R_EARTH_M = 6378.1366e3


@pytest.fixture(scope="module")
def res():
    return ground_pointing.run({})


def test_contract_attributes():
    assert ground_pointing.ID == "ground_pointing"
    assert ground_pointing.TITLE == "Ground-Station Pointing"
    assert ground_pointing.KIND == "single"
    assert isinstance(ground_pointing.DESCRIPTION, str) and ground_pointing.DESCRIPTION


def test_runs_finite_with_expected_channels(res):
    n = len(res.time_s)
    assert n > 100
    assert np.all(np.diff(res.time_s) > 0)
    expected = {"r_BN_N", "v_BN_N", "sigma_BN", "omega_BN_B", "altitude", "pointing_error"}
    assert expected <= set(res.channels)
    for name in ("r_BN_N", "v_BN_N", "sigma_BN", "omega_BN_B"):
        assert res.channels[name].shape == (n, 3)
    assert res.channels["altitude"].shape == (n, 1)
    assert res.channels["pointing_error"].shape == (n, 1)
    for arr in res.channels.values():
        assert np.all(np.isfinite(arr))
    # Near-circular 550 km orbit stays in its altitude band
    alt_km = res.channels["altitude"][:, 0] / 1e3
    assert alt_km.min() > 500.0 and alt_km.max() < 600.0
    assert res.epoch == "2026-01-01T00:00:00Z"
    assert res.bodies[0]["name"] == "earth"


def test_pointing_error_slews_down_to_plateau(res):
    err_deg = np.degrees(res.channels["pointing_error"][:, 0])
    # Starts well off-target...
    assert err_deg[0] > 15.0
    # ...and settles: the post-slew plateau (second half of the run) sits far
    # below the initial error, small in absolute terms too.
    plateau = err_deg[len(err_deg) // 2 :].mean()
    assert plateau < err_deg[0] / 5.0
    assert plateau < 3.0


def test_metrics(res):
    m = res.metrics
    assert m["min_pointing_error_deg"] < 5.0
    # Station marker metrics required by the web player
    assert m["station_lat_deg"] == pytest.approx(40.01)
    assert m["station_lon_deg"] == pytest.approx(-105.26)
    # Mean error is over the visibility window; the pass exists and is sane
    assert m["max_elevation_deg"] > 10.0
    assert 0.0 < m["mean_pointing_error_deg"] < 15.0
    for v in m.values():
        assert isinstance(v, float)
