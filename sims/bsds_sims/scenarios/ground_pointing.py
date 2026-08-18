"""Ground-station pointing: continuously slew the boresight onto Boulder.

Self-contained BSDS scenario modeled on Basilisk's official scenarioAttLocPoint:
groundLocation publishes the station's inertial position, locationPointing
turns that into a 2-axis attitude-error message (body +Z boresight), and
mrpFeedback closes the loop through an external control torque on the hub.

Planet-rotation simplification (inherited from the official example): the
groundLocation module's planetInMsg is deliberately left unconnected, so the
planet orientation stays at its identity default and the station is FIXED in
the inertial frame at lat 40.01 deg / lon -105.26 deg (no Earth rotation, no
SPICE kernels). Pass geometry repeats every orbit. The station_lat_deg /
station_lon_deg metrics carry the geodetic location for the web player's
station marker.

Control loop honesty note: FSW and dynamics share one 10 s task, i.e. a
0.1 Hz zero-order-hold control loop. Gains are tuned down from the official
example (which uses 1 s steps) to keep the discrete loop stable; the visible
few-degree tracking lag at closest approach is the real cost of the slow loop.
"""

from __future__ import annotations

import numpy as np

from Basilisk.architecture import messaging
from Basilisk.fswAlgorithms import locationPointing, mrpFeedback
from Basilisk.simulation import extForceTorque, groundLocation, simpleNav, spacecraft
from Basilisk.utilities import RigidBodyKinematics as rbk
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody

from bsds_sims.recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "ground_pointing"
TITLE = "Ground-Station Pointing"
KIND = "single"
DESCRIPTION = "A satellite slews to keep its antenna locked on Boulder as it flies over."

# RAAN 217 deg puts the ascending pass close to (but not exactly over) the
# station's fixed inertial position: max elevation ~68 deg.
DEFAULTS = {"alt_km": 550.0, "inc_deg": 51.6, "raan_deg": 217.0}
EPOCH = "2026-01-01T00:00:00Z"

STATION_LAT_DEG = 40.01
STATION_LON_DEG = -105.26
STATION_ALT_M = 1620.0
MIN_ELEVATION_DEG = 10.0

STEP_S = 10.0
RECORD_S = 5.0
N_ORBITS = 1.2
PHAT_B = [0.0, 0.0, 1.0]  # boresight: body +Z

