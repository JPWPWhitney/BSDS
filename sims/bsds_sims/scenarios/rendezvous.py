"""Orbital rendezvous: a chaser catches a passive target in LEO.

Two spacecraft propagate in the same simulation task. The target coasts on a
circular 500 km orbit; the chaser starts behind and below it on a slightly
lower coplanar circular orbit, coasts until the phase angle is right, then
flies a two-impulse Hohmann-style phasing transfer (velocity-state
modification between arcs, the scenarioOrbitManeuver pattern) and finishes
with a small matching burn that pins its orbit to the target's, ending in a
close standoff co-orbit.

Each Spacecraft owns its own DynParamManager, so the hub state names
("hubPosition"/"hubVelocity") do not collide between the two craft —
``scObject.dynManager.getStateObject(...)`` is already per-spacecraft.

All burn magnitudes and times are designed analytically: the first burn fires
when the target leads the chaser by phi = pi - n_t * t_transfer + standoff/r_t,
so the half-ellipse arrives ``standoff_m`` behind the target.
"""

from __future__ import annotations

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody
from Basilisk.utilities import simHelpers

from bsds_sims.recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "rendezvous"
TITLE = "Orbital Rendezvous"
KIND = "single"
DESCRIPTION = "A chaser closes a 10 km gap on a target in LEO and matches its orbit."

DEFAULTS = {
    "alt_target_km": 500.0,  # target's circular orbit altitude
    "below_km": 3.0,         # chaser starts this far below the target's radius
    "behind_km": 10.0,       # ... and this far behind along-track
    "standoff_m": 300.0,     # aimed final trailing distance
}
EPOCH = "2026-01-01T00:00:00Z"

TASK_DT_S = 5.0
RECORD_DT_S = 10.0


def _make_craft(tag: str, mu: float, a: float, f: float):
    """Spacecraft on an exactly circular orbit (i=28.5 deg plane) at phase f."""
    sc = spacecraft.Spacecraft()
    sc.ModelTag = tag
    oe = orbitalMotion.ClassicElements()
    oe.a = a
    oe.e = 0.0
    oe.i = 28.5 * macros.D2R
    oe.Omega = 48.2 * macros.D2R
    oe.omega = 0.0
    oe.f = f
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    sc.hub.r_CN_NInit = rN
    sc.hub.v_CN_NInit = vN
    return sc


def _refs(sc):
    """Per-craft position/velocity state objects (dynManager is per-spacecraft)."""
    pos = sc.dynManager.getStateObject(sc.hub.nameOfHubPosition)
    vel = sc.dynManager.getStateObject(sc.hub.nameOfHubVelocity)
    return pos, vel


