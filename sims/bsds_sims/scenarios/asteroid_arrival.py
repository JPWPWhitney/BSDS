"""Arrival at asteroid Bennu: slow hyperbolic approach, insertion burn, 1 km orbit.

Bennu is a custom point-mass gravity body (``createCustomGravObject`` — no
SPICE); the frame is Bennu-centered inertial. Scales are real: mu is a few
m³/s², orbital speeds are centimeters per second, and the final ~1 km orbit
takes about a day. The approach hyperbola is aimed analytically so its
periapsis sits at the target orbit radius; at periapsis one impulsive burn
(the ``scenarioOrbitManeuver`` velocity-state-modification pattern, as in
``hohmann.py``) circularizes the orbit, then the spacecraft coasts ~1.5 orbits.

The orbit plane contains the inertial y/z axes, so the orbit normal lies along
x̂ — read x̂ as the notional sun line and this is a terminator-ish orbit.
"""

from __future__ import annotations

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, simIncludeGravBody
from Basilisk.utilities import simHelpers

from bsds_sims.recording import RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "asteroid_arrival"
TITLE = "Arrival at Bennu"
KIND = "single"
DESCRIPTION = "Drift up to an asteroid at walking pace, brake, and settle into a 1 km orbit."

BENNU_BODY = {"name": "bennu", "mu": 4.892, "radius_km": 0.245}

DEFAULTS = {
    "approach_speed_ms": 0.15,  # |v| at the approach range (m/s)
    "approach_range_km": 5.0,   # initial distance from Bennu's center
    "orbit_radius_km": 1.0,     # target circular orbit radius
    "n_orbits": 1.5,            # coast after insertion, in final-orbit periods
}
EPOCH = "2026-01-01T00:00:00Z"

DT_S = 30.0   # RK4 step; relative energy drift per arc ~1e-12 at these speeds
REC_S = 60.0  # recorder cadence → ~2800 samples over the ~46 h mission


def _time_to_periapsis(mu: float, a: float, e: float, r0: float) -> float:
    """Time from radius r0 (inbound) to periapsis on a hyperbola (a < 0, e > 1)."""
    cosh_H = (1.0 - r0 / a) / e
    H = np.arccosh(cosh_H)
    M = e * np.sinh(H) - H
    n = np.sqrt(mu / (-a) ** 3)
    return float(M / n)


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}
    mu = BENNU_BODY["mu"]
    radius_m = BENNU_BODY["radius_km"] * 1e3
    v0 = float(p["approach_speed_ms"])
    r0 = float(p["approach_range_km"]) * 1e3
    rp = float(p["orbit_radius_km"]) * 1e3

    # Approach hyperbola with periapsis at the target orbit radius.
    energy = 0.5 * v0**2 - mu / r0
    if energy <= 0.0:
        raise ValueError("approach is not hyperbolic; raise approach_speed_ms")
    a = -mu / (2.0 * energy)  # < 0
    e = 1.0 - rp / a
    v_peri = np.sqrt(v0**2 - 2.0 * mu / r0 + 2.0 * mu / rp)
    cos_gamma = (rp * v_peri) / (r0 * v0)  # h = r v cos(γ) matched to periapsis
    if cos_gamma > 1.0:
        raise ValueError("periapsis unreachable; lower orbit_radius_km or approach_speed_ms")
    sin_gamma = np.sqrt(1.0 - cos_gamma**2)  # inbound: radial velocity < 0

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(DT_S)))

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    scSim.AddModelToTask("dynamicsTask", scObject)

    gravFactory = simIncludeGravBody.gravBodyFactory()
    bennu = gravFactory.createCustomGravObject("bennu", mu, radEquator=radius_m)
    bennu.isCentralBody = True
    gravFactory.addBodiesTo(scObject)

    # Terminator-ish geometry: orbit plane = y–z, orbit normal along the
    # notional sun line x̂. Start at r0 up the z axis, drifting in.
    p_hat = np.array([0.0, 0.0, 1.0])
    t_hat = np.array([0.0, 1.0, 0.0])
    scObject.hub.r_CN_NInit = (r0 * p_hat)[:, None]
    scObject.hub.v_CN_NInit = (v0 * (-sin_gamma * p_hat + cos_gamma * t_hat))[:, None]

    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=REC_S)
    scSim.InitializeSimulation()

    pos_ref = scObject.dynManager.getStateObject(scObject.hub.nameOfHubPosition)
    vel_ref = scObject.dynManager.getStateObject(scObject.hub.nameOfHubVelocity)

    # Arc 1: coast down the hyperbola to periapsis (burn time snapped to the
    # integration grid; the burn below circularizes from the actual state, so
    # sub-step timing slack cannot tilt the final orbit).
    t_burn = round(_time_to_periapsis(mu, a, e, r0) / DT_S) * DT_S
    scSim.ConfigureStopTime(macros.sec2nano(t_burn))
    scSim.ExecuteSimulation()

    # Insertion burn: kill the radial rate and set circular speed at the
    # current radius, staying in the orbit plane.
    r_vec = np.array(simHelpers.EigenVector3d2np(pos_ref.getState()), dtype=np.float64)
    v_vec = np.array(simHelpers.EigenVector3d2np(vel_ref.getState()), dtype=np.float64)
    r_burn = float(np.linalg.norm(r_vec))
    r_hat = r_vec / r_burn
    v_transverse = v_vec - (v_vec @ r_hat) * r_hat
    v_new = np.sqrt(mu / r_burn) * v_transverse / np.linalg.norm(v_transverse)
    insertion_dv = float(np.linalg.norm(v_new - v_vec))
    vel_ref.setState(simHelpers.np2EigenVectorXd(v_new))

    # Arc 2: coast n_orbits of the final orbit.
    period_s = 2.0 * np.pi * np.sqrt(r_burn**3 / mu)
    scSim.ConfigureStopTime(macros.sec2nano(t_burn + float(p["n_orbits"]) * period_s))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(rec)
    t, channels = dedupe_time(t, channels)
    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    channels["altitude"] = radius[:, None] - radius_m

    # Measure the achieved orbit from the recorded arc: mean post-burn radius,
    # and the period implied by the angle actually swept after insertion.
    post = t >= t_burn
    r_final = float(radius[post].mean())
    u = channels["r_BN_N"][post]
    u = u / np.linalg.norm(u, axis=1)[:, None]
    swept = float(np.arccos(np.clip(np.sum(u[:-1] * u[1:], axis=1), -1.0, 1.0)).sum())
    period_measured_s = (t[post][-1] - t[post][0]) * 2.0 * np.pi / swept

    metrics = {
        "approach_speed_ms": v0,
        "insertion_dv_ms": insertion_dv,
        "final_orbit_radius_km": r_final / 1e3,
        "orbit_period_h": period_measured_s / 3600.0,
        "burn_t_s": t_burn,
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[dict(BENNU_BODY)],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — {p['approach_range_km']:.0f} km out → {p['orbit_radius_km']:.1f} km orbit",
    )
