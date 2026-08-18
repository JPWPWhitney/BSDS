import numpy as np
import pytest

# Direct module import on purpose: this scenario is not yet in the registry.
from bsds_sims.scenarios import attitude_detumble

SETTLE_RATE_RADS = 1.0e-3


@pytest.fixture(scope="module")
def res():
    return attitude_detumble.run({})


def test_contract_attributes():
    assert attitude_detumble.ID == "attitude_detumble"
    assert attitude_detumble.KIND == "single"
    assert attitude_detumble.TITLE == "Reaction-Wheel Detumble"


def test_runs_with_finite_channels(res):
    n = len(res.time_s)
    assert n > 100
    assert np.all(np.diff(res.time_s) > 0)

    expected_shapes = {
        "r_BN_N": (n, 3),
        "v_BN_N": (n, 3),
        "sigma_BN": (n, 3),
        "omega_BN_B": (n, 3),
        "rw_speeds": (n, 3),
        "altitude": (n, 1),
    }
    for name, shape in expected_shapes.items():
        assert res.channels[name].shape == shape, name
        assert np.all(np.isfinite(res.channels[name])), name

    assert res.epoch == "2026-01-01T00:00:00Z"
    assert res.bodies[0]["name"] == "earth"


def test_detumbles_to_inertial_hold(res):
    omega_mag = np.linalg.norm(res.channels["omega_BN_B"], axis=1)
    # starts tumbling, ends still
    assert omega_mag[0] > 0.1
    assert omega_mag[-1] < SETTLE_RATE_RADS
    # points at the inertial reference at the end
    assert res.metrics["pointing_error_final_deg"] < 1.0


def test_settle_time_consistent_with_omega_channel(res):
    assert res.metrics["settled"] is True
    settle_s = res.metrics["settle_time_min"] * 60.0
    t = res.time_s
    omega_mag = np.linalg.norm(res.channels["omega_BN_B"], axis=1)

    # settle time is one of the recorded sample times, within the run
    i = int(np.argmin(np.abs(t - settle_s)))
    assert t[i] == pytest.approx(settle_s, abs=1e-9)
    assert 0 < settle_s < t[-1]

    # |omega| stays below the threshold from the settle time onward...
    assert np.all(omega_mag[i:] < SETTLE_RATE_RADS)
    # ...and was above it at the preceding sample (it is the FIRST such time)
    assert omega_mag[i - 1] >= SETTLE_RATE_RADS


def test_rw_speeds_spin_up(res):
    ws = res.channels["rw_speeds"]
    assert ws.shape[1] == 3
    # wheels start at rest and absorb the tumble momentum
    assert np.allclose(ws[0], 0.0)
    assert np.abs(ws).max() > 1.0  # rad/s, clearly nonzero
    # each wheel moved at some point (all three axes had rate to absorb)
    assert np.all(np.abs(ws).max(axis=0) > 1.0)
    # metric agrees with the channel, and stays below HR16 saturation (6000 RPM)
    rpm = np.abs(ws).max() * 30.0 / np.pi
    assert res.metrics["max_rw_speed_rpm"] == pytest.approx(rpm)
    assert 10.0 < rpm < 6000.0
