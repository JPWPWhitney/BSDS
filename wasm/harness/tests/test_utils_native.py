"""Native counterpart of test_utils_wasm.py, run with /home/user/bsk-venv python.
Uses Basilisk's pure-python utilities implementations of the same algorithms.
"""

import json
import math

import numpy as np

from Basilisk.utilities import RigidBodyKinematics as rbk
from Basilisk.utilities import orbitalMotion

mu = 3.986004415e14
el = orbitalMotion.ClassicElements()
el.a = 6878136.6
el.e = 0.01
el.i = 51.6 * math.pi / 180.0
el.Omega = 48.2 * math.pi / 180.0
el.omega = 347.8 * math.pi / 180.0
el.f = 0.0

r, v = orbitalMotion.elem2rv(mu, el)
el2 = orbitalMotion.rv2elem(mu, r, v)

sigma = np.array([0.1, 0.2, -0.3])
C = rbk.MRP2C(sigma)
sigma_rt = rbk.C2MRP(C)

cross = np.cross(r, v)
h = float(np.linalg.norm(cross))

result = {
    "r": np.asarray(r).tolist(),
    "v": np.asarray(v).tolist(),
    "roundtrip": {k: float(getattr(el2, k)) for k in
                  ("a", "e", "i", "Omega", "omega", "f", "rmag")},
    "dcm9": np.asarray(C).flatten().tolist(),
    "sigma_rt": np.asarray(sigma_rt).flatten().tolist(),
    "hmag": h,
}
print("BSK_RESULT_JSON " + json.dumps(result))
