#!/usr/bin/env bash
# Rung 2 check: run the C-utils numeric test in wasm and natively, compare.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"
mkdir -p "$ROOT/results"

WHEEL="$(ls "$ROOT"/wheels/bskcore-*.whl | head -1)"
NUMPY_WHEEL="$(ls "$ROOT"/downloads/wasm-wheels/numpy-*.whl | head -1)"

cd "$ROOT/harness"
"$NODE" run_in_pyodide.mjs tests/test_utils_wasm.py "$NUMPY_WHEEL" "$WHEEL" \
    > "$ROOT/results/utils_wasm.json"
/home/user/bsk-venv/bin/python tests/test_utils_native.py \
    > "$ROOT/results/utils_native.json"

python3 "$ROOT/harness/compare_results.py" \
    "$ROOT/results/utils_wasm.json" "$ROOT/results/utils_native.json" \
    --kind utils --tol 1e-9 | tee "$ROOT/results/utils_compare.txt"
