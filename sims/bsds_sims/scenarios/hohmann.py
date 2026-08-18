"""Impulsive two-burn Hohmann transfer LEO → GEO.

Three propagation arcs with velocity-state modification between them —
the official scenarioOrbitManeuver pattern.
"""

from __future__ import annotations

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody
from Basilisk.utilities import simHelpers

from ..recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "hohmann"
TITLE = "Hohmann Transfer"
KIND = "single"
DESCRIPTION = "Two burns from low Earth orbit to geostationary altitude."

DEFAULTS = {"r_start_km": 6878.137, "r_target_km": 42164.0}
EPOCH = "2026-01-01T00:00:00Z"


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}
    r1 = p["r_start_km"] * 1e3
    r2 = p["r_target_km"] * 1e3

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(10.0)))

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    scSim.AddModelToTask("dynamicsTask", scObject)

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    gravFactory.addBodiesTo(scObject)
    mu = earth.mu

    oe = orbitalMotion.ClassicElements()
    oe.a = r1
    oe.e = 0.0001
    oe.i = 28.5 * macros.D2R
    oe.Omega = 48.2 * macros.D2R
    oe.omega = 0.0
    oe.f = 0.0
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN
    scObject.hub.v_CN_NInit = vN

    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=60.0)
    scSim.InitializeSimulation()

    vel_ref = scObject.dynManager.getStateObject(scObject.hub.nameOfHubVelocity)

    # Analytic burn magnitudes
    at = (r1 + r2) / 2.0
    v_t1 = np.sqrt(mu * (2.0 / r1 - 1.0 / at))
    v_final = np.sqrt(mu / r2)
    t_transfer = np.pi * np.sqrt(at**3 / mu)
    period1 = 2 * np.pi * np.sqrt(r1**3 / mu)
    period2 = 2 * np.pi * np.sqrt(r2**3 / mu)

    def _prograde_burn(target_speed: float) -> float:
        v_now = np.array(simHelpers.EigenVector3d2np(vel_ref.getState()), dtype=np.float64)
        speed = np.linalg.norm(v_now)
        v_new = v_now / speed * target_speed
        vel_ref.setState(simHelpers.np2EigenVectorXd(v_new))
        return float(target_speed - speed)

    # Arc 1: quarter of the parking orbit
    t1 = 0.25 * period1
    scSim.ConfigureStopTime(macros.sec2nano(t1))
    scSim.ExecuteSimulation()
    dv1 = _prograde_burn(v_t1)

    # Arc 2: half the transfer ellipse (to apoapsis)
    t2 = t1 + t_transfer
    scSim.ConfigureStopTime(macros.sec2nano(t2))
    scSim.ExecuteSimulation()
    dv2 = _prograde_burn(v_final)

    # Arc 3: quarter of the final orbit
    t3 = t2 + 0.25 * period2
    scSim.ConfigureStopTime(macros.sec2nano(t3))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(rec)
    t, channels = dedupe_time(t, channels)
    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    channels["altitude"] = radius[:, None] - EARTH_BODY["radius_km"] * 1e3

    metrics = {
        "dv1_ms": dv1,
        "dv2_ms": dv2,
        "dv_total_ms": dv1 + dv2,
        "transfer_time_h": t_transfer / 3600.0,
        "burn1_t_s": t1,
        "burn2_t_s": t2,
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — {p['r_start_km']:.0f} km → {p['r_target_km']:.0f} km",
    )
