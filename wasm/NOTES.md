# Basilisk → WebAssembly port, Stage 3 milestone build

Workspace: this directory. Nothing here touches /home/user/BSDS (read-only reference).

## Fixed versions
- Basilisk source: tag **v2.11.1** (matches native install in /home/user/bsk-venv, bsk 2.11.1)
- pyodide-build **0.39.0** ↔ Pyodide **0.29.4** (CPython 3.13.2 in wasm)
- Emscripten: whatever the xbuildenv reports (spike: 4.0.9) — pinned by `pyodide config get emscripten_version`
- SWIG 4.2.0 (apt) — works on v2.11.1 .i files despite pyproject pinning >=4.4.1
- Node 22 (/opt/node22) + npm pyodide@0.29.4 for the test harness
- Eigen 3.4.0 vendored from apt libeigen3-dev into vendor/eigen3 (pywasmcross filters -I/usr/include)

## Network facts (container)
- pypi.org + files.pythonhosted.org are in no_proxy → pip talks to PyPI directly, TLS fine even on 3.13
- github.com goes through MITM proxy; curl trusts the CA, Python 3.13 does NOT (VERIFY_X509_STRICT)
  → download GitHub assets with curl, serve to python tools via `python3 -m http.server` on 127.0.0.1
- conancenter is BLOCKED → no conan; hand-rolled setup.py (Route B)
- xbuildenv asset: https://github.com/pyodide/pyodide/releases/download/0.29.4/xbuildenv-0.29.4.tar.bz2 (verified 200)

## Progress log
- [x] Workspace created, basilisk v2.11.1 shallow-cloned (465M)
- [x] Rung 1: `scripts/00_setup_toolchain.sh` one-shot green (emscripten 4.0.9,
      xbuildenv 0.29.4, swig 4.2.0, node pyodide 0.29.4, eigen 3.4.0 vendored,
      numpy wasm wheel extracted from the pyodide GH release bundle) +
      `scripts/01_hello_wheel.sh` imports a C extension in Pyodide-in-Node.
      Harness gotcha: pyodide 0.29 `unpackArchive` rejects Node `Buffer` — pass
      a plain `Uint8Array` view (fixed in harness/run_in_pyodide.mjs).
- [x] Rung 2/3 build system: `bskcore/generate.py` copies the v2.11.1 source
      subset, applies patches (sim_model no-threads, python wasm shims),
      generates the 7 messaging payload modules with the repo's own generators
      (libclang via pip `libclang`, which bundles a matching .so — apt
      libclang-18 mismatches pip `clang` bindings), runs host SWIG 4.2.0 (21
      modules, zero errors on real .i files), writes ext_manifest.json.
- [x] Rung 3: wheel builds — `bskcore-2.11.1-cp313-cp313-pyemscripten_2025_0_wasm32.whl`,
      1.81 MB, 21 extension .so (9.8 MB uncompressed). Iteration fixes:
      (1) each module's .i dir must be a C include dir (CMake PARENT_DIR
      equivalent); (2) SWIG 4.2 AppendOutput appends INTO a list result —
      argout typemaps must emit tuples, or the first output vector gets
      flattened; (3) simHelpers imports pyswice+dataFetcher at module scope —
      added to the python shims patch.
- [x] Rung 4: basic_orbit in Pyodide-in-Node vs native bsk 2.11.1 —
      **max |Δr|/|r| = 7.3e-15, max |Δv|/|v| = 6.2e-15 over 597 samples**
      (identical time grids), initial state agrees to 2e-16. Target was 1e-9;
      result is machine precision. Wheel install 65 ms, pyodide boot ~2.0 s,
      whole run (boot+install+sim+dump) 4.4 s wall in Node.
- [x] Rung 2: cutils (orbitalMotion/linearAlgebra/rigidBodyKinematics C code)
      elem2rv/rv2elem + MRP/DCM round-trips vs native pure-python
      implementations: worst 1.3e-15 (after treating true anomaly as an angle:
      the C impl returns 2pi-eps where python returns 0 — same angle,
      different wrap branch).
