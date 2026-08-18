"""Hohmann transfer scenario (mirrors sims/bsds_sims/scenarios/hohmann.py):
three arcs with impulsive prograde burns applied by rewriting the hub velocity
state between ExecuteSimulation calls. Exercises multi-resume stepping and
dynManager state access. Runs identically in native Basilisk and bskcore/wasm.
"""

import json

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import (SimulationBaseClass, macros, orbitalMotion,
                                simHelpers, simIncludeGravBody)

EARTH_RADIUS_KM = 6378.1366
r1 = EARTH_RADIUS_KM * 1e3 + 400.0e3    # parking orbit radius
r2 = EARTH_RADIUS_KM * 1e3 + 35786.0e3  # GEO-ish target radius

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

rec = scObject.scStateOutMsg.recorder(macros.sec2nano(60.0))
scSim.AddModelToTask("dynamicsTask", rec)
scSim.InitializeSimulation()

vel_ref = scObject.dynManager.getStateObject(scObject.hub.nameOfHubVelocity)

at = (r1 + r2) / 2.0
v_t1 = np.sqrt(mu * (2.0 / r1 - 1.0 / at))
v_final = np.sqrt(mu / r2)
t_transfer = np.pi * np.sqrt(at**3 / mu)
period1 = 2 * np.pi * np.sqrt(r1**3 / mu)
period2 = 2 * np.pi * np.sqrt(r2**3 / mu)


def prograde_burn(target_speed):
    v_now = np.array(simHelpers.EigenVector3d2np(vel_ref.getState()), dtype=np.float64)
    speed = np.linalg.norm(v_now)
    vel_ref.setState(simHelpers.np2EigenVectorXd(v_now / speed * target_speed))
    return float(target_speed - speed)


t1 = 0.25 * period1
scSim.ConfigureStopTime(macros.sec2nano(t1))
scSim.ExecuteSimulation()
dv1 = prograde_burn(v_t1)

t2 = t1 + t_transfer
scSim.ConfigureStopTime(macros.sec2nano(t2))
scSim.ExecuteSimulation()
dv2 = prograde_burn(v_final)

t3 = t2 + 0.25 * period2
scSim.ConfigureStopTime(macros.sec2nano(t3))
scSim.ExecuteSimulation()

t = np.asarray(rec.times(), dtype=np.float64) * macros.NANO2SEC
r = np.asarray(rec.r_BN_N, dtype=np.float64)
v = np.asarray(rec.v_BN_N, dtype=np.float64)
keep = np.ones(len(t), dtype=bool)
keep[:-1] = np.diff(t) > 0
t, r, v = t[keep], r[keep], v[keep]

result = {
    "mu": mu,
    "a": r1,
    "period_s": period1,
    "rN0": list(rN) if not hasattr(rN, "tolist") else rN.tolist(),
    "vN0": list(vN) if not hasattr(vN, "tolist") else vN.tolist(),
    "dv1": dv1,
    "dv2": dv2,
    "final_radius": float(np.linalg.norm(r[-1])),
    "t": t.tolist(),
    "r": r.tolist(),
    "v": v.tolist(),
}
print("BSK_RESULT_JSON " + json.dumps(result))
