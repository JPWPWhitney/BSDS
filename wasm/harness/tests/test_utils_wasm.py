"""Rung-A numeric check: C utils (orbitalMotion/linearAlgebra/rigidBodyKinematics)
compiled to wasm, exercised via elem2rv/rv2elem round-trip + MRP/DCM round-trip.
Emits `BSK_RESULT_JSON <json>` for comparison against the native run.
"""

import json
import math

from Basilisk.architecture import cutils

mu = 3.986004415e14
el = cutils.ClassicElements()
el.a = 6878136.6
el.e = 0.01
el.i = 51.6 * math.pi / 180.0
el.Omega = 48.2 * math.pi / 180.0
el.omega = 347.8 * math.pi / 180.0
el.f = 0.0

r, v = cutils.elem2rv_sized(mu, el)

el2 = cutils.ClassicElements()
cutils.rv2elem_sized(mu, r, v, el2)

sigma = [0.1, 0.2, -0.3]
c9 = cutils.MRP2C_sized(sigma)
sigma_rt = cutils.C2MRP_sized(c9)

cross = cutils.v3Cross_sized(r, v)
h = cutils.v3Norm_sized(cross)

result = {
    "r": list(r),
    "v": list(v),
    "roundtrip": {k: getattr(el2, k) for k in
                  ("a", "e", "i", "Omega", "omega", "f", "rmag")},
    "dcm9": list(c9),
    "sigma_rt": list(sigma_rt),
    "hmag": h,
}
print("BSK_RESULT_JSON " + json.dumps(result))
