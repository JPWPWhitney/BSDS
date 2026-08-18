"""One spacecraft, point-mass Earth gravity, ~1 LEO orbit.

Self-contained BSDS scenario modeled on Basilisk's official scenarioBasicOrbit.
"""

from __future__ import annotations

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody

from ..recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "basic_orbit"
TITLE = "Basic Orbit"
KIND = "single"
DESCRIPTION = "A spacecraft in low Earth orbit — the hello-world of astrodynamics."

DEFAULTS = {"alt_km": 500.0, "ecc": 0.01, "inc_deg": 51.6}
EPOCH = "2026-01-01T00:00:00Z"


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}

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
    oe.a = EARTH_BODY["radius_km"] * 1e3 + p["alt_km"] * 1e3
    oe.e = p["ecc"]
    oe.i = p["inc_deg"] * macros.D2R
    oe.Omega = 48.2 * macros.D2R
    oe.omega = 347.8 * macros.D2R
    oe.f = 0.0
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN
    scObject.hub.v_CN_NInit = vN

    period_s = 2 * np.pi * np.sqrt(oe.a**3 / mu)
    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=5.0)

    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(macros.sec2nano(1.05 * period_s))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(rec)
    t, channels = dedupe_time(t, channels)
    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    channels["altitude"] = radius[:, None] - EARTH_BODY["radius_km"] * 1e3

    metrics = {
        "period_min": period_s / 60.0,
        "alt_min_km": float((radius.min() - EARTH_BODY["radius_km"] * 1e3) / 1e3),
        "alt_max_km": float((radius.max() - EARTH_BODY["radius_km"] * 1e3) / 1e3),
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — {p['alt_km']:.0f} km, i={p['inc_deg']:.1f}°",
    )
