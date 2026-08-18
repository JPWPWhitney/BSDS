# BSDS Stage 1: Mission Player + Free Rails — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a static GitHub Pages site that replays real Basilisk simulations (run in CI) in a CesiumJS 3D player with synced charts and a parameter-sweep explorer, plus a Codespaces devcontainer and Colab notebook that give students full-fidelity Basilisk with zero installs.

**Architecture:** Python package `sims/` runs three Basilisk scenarios at build time and exports a compact binary run format (BSD1) + JSON manifests into `data/`; a Vite+TypeScript+CesiumJS app in `web/` decodes and replays them entirely client-side; one GitHub Actions workflow tests, simulates, builds, and deploys to Pages.

**Tech Stack:** Python 3.12, `bsk==2.11.1` (Basilisk), numpy, pytest · Node 22, Vite, TypeScript, CesiumJS (npm), vitest · GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-08-18-basilisk-missions-stage1-design.md` — read it first; §4 (BSD1 format) is the contract both sides implement.

## Global Constraints

- Pin `bsk==2.11.1` in `sims/pyproject.toml` (spec D2/§11).
- v1 scenarios must not require SPICE kernels or any network at sim time (spec D3).
- Player makes zero external network requests at runtime: no Cesium Ion token, bundled Natural Earth II imagery only (spec D6).
- Positions stored/rendered in the inertial frame with header epoch (spec D9); attitude stored as MRP (spec D8).
- Both site pages carry the Basilisk ISC attribution footer (spec D10, §6).
- All work on branch `claude/plugins-install-4d9a00`; never push elsewhere (spec D11).
- Generated `data/` is git-ignored except committed test fixtures.
- Commit after every green task; run `pytest sims/tests -q` (and `npm test` once web exists) before each commit.

---

### Task 1: Free rails + repo scaffold (devcontainer, Colab notebook, README, .gitignore)

**Files:**
- Create: `.devcontainer/devcontainer.json`
- Create: `notebooks/basilisk_quickstart.ipynb`
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the repo front door; later tasks only append badges/links to README.

- [ ] **Step 1: Write `.devcontainer/devcontainer.json`**

```json
{
  "name": "BSDS Basilisk Workbench",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "postCreateCommand": "pip install --user 'bsk==2.11.1' matplotlib pandas jupyter && (test -f sims/pyproject.toml && pip install --user -e './sims[test]' || true)",
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "ms-toolsai.jupyter"]
    }
  },
  "hostRequirements": {"cpus": 2, "memory": "8gb"}
}
```

- [ ] **Step 2: Write `notebooks/basilisk_quickstart.ipynb`** — cells: title/intro markdown; `%pip install bsk==2.11.1 --quiet`; a self-contained two-body LEO orbit (SimulationBaseClass + spacecraft + `gravFactory.createEarth()` point-mass + recorder, 1 orbit, RK4 default); matplotlib plot of the orbit in the orbital plane + altitude vs time; closing markdown linking Basilisk docs and this repo. Verify the sim cell code locally with the venv python before committing (copy cell code to a temp .py and run it).

- [ ] **Step 3: Write `README.md`** — what BSDS is (browser-first Basilisk missions, staged plan), Quickstart table: Colab badge `[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/JPWPWhitney/BSDS/blob/claude/plugins-install-4d9a00/notebooks/basilisk_quickstart.ipynb)`, Codespaces badge `[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/JPWPWhitney/BSDS)`, repo layout, "Powered by Basilisk (AVS Lab, CU Boulder) — ISC" attribution, spec/plan links.

- [ ] **Step 4: Write `.gitignore`** — `data/`, `node_modules/`, `dist/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `.venv/`.

- [ ] **Step 5: Commit and push** — `git add -A && git commit -m "feat: free rails — Codespaces devcontainer, Colab quickstart, README"` then push (unblocks the student collaborator).

### Task 2: BSD1 format writer/reader (`sims/bsds_sims/bsd1.py`) — TDD

**Files:**
- Create: `sims/pyproject.toml`, `sims/bsds_sims/__init__.py`
- Create: `sims/bsds_sims/bsd1.py`
- Test: `sims/tests/test_bsd1.py`

**Interfaces:**
- Produces:
  - `Channel(name: str, data: np.ndarray[n, c] float64, unit: str = "", frame: str = "", dtype: str = "f32")`
  - `write_run(path, *, scenario: str, run: str, title: str, epoch: str, params: dict, time_s: np.ndarray, channels: list[Channel], bodies: list[dict], metrics: dict) -> int` (bytes written)
  - `read_run(path) -> RunData` with `.header: dict`, `.time_s: np.ndarray`, `.channel(name) -> np.ndarray[n, c] float64` (dequantized)
