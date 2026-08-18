#!/usr/bin/env bash
# Rung 5c: run the repo's ACTUAL sims/bsds_sims/scenarios/drag_deorbit.py in
# Pyodide (wasm) and natively, compare. Params: BC=12.5 kg/m^2, alt=250 km
# (deorbits in ~49 h of sim time). Gate: deorbit_time_h + trajectory <= 1e-6
# relative (trajectory target is 1e-12; see results/drag_compare.txt).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"
mkdir -p "$ROOT/results"

BSDS_REPO="${BSDS_REPO:-/home/user/BSDS}"
WHEEL="$(ls "$ROOT"/wheels/bskcore-*.whl | head -1)"
NUMPY_WHEEL="$(ls "$ROOT"/downloads/wasm-wheels/numpy-*.whl | head -1)"

echo "== zip the bsds_sims subset + scenario from $BSDS_REPO/sims =="
PYLIB_ZIP="$ROOT/results/bsds_sims_drag.zip"
python3 - "$BSDS_REPO/sims" "$PYLIB_ZIP" <<'EOF'
import sys, zipfile
from pathlib import Path
sims, out = Path(sys.argv[1]), sys.argv[2]
files = ["bsds_sims/__init__.py", "bsds_sims/recording.py",
         "bsds_sims/scenarios/drag_deorbit.py"]
with zipfile.ZipFile(out, "w") as z:
    for f in files:
        z.write(sims / f, f)
print(f"wrote {out} ({len(files)} files)")
EOF

echo "== wasm run (Pyodide in Node) =="
cd "$ROOT/harness"
"$NODE" run_in_pyodide.mjs tests/scenario_drag_deorbit.py "$NUMPY_WHEEL" "$WHEEL" \
    "$PYLIB_ZIP" > "$ROOT/results/drag_wasm.json"

echo "== native run (bsk-venv, Basilisk $(/home/user/bsk-venv/bin/python -c 'import Basilisk;print(Basilisk.__version__)')) =="
(cd "$BSDS_REPO/sims" && /home/user/bsk-venv/bin/python \
    "$ROOT/harness/tests/scenario_drag_deorbit.py") \
    > "$ROOT/results/drag_native.json"

echo "== compare =="
python3 "$ROOT/harness/compare_results.py" \
    "$ROOT/results/drag_wasm.json" "$ROOT/results/drag_native.json" \
    --kind drag --tol 1e-6 | tee "$ROOT/results/drag_compare.txt"
