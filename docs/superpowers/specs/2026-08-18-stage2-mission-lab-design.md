# BSDS Stage 2: Mission Lab (edit & run real Basilisk in the browser) — Design Spec

**Date:** 2026-08-18
**Status:** Approved (staged-convergence approach approved by owner; Stage 2 kickoff
ordered "Stage 2 … then stage three"; access-control default adopted per the
recommended option with owner-flippable config)

## 1. Goal

A "Mission Lab" page on the existing site: edit real Basilisk scenario Python in
a browser editor, execute it at full native fidelity in an isolated sandbox, and
replay the result in the Stage 1 player (same 3D scene, charts, metrics) —
no local installs for the person running code.

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| S2-D1 | Execution on **Modal** (Starter plan, $30/mo included credits); **deployed by GitHub Actions**, never from the dev container | Research pick (least owner effort, gVisor per-run sandboxes are Modal's core product). This container's egress blocks Modal, and CI deploy keeps credentials in repo secrets, out of chat. |
| S2-D2 | **Passcode gate by default, public by config**: requests carry a passcode checked server-side; the passcode comes from repo secret `BSDS_RUN_PASSCODE` → Modal secret. If the secret is absent/empty, the gate is off (public). | Arbitrary code execution burns owner credits; a shared passphrase blocks drive-by abuse with zero accounts. Deleting the secret = going public. |
| S2-D3 | **User-code contract = the Stage 1 scenario contract**: the submitted module must define `run(params: dict) -> RunResult`. The sandbox harness imports it, calls `run({})`, and exports BSD1 bytes with `bsds_sims.bsd1`. | The lab's templates are literally our scenario files; results flow into the existing `bsd1.ts` decoder and player with zero new player code. |
| S2-D4 | **Plain POST request/response**, 120 s cap; no streaming | Measured runtimes: basic orbit ~0.02 s, worst 30-day deorbit ~2 s. Streaming is complexity without payoff at Stage 2 scale. |
| S2-D5 | Sandbox limits: 1 CPU, 2 GiB, 120 s wall, **network blocked**; the sandbox image bakes `bsk==2.11.1` + the repo's `sims/` package at deploy time | Full isolation of untrusted code (gVisor + no egress + caps); image versioned with the repo. |
| S2-D6 | Backend endpoint discovery: the CI deploy job captures the Modal URL and writes `lab-config.json` into the site build (`{"endpoint": ..., "gated": true|false}`); when secrets are missing the job writes `{"endpoint": null}` and the lab page shows a "backend not deployed" notice | Site never hardcodes a URL; the page degrades gracefully before the owner's Modal secrets exist. |
| S2-D7 | Frontend: `web/lab.html` — CodeMirror 6 Python editor + template picker (the three scenario sources shipped as site data) on the left, the existing player components on the right | One page, existing modules reused. |
| S2-D8 | Scenario modules switch to **absolute imports** (`from bsds_sims.recording import …`) | Makes the same files valid both as package members and as standalone lab templates executed in the sandbox. |
| S2-D9 | CORS: backend allows origins `https://jpwpwhitney.github.io` and localhost dev | Static site calls a different host. |
| S2-D10 | Error surface: harness returns structured JSON (`ok`, `error`, `stdout` tail, timing) alongside the BSD1 payload (base64) | Students see their tracebacks in the page. |

## 3. Architecture

```
browser (lab.html)                    GitHub Actions                    Modal
┌───────────────────┐   POST /run    ┌─────────────┐   modal deploy   ┌─────────────────┐
│ CodeMirror editor │ ─────────────► │ deploy job  │ ───────────────► │ FastAPI endpoint│
│ template picker   │  {code, pass}  │ (secrets)   │                  │  gate check     │
│ existing player   │ ◄───────────── └─────────────┘                  │  Sandbox.create │
│ (bsd1.ts, scene,  │  {ok, bsd1_b64,                                 │   └─ harness:   │
│  charts, metrics) │   metrics, stdout}                              │      user run() │
└───────────────────┘                                                 │      → BSD1     │
                                                                      └─────────────────┘
```

- `backend/bsds_backend/core.py`: pure logic — gate comparison (constant-time),
  harness script construction, sandbox-output parsing. Fully unit-tested with no
  Modal dependency.
- `backend/bsds_backend/app.py`: the Modal app — image definition, FastAPI ASGI
  endpoint, `Sandbox` orchestration, CORS. Exercised in CI at deploy.
- Harness protocol: user code → sandbox stdin → written to `/tmp/user_scenario.py`
  → imported → `run({})` → `bsd1.write_run` to bytes → printed to stdout between
  sentinel lines as base64 with a JSON trailer. Anything outside sentinels is
  captured user stdout.

## 4. CI changes

Extend `build-deploy.yml`: new job `deploy-backend` (needs: test-and-simulate;
runs when `MODAL_TOKEN_ID` secret exists): `pip install modal && modal deploy
backend/bsds_backend/app.py`, create/refresh the Modal secret from
`BSDS_RUN_PASSCODE`, emit `lab-config.json` as an artifact; `build-web` consumes
it (or writes the null config when the job was skipped).

## 5. Owner setup (one-time)

Three repo secrets (Settings → Secrets and variables → Actions):
`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` (from modal.com → Settings → API Tokens),
and `BSDS_RUN_PASSCODE` (any passphrase the owner picks; share it with intended
users; delete it later to go public).

## 6. Testing

- `backend/tests/`: gate accepts/rejects (constant-time path), harness script
  embeds user code safely (no f-string injection; code passed via stdin, never
  interpolated), output parser handles: happy path, user traceback, sentinel
  garbage, oversize output (cap + truncate flag).
- Existing web tests keep covering decode/attitude; new vitest for lab page pure
  helpers (template list handling, config fallback states).
- Post-deploy (after owner secrets land): live smoke — POST the basic-orbit
  template, expect BSD1 that decodes with n>100; wrong passcode → 401.

## 7. Out of scope for Stage 2

Streaming logs, saved user scenarios/sharing links, accounts, parameter UI for
user code, Monte Carlo, GPU, package installation from user code (image is
fixed), rate-limiting beyond Modal's own concurrency + the passcode gate.