- `sims/pyproject.toml`: name `bsds-sims`, requires `bsk==2.11.1`, `numpy`; extras `test = ["pytest"]`.

- [ ] **Step 1: Write failing tests** (`test_bsd1.py`): f32 round-trip exact equality; i16 round-trip `np.max(np.abs(back - orig)) <= scale/2 + 1e-12` per component with scale recomputed as `(max-min)/65534`; constant-channel i16 round-trips exactly; magic/`header_length` framing (read first 12 bytes manually, json parses, offsets self-consistent: each channel `byte_offset + byte_length` ≤ file payload size); `read_run` on truncated file raises `ValueError`; unknown extra header keys survive read (forward compat).
- [ ] **Step 2: Run** `pytest sims/tests/test_bsd1.py -q` → expect import errors/failures.
- [ ] **Step 3: Implement `bsd1.py`** per spec §4: header dict assembly, contiguous column-major-per-channel payload (`data[:, c].astype('<f4')` or quantized `<i2`), time always `<f8`. Quantization: `offset=min`, `scale=(max-min)/65534` (guard zero-range with `scale=1.0`), stored `int16` = `round((x-offset)/scale) - 32767`, dequant inverse. (Symmetric bias keeps stored values in int16 range; document formula in module docstring — the TS decoder must mirror it exactly.)
- [ ] **Step 4: Run tests** → PASS. **Step 5: Commit** `feat: BSD1 run format writer/reader with quantization`.

### Task 3: basic_orbit scenario + recording helpers — TDD

**Files:**
- Create: `sims/bsds_sims/recording.py`, `sims/bsds_sims/scenarios/__init__.py`, `sims/bsds_sims/scenarios/basic_orbit.py`
- Test: `sims/tests/test_scenarios.py`

**Interfaces:**
- Produces: `RunResult(time_s, channels: dict[str, np.ndarray], bodies, metrics, epoch, title)`; registry `SCENARIOS: dict[str, module]` where each scenario module has `ID: str`, `TITLE: str`, `KIND: "single"|"sweep"`, `run(params: dict) -> RunResult`, and for sweeps `AXES` + `sweep_grid() -> list[dict]`.
- `recording.py`: `attach_sc_recorder(scSim, taskName, scObject, min_update_ns) -> recorder`, `pull(rec) -> dict` with keys `r_BN_N`, `v_BN_N`, `sigma_BN`, `omega_BN_B`, time.

- [ ] **Step 1: Failing test** — `basic_orbit.run({})` returns n>100 samples, all finite; orbit radius stays within [6578 km, 7578 km] for the default 200 km-eccentric LEO... (use the actual elements chosen: a=6878 km, e=0.01 → bounds `a*(1±e)` ±1 km); metrics include `period_min` within 2% of `2π√(a³/μ)`.
- [ ] **Step 2:** Run → fail. **Step 3:** Implement with the canonical pattern (verified against bsk 2.11.1 in-container): `SimulationBaseClass.SimBaseClass()`, dynamics process+task at `macros.sec2nano(10)`, `spacecraft.Spacecraft()`, `simIncludeGravBody.gravBodyFactory().createEarth()` (`isCentralBody=True`, attach via `gravFactory.addBodiesTo(scObject)`), elements→r,v via `orbitalMotion.elem2rv`, recorder at ~5 s cadence for ~1.05 orbits, epoch `2026-01-01T00:00:00Z`. **Step 4:** tests PASS. **Step 5:** Commit `feat: basic_orbit scenario`.

### Task 4: hohmann scenario (impulsive two-burn) — TDD

**Files:**
- Create: `sims/bsds_sims/scenarios/hohmann.py`; extend `test_scenarios.py`

**Interfaces:** same scenario contract; params `{r_start_km: 6878, r_target_km: 42164}`.

- [ ] **Step 1: Failing test** — final orbit radius within 1% of `r_target_km` and eccentricity < 0.02 after burn 2; `metrics` carry `dv1_ms`, `dv2_ms`, `transfer_time_h`, with `dv1+dv2` within 1% of the analytic Hohmann total for those radii.
- [ ] **Step 2:** fail. **Step 3:** Implement as three arcs (park ¼ orbit → transfer half-ellipse → final ¼ orbit) using the `scenarioOrbitManeuver` state-modification pattern: between arcs, get `scObject.dynManager.getStateObject(scObject.hub.nameOfHubVelocity)`, read `getState()`, scale the velocity vector to the analytic post-burn magnitude, `setState()`, continue `ExecuteSimulation()` with extended stop time. Timing: burn 2 fires at `t_burn1 + π√(a_t³/μ)`. **Step 4:** PASS. **Step 5:** Commit `feat: hohmann transfer scenario`.

### Task 5: drag_deorbit scenario + sweep + build CLI — TDD

