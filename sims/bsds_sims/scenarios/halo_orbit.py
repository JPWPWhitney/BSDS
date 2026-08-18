"""A spacecraft looping the Earth-Moon L2 point in a circular-restricted 3-body model.

Self-contained BSDS scenario. Earth is the central gravity body; the Moon is a
second gravity body on a PRESCRIBED circular orbit (a = 384,400 km, mean motion
n = sqrt((mu_E + mu_M)/a^3), period 27.28 d), so the dynamics are exactly the
classical CR3BP written in Earth-centered inertial coordinates — no SPICE.
Basilisk's gravityEffector includes the third-body indirect term when a central
body is set (verified against finite-differenced accelerations), which is what
makes the Earth-pinned formulation equivalent to the barycentric CR3BP.

Why not Basilisk's planetEphemeris module: its Keplerian propagation hard-codes
the SUN's gravitational parameter (a prescribed a = 384,400 km orbit comes out
with a 68.5-minute period, v = 588 km/s — measured empirically). The
_PrescribedCircularMoon SysModel below writes the same SpicePlanetStateMsg that
planetEphemeris would (PositionVector/VelocityVector/J2000Current), just with
the correct Earth-Moon mean motion, and the Moon gravity body consumes it
through the standard planetBodyInMsg wiring.

Initial conditions: a small-amplitude planar L2 LYAPUNOV orbit (the planar
sibling of a halo; a true halo needs in-plane amplitudes whose y-excursion
exceeds this scenario's ~60,000 km budget, and an uncorrected out-of-plane
Lissajous component diverges in ~10 days — both measured, hence the honest
Lyapunov). The IC was differentially corrected offline in the exact same CR3BP
(numpy RK4, h = 2e-4 TU): fixing x0 = xL2 - Ax with Ax = 15,000 km, shooting
the rotating-frame vy0 for a perpendicular x-axis recrossing (residual
|vx| < 1e-12). Linear theory seeds the corrector: libration frequency
nu = 1.86265, amplitude ratio kappa = 2.9126, period 14.87 d.
"""

from __future__ import annotations

import numpy as np

from Basilisk.architecture import messaging, sysModel
from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, simIncludeGravBody

from bsds_sims.recording import EARTH_BODY, RunResult, attach_sc_recorder, dedupe_time, pull_sc_channels

ID = "halo_orbit"
TITLE = "Earth–Moon L2 Halo"
KIND = "single"
DESCRIPTION = (
    "A spacecraft rings the Earth–Moon L2 point for weeks — a planar Lyapunov "
    "orbit (the halo family's flat sibling) in a circular-restricted three-body "
    "model with a prescribed circular Moon."
)

DEFAULTS = {"sim_days": 28.0}
EPOCH = "2026-01-01T00:00:00Z"

MOON_BODY = {"name": "moon", "mu": 4.9028e12, "radius_km": 1737.4}

A_MOON_M = 384400e3                                   # prescribed circular lunar orbit radius [m]
MU_EM = EARTH_BODY["mu"] + MOON_BODY["mu"]            # Earth+Moon gravitational parameter
N_MOON = np.sqrt(MU_EM / A_MOON_M**3)                 # lunar mean motion [rad/s] (period 27.285 d)
MUSTAR = MOON_BODY["mu"] / MU_EM                      # CR3BP mass ratio, 0.0121506

# Differentially corrected planar Lyapunov IC (normalized rotating barycentric
# units; see module docstring). x0 is rebuilt from gamma_L2 and AX below.
AX_KM = 15000.0                # x-amplitude toward Earth from L2
VY0_ROT = 0.19370518301457434  # rotating-frame y-velocity at t=0 [units of a*n]
LYAP_PERIOD_DAYS = 14.8715     # corrected orbit period (linear theory: 14.65 d)

DYN_STEP_S = 300.0   # RK4 fixed step; 600 s diverges from the Lyapunov by day ~26 (verified)
REC_S = 900.0        # recorder cadence -> 2689 samples over 28 days


def _l2_gamma(mu: float) -> float:
    """Distance of L2 beyond the smaller primary (normalized), via Newton on the
    collinear-equilibrium quintic g^5 + (3-mu)g^4 + (3-2mu)g^3 - mu g^2 - 2mu g - mu = 0."""
    g = (mu / 3) ** (1 / 3)
    for _ in range(60):
        f = g**5 + (3 - mu) * g**4 + (3 - 2 * mu) * g**3 - mu * g**2 - 2 * mu * g - mu
        fp = 5 * g**4 + 4 * (3 - mu) * g**3 + 3 * (3 - 2 * mu) * g**2 - 2 * mu * g - 2 * mu
        step = f / fp
        g -= step
        if abs(step) < 1e-16:
            break
    return g


L2_GAMMA = _l2_gamma(MUSTAR)  # 0.16783 -> L2 is 64,515 km beyond the Moon


