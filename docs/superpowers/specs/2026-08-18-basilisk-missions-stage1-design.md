# BSDS Stage 1: Browser Mission Player + Free Compute Rails — Design Spec

**Date:** 2026-08-18
**Status:** Approved (approach and section-level design approved in-session by repo owner)
**Repo:** JPWPWhitney/BSDS

## 1. Context and goals

BSDS exists to make Basilisk (the AVS Lab astrodynamics simulation framework,
PyPI package `bsk`, ISC license) mission simulations usable from a browser.
Audiences, in priority order as set by the owner: education (A), outreach/demos
(B), and *mostly* a research workbench (C).

The approved strategy is **staged convergence**:

- **Stage 1 (this spec):** a static "mission player" web site whose data is
  produced by running real Basilisk simulations at build time in CI, plus two
  zero-infrastructure "free rails" that give audience C full-fidelity Basilisk
  immediately (Google Colab notebook, GitHub Codespaces devcontainer).
- **Stage 2 (later spec):** in-site scenario editing with sandboxed server
  execution (Modal was selected as least-owner-effort host by research).
- **Stage 3 (later spec):** WebAssembly/Pyodide port of Basilisk so simulation
  runs fully client-side. An empirical spike (2026-08-18) proved compiled
  Basilisk modules run correctly under Pyodide with machine-epsilon-identical
  numerics; the remaining work is build orchestration, a threading patch, and
  module-topology management.

Stage 1 must not build anything Stage 2/3 throws away: the player consumes
recorded run data through a documented format, and later stages only change
*where the data comes from*.

## 2. Decisions log