**Files:**
- Create: `sims/bsds_sims/scenarios/drag_deorbit.py`, `sims/bsds_sims/build.py`
- Test: extend `test_scenarios.py`; create `sims/tests/test_build.py`
- Create: `web/test/fixtures/` fixture generation hook (small committed .bsd1 + expected JSON, produced by a pytest fixture-writer marked `--write-fixtures`)

**Interfaces:**
- `drag_deorbit`: params `{ballistic_coeff, alt_km}`; `AXES` per spec §4 manifest example (4×4 grid); `run()` propagates in 30-min chunks until altitude < 100 km or 30 days cap; channels add `altitude`; metric `deorbit_time_h`.
- `build.py` CLI: `python -m bsds_sims.build --out DIR [--scenario ID] [--downsample-sweep 1500]` → writes `<out>/index.json`, per-scenario `manifest.json` + `.bsd1` runs (hero f32, sweep members i16 + downsampled), returns nonzero on any scenario failure.
- Modules: `exponentialAtmosphere.ExponentialAtmosphere` (env model, `addSpacecraftToModel(scObject.scStateOutMsg)`) + `dragDynamicEffector.DragDynamicEffector` (`coreParams.projectedArea`, `coreParams.dragCoeff`, subscribe `atmoDensInMsg` to `envModel.envOutMsgs[0]`, `scObject.addDynamicEffector(dragEffector)`) — verify exact attribute names in-container against bsk 2.11.1 before relying on them; adjust test tolerances only with justification.

- [ ] **Step 1: Failing tests** — high-drag case (BC=12.5, alt 250) deorbits in < 10 days with monotonically-trending-down apogee; low-drag case (BC=100, alt 400) does NOT deorbit inside a 2-day probe run; build CLI on `--scenario basic_orbit` produces index+manifest+file that `read_run` round-trips and whose manifest `bytes` matches the file size.
- [ ] **Step 2:** fail. **Step 3:** implement scenario then CLI. **Step 4:** PASS. **Step 5:** run the full `build --out data` locally, eyeball sizes (<2 MB total), commit `feat: drag deorbit sweep + site data build CLI` (code + fixtures only, not `data/`).