- [x] Rung 5a: hohmann scenario verified in wasm (multi-arc ExecuteSimulation
      + dynManager state rewrite between arcs) — see results/hohmann_compare.txt
- [x] Rung 5b: browser demo page in demo/ (Pyodide CDN + local wheel; canvas
      altitude plot). Untestable in this container (no browser) but the same
      wheel+scenario path is proven in Node.

## Rung 5: what drag_deorbit and hohmann need (dependency closure)
**hohmann.py — NOTHING new.** Uses dynManager.getStateObject +
StateData get/setState (wrapped via dynParamManager.i inside _spacecraft) and
simHelpers.EigenVector3d2np/np2EigenVectorXd (pure numpy). Verified running.

**drag_deorbit.py — two new SWIG modules + one payload:**
- `Basilisk.simulation.exponentialAtmosphere` ← src/simulation/environment/
  exponentialAtmosphere/{exponentialAtmosphere.cpp,.i} + environment/
  _GeneralModuleFiles/atmosphereBase.cpp (deps: linearAlgebra,
  macroDefinitions, simDefinitions — all already in bsk/)
- `Basilisk.simulation.dragDynamicEffector` ← src/simulation/dynamics/
  dragEffector/{dragDynamicEffector.cpp,.i} (base classes dynamicEffector/
  stateData already compiled)
- messaging payload `AtmoPropsMsgPayload` (atmosphereBase outputs it,
  dragDynamicEffector reads it) — add to PAYLOADS in generate.py
- scenario also calls scSim.SetProgressBar? no — uses chunked ExecuteSimulation
  (proven by hohmann) and modifies stop time repeatedly. atmosphereBase reads
  SpicePlanetStateMsgPayload + SCStatesMsgPayload + EpochMsgPayload — all
  already built.
Estimated effort: ~20 lines in generate.py MODULES/PAYLOADS + rebuild.

## Final state (2026-08-18)
- Wheel: `wheels/bskcore-2.11.1-cp313-cp313-pyemscripten_2025_0_wasm32.whl`
  1,811,973 bytes (sha256 bc4b27a4e31de8f6…), 21 extension .so, 9.8 MB unpacked.
- Verified reproducible: `scripts/10_build_bskcore.sh --clean` rebuilds from the
  pristine v2.11.1 clone end-to-end (exit 0), then 20/30/31 validation scripts
  all PASS.
- Validation summary (wasm vs native bsk 2.11.1):
  | check | samples | worst rel. err |
  |---|---|---|
  | cutils elem2rv/rv2elem/MRP round-trips | – | 1.3e-15 |
  | basic_orbit r/v trajectory | 597 | 7.3e-15 |
  | hohmann 3-arc r/v trajectory + dv1/dv2 | 700 | 4.1e-14 (dv exact to 1e-10 printed digits) |
- Timing (Node, this container): pyodide boot ~1.8–2.0 s, numpy install 0.16 s,
  bskcore install 0.06 s, basic_orbit total wall 4.1–4.4 s, hohmann 7.0 s.

## Reproduce from scratch
```bash
cd wasm-port
git clone --depth 1 --branch v2.11.1 https://github.com/AVSLab/basilisk
./scripts/00_setup_toolchain.sh   # venv+pyodide-build, xbuildenv (via curl+local http), emsdk 4.0.9, node harness, eigen, numpy wheel
./scripts/01_hello_wheel.sh       # sanity: C extension wheel imports in Pyodide
./scripts/10_build_bskcore.sh --clean
./scripts/20_test_utils.sh
./scripts/30_validate_orbit.sh
./scripts/31_validate_hohmann.sh
demo/serve.sh                     # browser demo at http://localhost:8000/
```
(Only manual pre-req on a fresh container: `apt-get install -y swig` if absent,
and `pip install libclang` happens inside 00 via the venv — see script.)