| # | Decision | Rationale |
|---|---|---|
| D1 | Host on **GitHub Pages** deployed by GitHub Actions | Zero owner accounts/cost. Payloads at Stage 1 scale (hero runs ~100–300 KB) don't need Cloudflare's Brotli edge; revisit if data outgrows it. |
| D2 | Simulations run **at build time in CI** via `pip install bsk` | Wheels exist since Oct 2025 (v2.11.1 current); install ~2 min; sims run in milliseconds–seconds. |
| D3 | v1 scenarios: **basic orbit, Hohmann transfer (impulsive), drag-deorbit sweep** | Approved scope. None require SPICE kernels (point-mass/J2-free Earth gravity + exponential atmosphere), which removes the kernel-hosting problem from Stage 1 entirely. |
| D4 | Scenario scripts are **thin, self-contained BSDS wrappers** modeled on the official Basilisk examples, not imports of them | The official example scripts are not packaged in the wheel (they download via `bskExamples`); self-contained scripts avoid a network fetch + API drift in CI and keep each scenario ~100 lines. |
| D5 | Custom compact binary run format (**BSD1**, §4) + JSON manifests | Purpose-built for scrubbing playback; supports f32 and quantized i16 columns from day one. |
| D6 | Player renders with **CesiumJS** using its bundled offline Natural Earth II imagery (no Ion token, no external services) | Timeline/clock/interpolation UI comes with Cesium; token-free keeps the site fully static and free. |
| D7 | Spacecraft rendered as **point + orbit trail + body-axes triad** in v1; glTF model is a later enhancement | The attitude triad is more informative than a tiny model and avoids asset licensing/weight now. |
| D8 | Attitude stored as **MRP (sigma_BN)**, converted to quaternion in the player | Matches Basilisk's native attitude representation. |
| D9 | Positions stored in the **inertial frame (r_BN_N)** with an epoch in the header; player uses Cesium's inertial reference frame so Earth rotation/ground tracks are correct | Direct mapping from Basilisk recorder output; no frame conversion in the exporter. |
| D10 | Site branding: **"BSDS"** with explicit "Powered by Basilisk (AVS Lab, CU Boulder)" attribution and the Basilisk ISC notice on the site | Basilisk's ISC license permits everything we do but grants no trademark rights; we attribute, we don't impersonate. |
| D11 | Development continues on branch `claude/plugins-install-4d9a00` (the repo's current default) | Owner can promote/rename to `main` at any time; all tooling references the default branch indirectly where possible. |
| D12 | Free rails ship **first** (devcontainer + Colab notebook) | Unblocks the student collaborator immediately, independent of the player build. |

## 3. Repository layout

```
BSDS/
├── .devcontainer/devcontainer.json      # Codespaces: python + pip install bsk
├── .github/workflows/build-deploy.yml   # test → simulate → export → build → Pages
├── notebooks/basilisk_quickstart.ipynb  # Colab-ready full-fidelity Basilisk
├── sims/                                # Python: scenarios + exporter (installable, `pip install -e sims/`)
│   ├── pyproject.toml
│   ├── bsds_sims/
│   │   ├── __init__.py
│   │   ├── bsd1.py                      # BSD1 format writer/reader (numpy)
│   │   ├── recording.py                 # recorder attachment + channel extraction helpers
│   │   ├── scenarios/
│   │   │   ├── __init__.py              # scenario registry
│   │   │   ├── basic_orbit.py
│   │   │   ├── hohmann.py
│   │   │   └── drag_deorbit.py
│   │   └── build.py                     # CLI: run scenarios/sweeps → site data dir
│   └── tests/
│       ├── test_bsd1.py
│       ├── test_scenarios.py
│       └── test_build.py
├── web/                                 # Vite + TypeScript + CesiumJS player
│   ├── package.json / vite.config.ts / tsconfig.json
│   ├── index.html                       # scenario index page
│   ├── player.html                      # the mission player page
│   ├── src/
│   │   ├── bsd1.ts                      # BSD1 decoder (mirrors sims/bsd1.py)
│   │   ├── attitude.ts                  # MRP→quaternion, MRP→DCM
│   │   ├── timeline.ts                  # playback clock shared by 3D + charts
│   │   ├── scene.ts                     # Cesium scene: entity, trail, triad, camera
│   │   ├── charts.ts                    # right-rail charts scrubbed by the clock
│   │   ├── sweep.ts                     # slider/heatmap UI, nearest-run selection
│   │   └── main.ts / index.ts           # page wiring
│   └── test/                            # vitest: decoder, attitude math, interpolation
├── data/                                # generated by CI (git-ignored); local dev output
└── docs/superpowers/{specs,plans}/
```

## 4. BSD1 run-file format (the load-bearing contract)

One file per run, extension `.bsd1`. Layout:

```
bytes 0..7    magic: ASCII "BSDS0001"
bytes 8..11   uint32 LE: header_length (bytes of UTF-8 JSON that follow)
next          header JSON
next          binary payload (channel columns, layout given by header)
```

Header JSON schema (v1):

```json
{
  "schema": 1,
  "scenario": "drag_deorbit",
  "run": "bc0025_alt300",
  "title": "Drag deorbit, BC=25 kg/m², h₀=300 km",
  "epoch": "2026-01-01T00:00:00Z",
  "params": {"ballistic_coeff": 25.0, "alt_km": 300.0},
  "n": 5400,
  "bodies": [{"name": "earth", "mu": 3.986004415e14, "radius_km": 6378.1366}],
  "time": {"dtype": "f64", "unit": "s", "byte_offset": 0, "byte_length": 43200},
  "channels": [
    {"name": "r_BN_N", "components": 3, "unit": "m", "frame": "inertial",
     "dtype": "f32", "byte_offset": 43200, "byte_length": 64800},
    {"name": "sigma_BN", "components": 3, "unit": "", "frame": "inertial→body MRP",
     "dtype": "i16", "byte_offset": 108000, "byte_length": 32400,
     "scale": [1.5e-5, 1.5e-5, 1.5e-5], "offset": [-0.42, -0.11, 0.3]}
  ],
  "metrics": {"deorbit_time_h": 41.2, "final_alt_km": 100.0}
}
```

Rules:

- `time` is always float64 seconds from sim start, strictly increasing.
- Channel columns are stored **contiguously, column-major per channel**
  (all of component 0's samples, then component 1's, …), so a component is one
  contiguous typed-array view in JS.
- `dtype` is `"f32"` or `"i16"`. For `i16`, real = stored × scale[c] + offset[c],
  with scale/offset per component computed as offset=min, scale=(max−min)/65534
  over that component (degenerate constant channels get scale=1). Round-trip
  error is therefore ≤ scale/2 per sample.
- Required channels for the player: `r_BN_N` (m). Optional, rendered when
  present: `v_BN_N` (m/s), `sigma_BN` (MRP), `omega_BN_B` (rad/s),
  `rw_speeds` (rad/s, N components), `thrust` (N), `altitude` (m).
- Unknown channels must be ignored by readers (forward compatibility).

Per-scenario manifest `data/<scenario>/manifest.json`:

```json
{
  "schema": 1, "id": "drag_deorbit", "title": "Drag Deorbit",
  "kind": "sweep",
  "description": "How long until it comes down?",
  "hero": "bc0025_alt300",
  "axes": [
    {"param": "ballistic_coeff", "label": "Ballistic coefficient (kg/m²)", "values": [12.5, 25, 50, 100]},
    {"param": "alt_km", "label": "Initial altitude (km)", "values": [250, 300, 350, 400]}
  ],
  "runs": [{"id": "bc0025_alt300", "params": {"ballistic_coeff": 25.0, "alt_km": 300.0},
            "file": "bc0025_alt300.bsd1", "bytes": 140600,
            "metrics": {"deorbit_time_h": 41.2}}]
}
```

Site index `data/index.json`: `{"schema": 1, "scenarios": [{"id", "title",
"kind", "description", "path"}]}`.

## 5. Simulation pipeline (`sims/`)

- Each scenario module exposes `run(params: dict) -> RunResult` where
  `RunResult` carries the numpy time base, a dict of channel arrays, body
  metadata, and computed metrics. `build.py` provides a CLI:
  `python -m bsds_sims.build --out ../data [--scenario id]` that runs every
  registered scenario (hero runs at full sample rate, sweep members
  downsampled), writes BSD1 files + manifests + index.
- **basic_orbit:** single spacecraft, point-mass Earth gravity
  (`gravFactory.createEarth()` without SPICE), one LEO orbit propagated with
  the default RK4 integrator; records r/v. Modeled on `scenarioBasicOrbit`.
- **hohmann:** impulsive two-burn transfer LEO→GEO done as three propagation
  arcs with velocity-state modification between arcs (the official
  `scenarioOrbitManeuver` pattern). Records r/v; metrics: transfer time,
  Δv₁, Δv₂, total Δv.
- **drag_deorbit:** exponential atmosphere (`exponentialAtmosphere`) + cannonball
  drag effector on a LEO spacecraft; propagate until altitude < 100 km
  (terminal event checked between fixed-duration chunks) or a max-duration cap;
  records r/v + altitude; metric: deorbit time. Sweep over ballistic
  coefficient × initial altitude (4×4 grid in v1); sweep members downsampled to
  ≤1500 samples and quantized i16; hero run f32 at full viz rate.
- Sample-rate policy: recorders use `minUpdateTime` so hero runs carry
  ~2000–5000 samples regardless of integration step.
- Determinism: fixed initial conditions and epoch per scenario (no RNG), so CI
  output is reproducible run-to-run.
- Vizard sidecar (stretch, non-blocking): where the installed wheel's
  `vizSupport.enableUnityVisualization(..., saveFile=...)` works headless, also
  publish the official Vizard `.bin` next to each hero run for desktop
  playback; failures skip the sidecar with a logged warning, never fail the build.

## 6. Player (`web/`)

- **Stack:** Vite + TypeScript, CesiumJS from npm. No external network use at
  runtime: Cesium's bundled offline Natural Earth II imagery, no Ion token, no
  terrain server (ellipsoid terrain).
- **player.html?scenario=<id>[&run=<id>]** loads the manifest, fetches the run
  file, decodes it (`bsd1.ts`), and drives:
  - Cesium `Viewer` with timeline+animation widgets; entity position from a
    `SampledPositionProperty` in the **inertial** reference frame (epoch from
    header → Cesium `JulianDate`); orbit trail via path graphics; body-axes
    triad drawn from `sigma_BN` when present (MRP→quaternion in `attitude.ts`).
  - A right rail of 2–3 charts (altitude vs time always; others per available
    channels) rendered as the timeline clock moves, with a scrub cursor synced
    both ways (chart click seeks the clock).
  - For sweep scenarios, `sweep.ts` renders one slider per axis (snapping to
    grid values), a metric heatmap over the two primary axes built from the
    manifest (no run fetches needed), and swaps the loaded run to the nearest
    grid point on slider change, prefetching neighbors.
- **index.html** lists scenarios from `data/index.json` as cards.
- Attribution footer on both pages: "Powered by Basilisk — © Autonomous Vehicle
  Systems Lab, University of Colorado Boulder (ISC License)" linking to the
  Basilisk repo, plus a link to BSDS's own repo.
- Chart visual design follows the project's dataviz guidance (loaded at
  implementation time): shared palette, dark/light safe, axis/legend rules.