### Task 6: Web scaffold + BSD1 decoder + attitude math (`web/`) — TDD

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`, `web/player.html`, `web/src/bsd1.ts`, `web/src/attitude.ts`, `web/src/main.ts` (index page), `web/src/player.ts` (stub wiring)
- Test: `web/test/bsd1.test.ts`, `web/test/attitude.test.ts` (vitest)

**Interfaces:**
- `bsd1.ts`: `decodeRun(buf: ArrayBuffer): RunData` — `RunData.header`, `.time: Float64Array`, `.channel(name): {data: Float64Array, components: number} | null` (dequantized, column-major per component with `component(i): Float64Array` view helper).
- `attitude.ts`: `mrpToQuaternion(s: [number,number,number]): [w,x,y,z]` (`q = [(1-|s|²), 2s] / (1+|s|²)`), `mrpToDcm(s)`.
- Vite multi-page build (index + player), `vite-plugin-static-copy` (or equivalent documented Cesium+Vite recipe) for Cesium's `Assets/Widgets/Workers` static files, `CESIUM_BASE_URL` define; `base: './'` for Pages subpath.

- [ ] **Step 1: Failing vitest** — decode the committed Python-written fixture: header fields match expected JSON; f32 channel equals expected values exactly; i16 channel within scale/2; `mrpToQuaternion([0,0,0]) = [1,0,0,0]`; `mrpToQuaternion([0,0,Math.tan(Math.PI/8)])` ≈ 90° z-rotation `[cos45°,0,0,sin45°]` (1e-12); DCM orthonormality.
- [ ] **Step 2:** fail. **Step 3:** implement. **Step 4:** `npm test` PASS and `npm run build` succeeds. **Step 5:** Commit `feat: web scaffold, BSD1 decoder, attitude math`.

### Task 7: Cesium mission player page

**Files:**
- Create: `web/src/scene.ts`, `web/src/timeline.ts`; fill `web/src/player.ts`; style `web/src/style.css`

**Interfaces:**
- `timeline.ts`: wraps Cesium's clock — `initClock(viewer, epochIso, time: Float64Array)`, emits `onTick(tSimSeconds)`; slider/keyboard seeks delegate to Cesium's animation widget.
- `scene.ts`: `buildScene(viewer, run: RunData)` — SampledPositionProperty in `ReferenceFrame.INERTIAL` (epoch-based JulianDates, Lagrange interpolation degree 5), point entity + path trail (trailTime = full span), body-axes triad from `sigma_BN` (three colored unit-vector polylines recomputed per tick via `mrpToDcm`, transformed inertial→fixed with `Transforms.computeIcrfToFixedMatrix` guarded by its undefined-return fallback), camera tracking the entity with a wide default view.
- Offline: `Ion.defaultAccessToken` never set; imagery `TileMapServiceImageryProvider.fromUrl(buildModuleUrl('Assets/Textures/NaturalEarthII'))`; `baseLayerPicker/geocoder/infoBox` off; ellipsoid terrain.

- [ ] **Step 1:** Implement; load `?scenario=basic_orbit` against locally-built `data/` via vite dev proxy or copied dir.
- [ ] **Step 2: Visual verification (required):** headless Chromium (Playwright, `executablePath: '/opt/pw-browsers/chromium'`) screenshot after load + after seeking mid-run; verify globe visible, orbit trail drawn, no console errors; a prograde LEO ground track must drift westward between successive passes (inertial-frame correctness check). Save screenshots to scratch, review them.
- [ ] **Step 3:** Commit `feat: Cesium mission player with inertial playback and attitude triad`.

### Task 8: Charts rail synced to the clock

**Files:**
- Create: `web/src/charts.ts`; extend `player.ts`/`style.css`
- Test: `web/test/charts.test.ts` (pure helpers only: series extraction, nearest-index lookup)

**Interfaces:**
- `charts.ts`: `buildCharts(container, run, clock)` — SVG line charts (no chart lib): altitude km vs time always (derived `|r|−radius` when no `altitude` channel), plus per-component charts for `sigma_BN` when present; shared vertical cursor follows `clock.onTick`; click/drag on a chart seeks the clock. **Before writing chart code, load the project `dataviz` skill and follow its palette/axis/legend/dark-mode rules.**

- [ ] **Step 1:** failing tests for `altitudeSeries(run)` (uses channel when present, derives otherwise; values in km) and `nearestIndex(time, t)` (binary search, clamped). **Step 2:** fail → implement → PASS. **Step 3:** visual check via Playwright screenshot (cursor mid-chart while playing). **Step 4:** Commit `feat: synced telemetry charts`.

### Task 9: Sweep explorer (sliders + heatmap) for drag_deorbit

**Files:**
- Create: `web/src/sweep.ts`; extend `player.ts`
- Test: `web/test/sweep.test.ts`

**Interfaces:**
- `sweep.ts`: `initSweep(container, manifest, onSelectRun)` — one snapping slider per axis; 2D metric heatmap (SVG grid of axes[0]×axes[1], color = `metrics.deorbit_time_h`, sequential palette per dataviz skill, cell click = select run); `selectRun(params)` finds exact grid match (`runIdFor(params)`); prefetch the ±1 neighbors along each axis via `fetch` on idle.

- [ ] **Step 1:** failing tests for `runIdFor(manifest, params)` and neighbor-prefetch list computation. **Step 2:** implement → PASS. **Step 3:** Playwright screenshot of heatmap + slider swap changing the loaded run title. **Step 4:** Commit `feat: parameter sweep explorer`.

### Task 10: CI workflow + Pages deploy + final wiring

**Files:**
- Create: `.github/workflows/build-deploy.yml`
- Modify: `README.md` (site link, status badge), `web/vite.config.ts` if base-path fixes needed

**Interfaces:** consumes everything; produces the live site.

- [ ] **Step 1:** Write the workflow per spec §8 (jobs: test → build-data → build-web → deploy; `actions/setup-python@v5` 3.12, `actions/setup-node@v4` 22, `actions/configure-pages@v5` with `enablement: true`, `actions/upload-pages-artifact@v3` on `web/dist`, `actions/deploy-pages@v4`; permissions `pages: write, id-token: write, contents: read`; triggers: push to the default branch + `workflow_dispatch`). Data flows job→job via `actions/upload-artifact`/`download-artifact` into `web/public/data/`.
- [ ] **Step 2:** Push; watch the run via the GitHub MCP actions tools; fix failures until green.
- [ ] **Step 3:** Fetch the deployed Pages URL, Playwright-load it, screenshot both pages, confirm no console errors and data loads (base-path correctness).
- [ ] **Step 4:** Commit README updates `docs: link live site`; report the URL.

## Self-Review Notes

- Spec coverage: §3 layout→T1/T2/T6; §4 format→T2/T6; §5 pipeline→T3–T5; §6 player→T7–T9; §7 rails→T1; §8 CI→T10; §9 tests distributed per task. Vizard sidecar (spec §5 stretch) intentionally deferred post-T10 — non-blocking by spec.
- Type consistency: `RunResult`/`Channel`/`RunData` names used consistently across T2/T3/T6; quantization formula identical in T2 and T6 tests.
- Basilisk API attribute names (T3–T5) are flagged for in-container verification against bsk 2.11.1 before use — treat compile/attribute errors there as expected discovery, not plan failure.
