#!/usr/bin/env bash
# Rung 5a: hohmann transfer (multi-arc + impulsive burns via dynManager state
# rewrite) in wasm vs native. Proves resumed stepping under the no-threads patch.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"
mkdir -p "$ROOT/results"

WHEEL="$(ls "$ROOT"/wheels/bskcore-*.whl | head -1)"
NUMPY_WHEEL="$(ls "$ROOT"/downloads/wasm-wheels/numpy-*.whl | head -1)"

cd "$ROOT/harness"
"$NODE" run_in_pyodide.mjs tests/scenario_hohmann.py "$NUMPY_WHEEL" "$WHEEL" \
    > "$ROOT/results/hohmann_wasm.json"
/home/user/bsk-venv/bin/python tests/scenario_hohmann.py \
    > "$ROOT/results/hohmann_native.json"

python3 "$ROOT/harness/compare_results.py" \
    "$ROOT/results/hohmann_wasm.json" "$ROOT/results/hohmann_native.json" \
    --kind orbit --tol 1e-9 | tee "$ROOT/results/hohmann_compare.txt"