## 7. Free rails

- **.devcontainer/devcontainer.json:** `mcr.microsoft.com/devcontainers/python:3.12`
  base, `postCreateCommand` installing `bsk`, matplotlib, pandas, jupyter, and
  `-e ./sims`; VS Code extensions: Python + Jupyter. Purpose: "open this repo
  in a Codespace → full Basilisk workbench in the browser," billed to the
  launching user's own free quota.
- **notebooks/basilisk_quickstart.ipynb:** Colab-ready; cells: intro markdown →
  `%pip install bsk` → minimal two-body orbit sim with recorder → matplotlib
  orbit plot → pointers (Basilisk docs, this repo, how to go further). README
  gets an "Open in Colab" badge pointing at the notebook on the default branch.

## 8. CI/CD (`.github/workflows/build-deploy.yml`)

On push to the default branch and manual dispatch:

1. **test:** set up Python 3.12 → `pip install bsk -e ./sims[test]` → `pytest sims/tests -q`.
2. **simulate+export:** `python -m bsds_sims.build --out data` (artifact).
3. **web:** Node 22 → `npm ci && npm test && npm run build` in `web/`, copying
   `data/` into the built site.
4. **deploy:** `actions/configure-pages@v5` with `enablement: true` (attempts
   to enable Pages automatically; if the repo forbids it, the workflow's failure
   message tells the owner to enable Pages → "GitHub Actions" in repo settings —
   the one possible manual step), `actions/upload-pages-artifact`,
   `actions/deploy-pages`. Workflow permissions: `pages: write`, `id-token:
   write`, `contents: read`.

