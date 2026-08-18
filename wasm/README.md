# BSDS Stage 3: Basilisk compiled to WebAssembly (bskcore)

A subset of Basilisk 2.11.1 (architecture + messaging + spacecraft dynamics,
21 SWIG extension modules) cross-compiled to `wasm32-emscripten` and packaged
as a Pyodide-loadable wheel. Trajectories match native Basilisk to ~1e-15
relative error (basic orbit and Hohmann validated end to end).

- `wheels/bskcore-…wasm32.whl` — the built wheel (1.8 MB); `numpy-…wasm32.whl`
  is the matching Pyodide numpy, self-hosted so the site needs no CDN.
- `bskcore/` — `generate.py` copies the pinned Basilisk v2.11.1 source subset,
  applies `patches/`, runs the payload generators + SWIG, and `setup.py`
  builds the wheel with `pyodide build`.
- `patches/sim_model_nothreads.patch` — the one mandatory source change:
  drives the sim executive inline under Emscripten (no pthreads).
- `scripts/` — idempotent toolchain + build + validation pipeline; see
  `NOTES.md` for the build log and container-specific workarounds.
- `harness/` — Node+Pyodide runner and the dual-environment validation tests.
- `demo/` — standalone single-file demo page (the site's WASM Lab supersedes it).

Rebuild from scratch (Linux):

    cd wasm
    git clone --depth 1 --branch v2.11.1 https://github.com/AVSLab/basilisk
    ./scripts/00_setup_toolchain.sh
    ./scripts/10_build_bskcore.sh --clean
    ./scripts/30_validate_orbit.sh && ./scripts/31_validate_hohmann.sh

Not yet ported: SPICE ephemerides, the C FSW algorithm stack, and the
environment/effector long tail (exponentialAtmosphere + dragDynamicEffector
are the next ~20 manifest lines).
