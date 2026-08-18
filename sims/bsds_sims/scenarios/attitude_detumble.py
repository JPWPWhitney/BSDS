"""Reaction-wheel detumble: null a tumble with MRP feedback flight software.

Self-contained BSDS scenario modeled on Basilisk's official
scenarioAttitudeFeedbackRW: a small spacecraft tumbling at ~11 deg/s spins up
three body-axis Honeywell HR16 reaction wheels, commanded by an
inertial3D -> attTrackingError -> mrpFeedback -> rwMotorTorque flight-software
chain, to null its rates and hold a fixed inertial attitude. Point-mass Earth
gravity on a LEO orbit (no SPICE, no kernels).
"""

from __future__ import annotations

import numpy as np

from Basilisk.architecture import messaging
from Basilisk.fswAlgorithms import attTrackingError, inertial3D, mrpFeedback, rwMotorTorque
from Basilisk.simulation import reactionWheelStateEffector, simpleNav, spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody, simIncludeRW

from bsds_sims.recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "attitude_detumble"
TITLE = "Reaction-Wheel Detumble"
KIND = "single"
DESCRIPTION = "A tumbling spacecraft spins up three reaction wheels to null its rates and hold an inertial attitude."

DEFAULTS = {
    "alt_km": 500.0,
    # initial tumble rate omega_BN_B [rad/s]
    "omega0_x": 0.1,
    "omega0_y": -0.15,
    "omega0_z": 0.08,
    # mrpFeedback gains (Ki < 0 disables integral feedback)
    "K": 0.2,
    "Ki": -1.0,
    "P": 1.0,
    "sim_min": 15.0,
}
EPOCH = "2026-01-01T00:00:00Z"

STEP_S = 0.5
RECORD_S = 2.0
SETTLE_RATE_RADS = 1.0e-3  # |omega| threshold defining "detumbled"