## 9. Testing strategy

- **sims (pytest):** BSD1 writer/reader round-trip (f32 exact; i16 within
  scale/2 bound); header validation errors; each scenario smoke test (runs,
  n>100, finite values, basic physics sanity: orbit radius bounds for
  basic_orbit, deorbit terminates for a high-drag case, Hohmann final radius
  within 1% of GEO); build CLI produces index + manifests + files that re-read.
- **web (vitest):** bsd1.ts decodes fixture files byte-for-byte produced by the
  Python writer (a small fixture is committed); MRP→quaternion against known
  values (e.g. σ=(0,0,0)→identity; σ=(0,0,tan(90°/4))→90° yaw); nearest-run
  selection logic; linear/Hermite sample interpolation at exact and midpoint
  times.
- **CI is the integration test:** any scenario failure, export failure, or
  build failure fails the deploy.

## 10. Out of scope for Stage 1

Live/server execution of user code (Stage 2); the WASM port (Stage 3); SPICE
ephemerides and non-Earth scenes (asteroid/L2 need three.js — enters with the
scenario set expansion); glTF spacecraft models; Monte Carlo; Vizard live
streaming; user accounts/persistence of any kind.

## 11. Risks and mitigations

- **`bsk` wheel/API drift in CI:** pin `bsk==2.11.1` in `sims/pyproject.toml`;
  bump deliberately.
- **Pages enablement may need one manual click** (see §8) — surfaced in the
  workflow failure message and README.
- **Cesium inertial-frame rendering subtleties** (epoch handling, ICRF↔Fixed
  transforms for the triad): covered by a dedicated implementation task with
  visual verification against the known ground-track direction of a prograde
  LEO orbit.
- **Sweep payload growth:** v1 grid is 16 runs ≤ ~1 MB total; format's i16 path
  and downsampling policy are already in place for larger grids.