# Rigid-body properties and gains (official scenarioAttLocPoint bus, gains
# retuned for the 10 s discrete loop; boresight rate damping is required for
# stability of the 2-axis pointing law).
INERTIA = [900.0, 0.0, 0.0, 0.0, 800.0, 0.0, 0.0, 0.0, 600.0]
HUB_MASS_KG = 750.0
FSW_K = 2.0
FSW_P = 40.0


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}
    r_earth_m = EARTH_BODY["radius_km"] * 1e3

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(STEP_S)))

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    scObject.hub.mHub = HUB_MASS_KG
    scObject.hub.IHubPntBc_B = [INERTIA[0:3], INERTIA[3:6], INERTIA[6:9]]
    scSim.AddModelToTask("dynamicsTask", scObject)

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    gravFactory.addBodiesTo(scObject)
    mu = earth.mu

    oe = orbitalMotion.ClassicElements()
    oe.a = r_earth_m + p["alt_km"] * 1e3
    oe.e = 0.0001
    oe.i = p["inc_deg"] * macros.D2R
    oe.Omega = p["raan_deg"] * macros.D2R
    oe.omega = 0.0
    oe.f = 0.0
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN
    scObject.hub.v_CN_NInit = vN
    scObject.hub.sigma_BNInit = [[0.1], [0.2], [-0.3]]  # start well off-target
    scObject.hub.omega_BN_BInit = [[0.001], [-0.01], [0.02]]

    # Control torque enters the dynamics as an external effector.
    extFT = extForceTorque.ExtForceTorque()
    extFT.ModelTag = "controlTorque"
    scObject.addDynamicEffector(extFT)
    scSim.AddModelToTask("dynamicsTask", extFT)

    sNav = simpleNav.SimpleNav()
    sNav.ModelTag = "simpleNav"
    scSim.AddModelToTask("dynamicsTask", sNav)
    sNav.scStateInMsg.subscribeTo(scObject.scStateOutMsg)

    # Boulder ground station. planetInMsg intentionally NOT connected: planet
    # orientation stays identity, station fixed in the inertial frame (see
    # module docstring).
    station = groundLocation.GroundLocation()
    station.ModelTag = "boulderStation"
    station.planetRadius = r_earth_m
    station.specifyLocation(
        np.radians(STATION_LAT_DEG), np.radians(STATION_LON_DEG), STATION_ALT_M
    )
    station.minimumElevation = np.radians(MIN_ELEVATION_DEG)
    station.maximumRange = 1e9
    station.addSpacecraftToModel(scObject.scStateOutMsg)
    scSim.AddModelToTask("dynamicsTask", station)

    # FSW: point body +Z at the station, MRP feedback -> commanded torque.
    locPoint = locationPointing.locationPointing()
    locPoint.ModelTag = "locationPointing"
    scSim.AddModelToTask("dynamicsTask", locPoint)
    locPoint.pHat_B = PHAT_B
    locPoint.useBoresightRateDamping = 1
    locPoint.scAttInMsg.subscribeTo(sNav.attOutMsg)
    locPoint.scTransInMsg.subscribeTo(sNav.transOutMsg)
    locPoint.locationInMsg.subscribeTo(station.currentGroundStateOutMsg)

    mrpControl = mrpFeedback.mrpFeedback()
    mrpControl.ModelTag = "mrpFeedback"
    scSim.AddModelToTask("dynamicsTask", mrpControl)
    mrpControl.guidInMsg.subscribeTo(locPoint.attGuidOutMsg)
    mrpControl.K = FSW_K
    mrpControl.Ki = -1.0  # integral feedback off
    mrpControl.P = FSW_P
    mrpControl.integralLimit = 2.0 / mrpControl.Ki * 0.1
    extFT.cmdTorqueInMsg.subscribeTo(mrpControl.cmdTorqueOutMsg)

    vehConfigMsg = messaging.VehicleConfigMsg().write(
        messaging.VehicleConfigMsgPayload(ISCPntB_B=INERTIA)
    )
    mrpControl.vehConfigInMsg.subscribeTo(vehConfigMsg)

    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=RECORD_S)
    stationRec = station.currentGroundStateOutMsg.recorder(macros.sec2nano(RECORD_S))
    accessRec = station.accessOutMsgs[0].recorder(macros.sec2nano(RECORD_S))
    scSim.AddModelToTask("dynamicsTask", stationRec)
    scSim.AddModelToTask("dynamicsTask", accessRec)

    period_s = 2 * np.pi * np.sqrt(oe.a**3 / mu)
    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(macros.sec2nano(N_ORBITS * period_s))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(rec)
    # Ride the shared dedupe mask by stashing the extra recorder outputs as
    # temporary channels (all recorders share the task's time base).
    channels["_r_LN_N"] = np.asarray(stationRec.r_LN_N, dtype=np.float64)
    channels["_elev"] = np.asarray(accessRec.elevation, dtype=np.float64)
    t, channels = dedupe_time(t, channels)
    r_LN_N = channels.pop("_r_LN_N")
    elev_rad = channels.pop("_elev")

    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    channels["altitude"] = radius[:, None] - r_earth_m

    # Pointing error: angle between the body boresight and the spacecraft ->
    # station line of sight, recomputed from the recorded states.
    pHat_B = np.array(PHAT_B)
    n = len(t)
    err_rad = np.empty(n)
    for k in range(n):
        BN = rbk.MRP2C(channels["sigma_BN"][k])  # DCM: inertial -> body
        boresight_N = BN.T @ pHat_B
        los_N = r_LN_N[k] - channels["r_BN_N"][k]
        los_N /= np.linalg.norm(los_N)
        err_rad[k] = np.arccos(np.clip(boresight_N @ los_N, -1.0, 1.0))
    channels["pointing_error"] = err_rad[:, None]

    visible = elev_rad > np.radians(MIN_ELEVATION_DEG)
    mean_err_rad = err_rad[visible].mean() if visible.any() else err_rad.mean()
    metrics = {
        "min_pointing_error_deg": float(np.degrees(err_rad.min())),
        "mean_pointing_error_deg": float(np.degrees(mean_err_rad)),
        "station_lat_deg": STATION_LAT_DEG,
        "station_lon_deg": STATION_LON_DEG,
        "max_elevation_deg": float(np.degrees(elev_rad.max())),
        "visible_min": float(visible.sum() * np.median(np.diff(t)) / 60.0),
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — Boulder from {p['alt_km']:.0f} km",
    )
