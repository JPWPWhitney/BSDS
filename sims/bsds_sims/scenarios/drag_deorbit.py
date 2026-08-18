"""Atmospheric drag deorbit: how long until it comes down?

Exponential atmosphere + cannonball drag on a LEO spacecraft, propagated in
chunks until the 100 km interface (or a max-duration cap). Swept over
ballistic coefficient × initial altitude.

Atmosphere: single-scale-height exponential fitted to the 150–400 km band
(rho(250 km) = 6e-11 kg/m³, H = 45 km — representative of medium solar
activity). Not valid below ~120 km, which is fine: runs terminate at 100 km.
"""

from __future__ import annotations

import numpy as np

from Basilisk.simulation import dragDynamicEffector, exponentialAtmosphere, spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody

from ..recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "drag_deorbit"
TITLE = "Drag Deorbit"
KIND = "sweep"
DESCRIPTION = "How long until it comes down? Atmospheric drag vs ballistic coefficient."

AXES = [
    {"param": "ballistic_coeff", "label": "Ballistic coefficient (kg/m²)", "values": [12.5, 25.0, 50.0, 100.0]},
    {"param": "alt_km", "label": "Initial altitude (km)", "values": [200.0, 250.0, 300.0, 350.0]},
]

DEFAULTS = {"ballistic_coeff": 25.0, "alt_km": 300.0, "max_days": 30.0}
EPOCH = "2026-01-01T00:00:00Z"

# Atmosphere anchored to the LEO band (see module docstring)
RHO_250KM = 6.0e-11  # kg/m^3
SCALE_HEIGHT_M = 45.0e3
TERMINAL_ALT_M = 100.0e3
DRAG_COEFF = 2.2
AREA_M2 = 1.0
STEP_S = 30.0
CHUNK_S = 3 * 3600.0
RECORD_S = 120.0


def sweep_grid() -> list[dict]:
    return [
        {"ballistic_coeff": bc, "alt_km": alt}
        for bc in AXES[0]["values"]
        for alt in AXES[1]["values"]
    ]


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}
    bc = float(p["ballistic_coeff"])
    alt0_m = float(p["alt_km"]) * 1e3
    max_s = float(p["max_days"]) * 86400.0
    r_earth_m = EARTH_BODY["radius_km"] * 1e3

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(STEP_S)))

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    # Ballistic coefficient = m / (Cd * A); fix Cd and A, derive mass.
    scObject.hub.mHub = bc * DRAG_COEFF * AREA_M2

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    gravFactory.addBodiesTo(scObject)
    mu = earth.mu

    atmo = exponentialAtmosphere.ExponentialAtmosphere()
    atmo.ModelTag = "expAtmo"
    atmo.planetRadius = r_earth_m
    atmo.scaleHeight = SCALE_HEIGHT_M
    # baseDensity chosen so density at 250 km equals RHO_250KM
    atmo.baseDensity = RHO_250KM * np.exp(250.0e3 / SCALE_HEIGHT_M)
    atmo.addSpacecraftToModel(scObject.scStateOutMsg)

    drag = dragDynamicEffector.DragDynamicEffector()
    drag.ModelTag = "drag"
    drag.coreParams.projectedArea = AREA_M2
    drag.coreParams.dragCoeff = DRAG_COEFF
    drag.atmoDensInMsg.subscribeTo(atmo.envOutMsgs[0])
    scObject.addDynamicEffector(drag)

    scSim.AddModelToTask("dynamicsTask", atmo)
    scSim.AddModelToTask("dynamicsTask", drag)
    scSim.AddModelToTask("dynamicsTask", scObject)

    oe = orbitalMotion.ClassicElements()
    oe.a = r_earth_m + alt0_m
    oe.e = 0.0001
    oe.i = 51.6 * macros.D2R
    oe.Omega = 48.2 * macros.D2R
    oe.omega = 0.0
    oe.f = 0.0
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN
    scObject.hub.v_CN_NInit = vN

    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=RECORD_S)
    scSim.InitializeSimulation()

    # Propagate in chunks until the terminal altitude or the cap.
    t_stop = 0.0
    capped = True
    while t_stop < max_s:
        t_stop = min(t_stop + CHUNK_S, max_s)
        scSim.ConfigureStopTime(macros.sec2nano(t_stop))
        scSim.ExecuteSimulation()
        r_now = np.array(rec.r_BN_N[-1], dtype=np.float64)
        if np.linalg.norm(r_now) - r_earth_m <= TERMINAL_ALT_M:
            capped = False
            break

    t, channels = pull_sc_channels(rec)
    t, channels = dedupe_time(t, channels)
    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    alt = radius - r_earth_m
    channels["altitude"] = alt[:, None]

    if capped:
        deorbit_time_h = max_s / 3600.0
    else:
        below = np.nonzero(alt <= TERMINAL_ALT_M)[0]
        deorbit_time_h = float(t[below[0]] / 3600.0) if len(below) else float(t[-1] / 3600.0)

    metrics = {
        "deorbit_time_h": deorbit_time_h,
        "capped": capped,
        "final_alt_km": float(alt[-1] / 1e3),
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — BC={bc:g} kg/m², h₀={p['alt_km']:.0f} km",
    )
