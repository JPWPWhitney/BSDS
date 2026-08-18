# BSDS — Basilisk missions in the browser

BSDS makes real spacecraft mission simulations — powered by
[Basilisk](https://avslab.github.io/basilisk/), the open-source astrodynamics
framework from the AVS Lab at CU Boulder — runnable and watchable from a web
browser, with nothing to install.

**Live site:** <https://jpwpwhitney.github.io/BSDS/> · **How it all fits
together:** [ARCHITECTURE.md](ARCHITECTURE.md)

## Run Basilisk right now (zero install)

| Rail | What you get | Start |
|---|---|---|
| **Google Colab** | Full-fidelity Basilisk in a free notebook, running in ~3 minutes | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/JPWPWhitney/BSDS/blob/main/notebooks/basilisk_quickstart.ipynb) |
| **GitHub Codespaces** | A persistent browser VS Code workbench with Basilisk preinstalled (terminal, notebooks, real files) — billed to *your* free Codespaces quota (students: free Pro via [GitHub Education](https://education.github.com)) | [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/JPWPWhitney/BSDS) |

## The project

All three planned stages have shipped (design history in
[`docs/superpowers/specs/`](docs/superpowers/specs/), system description in
[ARCHITECTURE.md](ARCHITECTURE.md)):

1. **Stage 1 — mission player:** eight Basilisk scenarios run in CI and a
   CesiumJS/three.js 3D player replays them with synced telemetry charts and
   parameter-sweep exploration. Free hosting, no accounts.
2. **Stage 2 — Mission Lab:** edit and run real scenario code in the browser
   against sandboxed cloud execution (Modal, no network, hard resource caps).
3. **Stage 3 — WASM Lab:** a subset of Basilisk cross-compiled to
   WebAssembly (`bskcore`) — simulations run fully client-side, matching
   native results to machine precision.

## Repository layout

```
notebooks/       Colab-ready quickstart notebook
.devcontainer/   GitHub Codespaces workbench definition
sims/            Python: Basilisk scenarios + BSD1 run-data exporter
backend/         Mission Lab cloud backend (Modal sandbox execution)
web/             The site: mission player + both labs (Vite + TypeScript)
wasm/            Basilisk -> WebAssembly port (bskcore wheel pipeline)
docs/superpowers Design specs and implementation plans
```

## Attribution

BSDS is an independent project **powered by Basilisk** — © Autonomous Vehicle
Systems Lab, University of Colorado Boulder, distributed under the
[ISC License](https://github.com/AVSLab/basilisk/blob/develop/LICENSE).
BSDS is not affiliated with or endorsed by the AVS Lab. Desktop 3D playback of
recorded runs is available with [Vizard](https://github.com/AVSLab/vizard).