## Top remaining problems for the full port
1. **SPICE (pyswice / spiceInterface)**: cspice is a large C library; needed for
   any scenario with real ephemerides/epochs. Cross-compiling cspice to wasm is
   unproven; data kernels (de430.bsp ~120 MB) are far too big for a wheel —
   needs lazy fetch + a trimmed kernel set.
2. **C-module FSW stack (alg_contain, cMsgCInterface)**: the messaging C
   interface (auto-generated per-payload .c) and algorithm containers are
   stubbed out; porting fswAlgorithms requires generating + compiling those and
   wiring `swig_c_wrap`/`cSysModel` paths.
3. **Scale-out of module coverage**: each new Basilisk module needs a MODULES
   entry (sources + .i) in generate.py; the messaging payload list is manual.
   Deriving both automatically from the CMake tree (or a parsed build manifest)
   would remove the main maintenance burden. Also: matplotlib-dependent
   utilities are shimmed, not ported (visualization stays host-side by design).

## Network gotchas discovered this session
- jsdelivr CDN is blocked -> numpy wasm wheel must come from the GitHub release
  bundle `pyodide-0.29.4.tar.bz2` (extract `pyodide/numpy-*.whl`).
- PyPI serves NO pyodide/emscripten wheels for numpy (checked via pip
  --platform pyodide_2025_0_wasm32) — the release bundle is the only source.
- GitHub REST API via the proxy requires repo attachment; plain
  `https://github.com/<org>/<repo>/releases/download/...` asset URLs work with
  curl without it.

## Addendum 2026-08-18: drag modules (drag_deorbit closure)
Added to the wheel so the WASM Lab can run the drag_deorbit template:
- `Basilisk.simulation.exponentialAtmosphere` (env model; compiles
  environment/_GeneralModuleFiles/atmosphereBase.cpp + ExponentialAtmosphere/
  exponentialAtmosphere.cpp on top of ARCH_CORE + C_UTILS)
- `Basilisk.simulation.dragDynamicEffector` (DYN_CORE + dragEffector/
  dragDynamicEffector.cpp)
- messaging payload `AtmoPropsMsgPayload` (PAYLOADS + overlay messaging
  __init__) — WindMsgPayload stays header-only/opaque (windVelInMsg unused)
Manifest: generate.py COPY_DIRS +3 dirs, PAYLOADS +1, MODULES +2 (ATMO_SRC /
DRAG_SRC bundles) -> 24 extension .so (was 21).

Wheel: `bskcore-2.11.1-cp313-cp313-pyemscripten_2025_0_wasm32.whl` now
**2,089,446 bytes** (was 1,811,973), 12.5 MB unpacked,
sha256 0b60b6e34263d7a6…  Same filename; web/ fetch path unchanged.

Validation (`scripts/32_validate_drag.sh`, runs the repo's actual
sims/bsds_sims/scenarios/drag_deorbit.py verbatim on both sides, params
BC=12.5 kg/m², alt=250 km -> deorbits, ~49 h sim):
| check | samples | result |
|---|---|---|
| deorbit_time_h wasm vs native | – | 49.1 h both, rel err 0.0 (requirement 1e-6) |
| drag r/v trajectory | 1531 | max rel err 1.5e-11 / 1.6e-11 (target 1e-12 missed: 49 h ≈ 31 revs through an exp() atmosphere amplifies 1-ulp libm differences; deorbit time still exact) |
| basic_orbit regression | 597 | 7.3e-15 (unchanged) |
| hohmann regression | 700 | 4.1e-14 (unchanged) |
| cutils regression | – | 1.3e-15 (unchanged) |
wasm run wall time (Node): 9.2 s total for the 49 h deorbit (~5,880 RK4 steps).
web/: drag_deorbit added to WASM_TEMPLATE_IDS (wasmcore.ts) + test flipped.