def _read(ref) -> np.ndarray:
    return np.array(simHelpers.EigenVector3d2np(ref.getState()), dtype=np.float64)


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}
    r_t = (EARTH_BODY["radius_km"] + p["alt_target_km"]) * 1e3
    r_c = r_t - p["below_km"] * 1e3
    if r_c <= 0 or r_c >= r_t:
        raise ValueError("below_km must be positive and smaller than the target radius")

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(TASK_DT_S)))

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    mu = earth.mu

    # Analytic phasing design (pure two-body, matches the point-mass sim).
    n_t = np.sqrt(mu / r_t**3)
    n_c = np.sqrt(mu / r_c**3)
    a_h_nom = 0.5 * (r_c + r_t)
    t_h_nom = np.pi * np.sqrt(a_h_nom**3 / mu)
    period_t = 2.0 * np.pi / n_t
    phi0 = p["behind_km"] * 1e3 / r_t                       # target's initial lead angle
    phi_req = np.pi - n_t * t_h_nom + p["standoff_m"] / r_t  # lead angle at burn 1
    if phi0 <= phi_req:
        raise ValueError(
            "behind_km too small for this below_km: chaser must start further back "
            f"than the transfer sweep requires (need > {phi_req * r_t / 1e3:.2f} km)"
        )
    t1 = (phi0 - phi_req) / (n_c - n_t)  # coast until the phase condition is met

    target = _make_craft("bsds-target", mu, r_t, 0.0)
    chaser = _make_craft("bsds-chaser", mu, r_c, -phi0)
    scSim.AddModelToTask("dynamicsTask", target)
    scSim.AddModelToTask("dynamicsTask", chaser)
    gravFactory.addBodiesTo(target)
    gravFactory.addBodiesTo(chaser)

    rec_chaser = attach_sc_recorder(scSim, "dynamicsTask", chaser, min_update_s=RECORD_DT_S)
    rec_target = attach_sc_recorder(scSim, "dynamicsTask", target, min_update_s=RECORD_DT_S)
    scSim.InitializeSimulation()

    t_pos, t_vel = _refs(target)
    c_pos, c_vel = _refs(chaser)

    def _snap(t: float) -> float:
        """Burn times land on task ticks so state edits happen at known times."""
        return max(TASK_DT_S, round(t / TASK_DT_S) * TASK_DT_S)

    def _run_to(t: float) -> None:
        scSim.ConfigureStopTime(macros.sec2nano(t))
        scSim.ExecuteSimulation()

    # Arc 1: coast to the phasing point, then burn onto the transfer ellipse.
    t1 = _snap(t1)
    _run_to(t1)
    r_now = _read(c_pos)
    v_now = _read(c_vel)
    r_aim = float(np.linalg.norm(_read(t_pos)))  # aim at the target's actual radius
    a_h = 0.5 * (float(np.linalg.norm(r_now)) + r_aim)
    v_peri = np.sqrt(mu * (2.0 / np.linalg.norm(r_now) - 1.0 / a_h))
    v_new = v_now / np.linalg.norm(v_now) * v_peri
    dv1 = float(np.linalg.norm(v_new - v_now))
    c_vel.setState(simHelpers.np2EigenVectorXd(v_new))
    t_transfer = float(np.pi * np.sqrt(a_h**3 / mu))

    # Arc 2: half the transfer ellipse; circularize on arrival near the target.
    t2 = _snap(t1 + t_transfer)
    _run_to(t2)
    r_now = _read(c_pos)
    v_now = _read(c_vel)
    v_circ = np.sqrt(mu / np.linalg.norm(r_now))
    v_new = v_now / np.linalg.norm(v_now) * v_circ
    dv2 = float(np.linalg.norm(v_new - v_now))
    c_vel.setState(simHelpers.np2EigenVectorXd(v_new))

    # Arc 3: quarter orbit later, trim burn matching the target's semi-major
    # axis exactly (tangential, in-plane) so the relative drift freezes.
    t3 = _snap(t2 + 0.25 * period_t)
    _run_to(t3)
    r_tv = _read(t_pos)
    v_tv = _read(t_vel)
    a_target = 1.0 / (2.0 / np.linalg.norm(r_tv) - float(np.dot(v_tv, v_tv)) / mu)
    r_now = _read(c_pos)
    v_now = _read(c_vel)
    h_hat = np.cross(r_now, v_now)
    h_hat /= np.linalg.norm(h_hat)
    t_hat = np.cross(h_hat, r_now / np.linalg.norm(r_now))
    speed = np.sqrt(mu * (2.0 / np.linalg.norm(r_now) - 1.0 / a_target))
    v_new = speed * t_hat
    dv3 = float(np.linalg.norm(v_new - v_now))
    c_vel.setState(simHelpers.np2EigenVectorXd(v_new))

    # Arc 4: station-keep in the standoff co-orbit for 1.5 target orbits.
    t_end = _snap(t3 + 1.5 * period_t)
    _run_to(t_end)

    t_c, ch = pull_sc_channels(rec_chaser)
    t_t, ch_target = pull_sc_channels(rec_target)
    if not np.array_equal(t_c, t_t):
        raise RuntimeError("chaser/target recorder time bases diverged")
    ch["r2_BN_N"] = ch_target["r_BN_N"]
    ch["v2_BN_N"] = ch_target["v_BN_N"]
    t, ch = dedupe_time(t_c, ch)

    radius = np.linalg.norm(ch["r_BN_N"], axis=1)
    ch["altitude"] = radius[:, None] - EARTH_BODY["radius_km"] * 1e3
    sep = np.linalg.norm(ch["r_BN_N"] - ch["r2_BN_N"], axis=1)
    ch["separation"] = sep[:, None]

    metrics = {
        "initial_separation_km": float(sep[0] / 1e3),
        "final_separation_m": float(sep[-1]),
        "dv_total_ms": dv1 + dv2 + dv3,
        "transfer_time_h": t_transfer / 3600.0,
        "dv1_ms": dv1,
        "dv2_ms": dv2,
        "dv3_ms": dv3,
        "burn1_t_s": t1,
        "burn2_t_s": t2,
        "burn3_t_s": t3,
    }
    return RunResult(
        time_s=t,
        channels=ch,
        bodies=[EARTH_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — {p['behind_km']:.0f} km chase to {p['standoff_m']:.0f} m",
    )