# Small agile spacecraft: 100 kg hub, principal inertias in kg*m^2
HUB_MASS_KG = 100.0
HUB_INERTIA = [12.0, 10.0, 8.0]
SIGMA_BN_INIT = [0.1, 0.2, -0.3]
RW_MAX_MOMENTUM_NMS = 50.0  # Honeywell HR16, small momentum option


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(STEP_S)))

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    Ix, Iy, Iz = HUB_INERTIA
    scObject.hub.mHub = HUB_MASS_KG
    scObject.hub.r_BcB_B = [[0.0], [0.0], [0.0]]
    scObject.hub.IHubPntBc_B = [[Ix, 0.0, 0.0], [0.0, Iy, 0.0], [0.0, 0.0, Iz]]

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    gravFactory.addBodiesTo(scObject)
    mu = earth.mu

    oe = orbitalMotion.ClassicElements()
    oe.a = EARTH_BODY["radius_km"] * 1e3 + p["alt_km"] * 1e3
    oe.e = 0.01
    oe.i = 51.6 * macros.D2R
    oe.Omega = 48.2 * macros.D2R
    oe.omega = 347.8 * macros.D2R
    oe.f = 0.0
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN
    scObject.hub.v_CN_NInit = vN
    scObject.hub.sigma_BNInit = [[s] for s in SIGMA_BN_INIT]
    scObject.hub.omega_BN_BInit = [[p["omega0_x"]], [p["omega0_y"]], [p["omega0_z"]]]

    # Three balanced HR16 wheels on the body axes, torque-limited, starting at rest.
    rwFactory = simIncludeRW.rwFactory()
    for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
        rwFactory.create("Honeywell_HR16", axis, maxMomentum=RW_MAX_MOMENTUM_NMS, Omega=0.0, useMaxTorque=True)
    rwStateEffector = reactionWheelStateEffector.ReactionWheelStateEffector()
    rwFactory.addToSpacecraft("RW_cluster", rwStateEffector, scObject)

    sNavObject = simpleNav.SimpleNav()
    sNavObject.ModelTag = "simpleNav"

    # FSW chain: hold the identity inertial attitude.
    inertial3DObj = inertial3D.inertial3D()
    inertial3DObj.ModelTag = "inertial3D"
    inertial3DObj.sigma_R0N = [0.0, 0.0, 0.0]

    attError = attTrackingError.attTrackingError()
    attError.ModelTag = "attError"

    mrpControl = mrpFeedback.mrpFeedback()
    mrpControl.ModelTag = "mrpFeedback"
    mrpControl.K = p["K"]
    mrpControl.Ki = p["Ki"]
    mrpControl.P = p["P"]
    if p["Ki"] > 0:
        mrpControl.integralLimit = 2.0 / p["Ki"] * 0.1

    rwMotorTorqueObj = rwMotorTorque.rwMotorTorque()
    rwMotorTorqueObj.ModelTag = "rwMotorTorque"
    rwMotorTorqueObj.controlAxes_B = [1, 0, 0, 0, 1, 0, 0, 0, 1]

    scSim.AddModelToTask("dynamicsTask", scObject, 1)
    scSim.AddModelToTask("dynamicsTask", rwStateEffector, 2)
    scSim.AddModelToTask("dynamicsTask", sNavObject)
    scSim.AddModelToTask("dynamicsTask", inertial3DObj)
    scSim.AddModelToTask("dynamicsTask", attError)
    scSim.AddModelToTask("dynamicsTask", mrpControl)
    scSim.AddModelToTask("dynamicsTask", rwMotorTorqueObj)

    # Stand-alone FSW config messages
    vehicleConfigOut = messaging.VehicleConfigMsgPayload()
    vehicleConfigOut.ISCPntB_B = [Ix, 0.0, 0.0, 0.0, Iy, 0.0, 0.0, 0.0, Iz]
    vcMsg = messaging.VehicleConfigMsg().write(vehicleConfigOut)
    fswRwParamMsg = rwFactory.getConfigMessage()

    # Message wiring (the scenarioAttitudeFeedbackRW loop)
    sNavObject.scStateInMsg.subscribeTo(scObject.scStateOutMsg)
    attError.attNavInMsg.subscribeTo(sNavObject.attOutMsg)
    attError.attRefInMsg.subscribeTo(inertial3DObj.attRefOutMsg)
    mrpControl.guidInMsg.subscribeTo(attError.attGuidOutMsg)
    mrpControl.vehConfigInMsg.subscribeTo(vcMsg)
    mrpControl.rwParamsInMsg.subscribeTo(fswRwParamMsg)
    mrpControl.rwSpeedsInMsg.subscribeTo(rwStateEffector.rwSpeedOutMsg)
    rwMotorTorqueObj.rwParamsInMsg.subscribeTo(fswRwParamMsg)
    rwMotorTorqueObj.vehControlInMsg.subscribeTo(mrpControl.cmdTorqueOutMsg)
    rwStateEffector.rwMotorCmdInMsg.subscribeTo(rwMotorTorqueObj.rwMotorTorqueOutMsg)

    rec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=RECORD_S)
    rwRec = rwStateEffector.rwSpeedOutMsg.recorder(macros.sec2nano(RECORD_S))
    scSim.AddModelToTask("dynamicsTask", rwRec)

    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(macros.sec2nano(p["sim_min"] * 60.0))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(rec)
    # wheelSpeeds payload is a fixed MAX_EFF_CNT-wide array; keep the 3 real wheels.
    # rwRec runs on the same task at the same cadence, so its samples align with rec's.
    channels["rw_speeds"] = np.asarray(rwRec.wheelSpeeds, dtype=np.float64)[:, :3]
    t, channels = dedupe_time(t, channels)

    radius = np.linalg.norm(channels["r_BN_N"], axis=1)
    channels["altitude"] = radius[:, None] - EARTH_BODY["radius_km"] * 1e3

    omega_mag = np.linalg.norm(channels["omega_BN_B"], axis=1)
    above = np.nonzero(omega_mag >= SETTLE_RATE_RADS)[0]
    if len(above) == 0:
        settle_idx = 0
    elif above[-1] + 1 < len(t):
        settle_idx = above[-1] + 1
    else:
        settle_idx = None  # never stayed below the threshold
    settled = settle_idx is not None

    pointing_err_deg = 4.0 * np.degrees(np.arctan(np.linalg.norm(channels["sigma_BN"][-1])))
    metrics = {
        "settle_time_min": float(t[settle_idx] / 60.0) if settled else float(t[-1] / 60.0),
        "settled": settled,
        "max_rw_speed_rpm": float(np.abs(channels["rw_speeds"]).max() * 30.0 / np.pi),
        "pointing_error_final_deg": float(pointing_err_deg),
    }

    tumble_deg_s = np.degrees(np.linalg.norm([p["omega0_x"], p["omega0_y"], p["omega0_z"]]))
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — {tumble_deg_s:.1f}°/s tumble → inertial hold",
    )