class _PrescribedCircularMoon(sysModel.SysModel):
    """Writes a SpicePlanetStateMsg for a Moon on a prescribed circular orbit in
    the inertial x-y plane (what planetEphemeris would emit, with the right rate)."""

    def __init__(self, a_m: float, n_rad_s: float):
        super().__init__()
        self.a = a_m
        self.n = n_rad_s
        self.planetOutMsg = messaging.SpicePlanetStateMsg()

    def Reset(self, CurrentSimNanos):
        self.writeMsg(CurrentSimNanos)

    def UpdateState(self, CurrentSimNanos):
        self.writeMsg(CurrentSimNanos)

    def writeMsg(self, tNanos):
        t = tNanos * macros.NANO2SEC
        c, s = np.cos(self.n * t), np.sin(self.n * t)
        pl = messaging.SpicePlanetStateMsgPayload()
        pl.PlanetName = "moon"
        pl.J2000Current = t  # lets gravityEffector extrapolate between task ticks
        pl.PositionVector = [self.a * c, self.a * s, 0.0]
        pl.VelocityVector = [-self.a * self.n * s, self.a * self.n * c, 0.0]
        self.planetOutMsg.write(pl, tNanos, self.moduleID)


def run(params: dict) -> RunResult:
    p = {**DEFAULTS, **params}

    scSim = SimulationBaseClass.SimBaseClass()
    dyn_process = scSim.CreateNewProcess("dynamicsProcess")
    dyn_process.addTask(scSim.CreateNewTask("dynamicsTask", macros.sec2nano(DYN_STEP_S)))

    moonEphem = _PrescribedCircularMoon(A_MOON_M, N_MOON)
    moonEphem.ModelTag = "moonEphemeris"
    scSim.AddModelToTask("dynamicsTask", moonEphem, 100)  # runs before the spacecraft

    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "bsds-sat"
    scSim.AddModelToTask("dynamicsTask", scObject, 50)

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    earth.mu = EARTH_BODY["mu"]
    moon = gravFactory.createMoon()
    moon.mu = MOON_BODY["mu"]
    moon.planetBodyInMsg.subscribeTo(moonEphem.planetOutMsg)
    gravFactory.addBodiesTo(scObject)

    # Rotating -> inertial at t=0 (Moon at +x, rotating axes aligned with inertial):
    # Earth-centered x0 = (xL2_bary - Ax) + mustar; inertial v adds the omega x r term.
    x0_e = (1.0 - MUSTAR + L2_GAMMA) - AX_KM * 1e3 / A_MOON_M + MUSTAR
    scObject.hub.r_CN_NInit = [x0_e * A_MOON_M, 0.0, 0.0]
    scObject.hub.v_CN_NInit = [0.0, (VY0_ROT + x0_e) * A_MOON_M * N_MOON, 0.0]

    scRec = attach_sc_recorder(scSim, "dynamicsTask", scObject, min_update_s=REC_S)
    moonRec = moonEphem.planetOutMsg.recorder(macros.sec2nano(REC_S))
    scSim.AddModelToTask("dynamicsTask", moonRec)

    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(macros.sec2nano(p["sim_days"] * 86400.0))
    scSim.ExecuteSimulation()

    t, channels = pull_sc_channels(scRec)
    t_moon = np.asarray(moonRec.times(), dtype=np.float64) * macros.NANO2SEC
    if not np.array_equal(t, t_moon):
        raise RuntimeError("spacecraft and moon recorders fell out of step")
    channels["r_moon_N"] = np.asarray(moonRec.PositionVector, dtype=np.float64)
    t, channels = dedupe_time(t, channels)

    r = channels["r_BN_N"]
    r_moon = channels["r_moon_N"]
    # Instantaneous L2 sits on the Earth-Moon line, (1+gamma)*a from Earth.
    channels["r_rel_l2"] = r - (1.0 + L2_GAMMA) * r_moon
    radius = np.linalg.norm(r, axis=1)
    channels["altitude"] = radius[:, None] - EARTH_BODY["radius_km"] * 1e3

    # Winding of the L2-relative position in the rotating frame -> revolutions.
    xhat = r_moon / np.linalg.norm(r_moon, axis=1)[:, None]
    yhat = np.cross(np.broadcast_to([0.0, 0.0, 1.0], xhat.shape), xhat)
    xi = np.einsum("ij,ij->i", channels["r_rel_l2"], xhat)
    eta = np.einsum("ij,ij->i", channels["r_rel_l2"], yhat)
    theta = np.unwrap(np.arctan2(eta, xi))
    excursion_km = np.linalg.norm(channels["r_rel_l2"], axis=1) / 1e3

    metrics = {
        "l2_max_excursion_km": float(excursion_km.max()),
        "revolutions_completed": float(abs(theta[-1] - theta[0]) / (2 * np.pi)),
        "sim_days": float(t[-1] / 86400.0),
        "orbit_period_days": LYAP_PERIOD_DAYS,
        "moon_period_days": float(2 * np.pi / N_MOON / 86400.0),
    }
    return RunResult(
        time_s=t,
        channels=channels,
        bodies=[EARTH_BODY, MOON_BODY],
        metrics=metrics,
        epoch=EPOCH,
        title=f"{TITLE} — planar Lyapunov, {p['sim_days']:.0f} days",
    )
