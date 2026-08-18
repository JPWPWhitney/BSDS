"""Run the repo's ACTUAL drag_deorbit scenario template, unmodified.

Loads sims/bsds_sims/scenarios/drag_deorbit.py standalone via importlib (the
same way the WASM Lab's PY_DRIVER execs template code, bypassing the scenario
registry __init__ which imports modules not in the wheel). Needs `bsds_sims`
importable and the scenario file at bsds_sims/scenarios/drag_deorbit.py under
the current working directory:
  - native: run with cwd = <repo>/sims
  - wasm:   32_validate_drag.sh zips that subset of <repo>/sims; the harness
            unpacks it into pyodide's cwd (/home/pyodide)
Emits one line: `BSK_RESULT_JSON <json>`.
"""

import importlib.util
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())  # bsds_sims/ lives under cwd on both sides

PARAMS = {"ballistic_coeff": 12.5, "alt_km": 250.0}

scen_path = os.path.join(os.getcwd(), "bsds_sims", "scenarios", "drag_deorbit.py")
spec = importlib.util.spec_from_file_location("drag_deorbit_template", scen_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["drag_deorbit_template"] = mod
spec.loader.exec_module(mod)

res = mod.run(dict(PARAMS))

result = {
    "params": PARAMS,
    "t": np.asarray(res.time_s, dtype=np.float64).tolist(),
    "r": np.asarray(res.channels["r_BN_N"], dtype=np.float64).tolist(),
    "v": np.asarray(res.channels["v_BN_N"], dtype=np.float64).tolist(),
    "alt": np.asarray(res.channels["altitude"], dtype=np.float64).ravel().tolist(),
    "metrics": {
        "deorbit_time_h": float(res.metrics["deorbit_time_h"]),
        "capped": bool(res.metrics["capped"]),
        "final_alt_km": float(res.metrics["final_alt_km"]),
    },
}
print("BSK_RESULT_JSON " + json.dumps(result))
