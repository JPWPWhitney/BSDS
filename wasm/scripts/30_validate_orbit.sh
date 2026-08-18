#!/usr/bin/env bash
# Rung 4: run the basic_orbit scenario in Pyodide (wasm) and natively, compare
# trajectories sample-by-sample. Target: max relative error <= 1e-9.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"
mkdir -p "$ROOT/results"

WHEEL="$(ls "$ROOT"/wheels/bskcore-*.whl | head -1)"
NUMPY_WHEEL="$(ls "$ROOT"/downloads/wasm-wheels/numpy-*.whl | head -1)"

echo "== wasm run (Pyodide in Node) =="
cd "$ROOT/harness"
"$NODE" run_in_pyodide.mjs tests/scenario_basic_orbit.py "$NUMPY_WHEEL" "$WHEEL" \
    > "$ROOT/results/orbit_wasm.json"

echo "== native run (bsk-venv, Basilisk $(/home/user/bsk-venv/bin/python -c 'import Basilisk;print(Basilisk.__version__)')) =="
/home/user/bsk-venv/bin/python tests/scenario_basic_orbit.py \
    > "$ROOT/results/orbit_native.json"

echo "== compare =="
python3 "$ROOT/harness/compare_results.py" \
    "$ROOT/results/orbit_wasm.json" "$ROOT/results/orbit_native.json" \
    --kind orbit --tol 1e-9 | tee "$ROOT/results/orbit_compare.txt"
