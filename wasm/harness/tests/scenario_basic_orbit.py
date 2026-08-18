"""basic_orbit scenario, equivalent to sims/bsds_sims/scenarios/basic_orbit.py.

Runs in BOTH native Basilisk (bsk-venv) and bskcore-in-Pyodide unchanged.
Emits one line: `BSK_RESULT_JSON <json>` with the recorded trajectory.
"""

import json

import numpy as np

from Basilisk.simulation import spacecraft
from Basilisk.utilities import SimulationBaseClass, macros, orbitalMotion, simIncludeGravBody

EARTH_RADIUS_KM = 6378.1366  # matches bsds_sims.recording.EARTH_BODY
ALT_KM = 500.0
ECC = 0.01
INC_DEG = 51.6

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
oe.a = EARTH_RADIUS_KM * 1e3 + ALT_KM * 1e3
oe.e = ECC
oe.i = INC_DEG * macros.D2R
oe.Omega = 48.2 * macros.D2R
oe.omega = 347.8 * macros.D2R
oe.f = 0.0
rN, vN = orbitalMotion.elem2rv(mu, oe)
scObject.hub.r_CN_NInit = rN
scObject.hub.v_CN_NInit = vN

period_s = 2 * np.pi * np.sqrt(oe.a**3 / mu)

rec = scObject.scStateOutMsg.recorder(macros.sec2nano(5.0))
scSim.AddModelToTask("dynamicsTask", rec)

scSim.InitializeSimulation()
scSim.ConfigureStopTime(macros.sec2nano(1.05 * period_s))
scSim.ExecuteSimulation()

t = np.asarray(rec.times(), dtype=np.float64) * macros.NANO2SEC
r = np.asarray(rec.r_BN_N, dtype=np.float64)
v = np.asarray(rec.v_BN_N, dtype=np.float64)

# dedupe repeated timestamps, keep last occurrence (as bsds_sims.recording does)
keep = np.ones(len(t), dtype=bool)
keep[:-1] = np.diff(t) > 0
t, r, v = t[keep], r[keep], v[keep]

result = {
    "mu": mu,
    "a": oe.a,
    "period_s": period_s,
    "rN0": list(rN) if not hasattr(rN, "tolist") else rN.tolist(),
    "vN0": list(vN) if not hasattr(vN, "tolist") else vN.tolist(),
    "t": t.tolist(),
    "r": r.tolist(),
    "v": v.tolist(),
}
print("BSK_RESULT_JSON " + json.dumps(result))
