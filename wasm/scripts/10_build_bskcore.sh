#!/usr/bin/env bash
# Rungs 2+3: generate SWIG wrappers + build the bskcore wasm wheel.
# Re-runnable; pass --clean to regenerate everything from the pristine clone.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"

cd "$ROOT/bskcore"
"$ROOT/toolchain/venv313/bin/python" generate.py "$@"

# setuptools caches compiled objects keyed by path; after regenerating sources
# a stale build/ can mask missing-source errors until import time. Clean it.
rm -rf build dist

pyodide build
mkdir -p "$ROOT/wheels"
cp dist/bskcore-*.whl "$ROOT/wheels/"
ls -la "$ROOT/wheels/"
