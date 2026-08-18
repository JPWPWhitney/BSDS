# BSDS Stage 2: Mission Lab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Mission Lab: browser editor → Modal-sandboxed Basilisk execution → replay in the Stage 1 player, deployed by CI once the owner's three repo secrets exist.

**Architecture:** Pure logic in `backend/bsds_backend/core.py` (unit-tested, Modal-free), the Modal app in `app.py`, a CodeMirror lab page reusing the Stage 1 player modules, and a CI `deploy-backend` job that also plumbs the endpoint URL into the site via `lab-config.json`.

**Tech Stack:** Python 3.12, `modal`, FastAPI (bundled with Modal images) · CodeMirror 6 · existing Vite/Cesium stack.

**Spec:** `docs/superpowers/specs/2026-08-18-stage2-mission-lab-design.md`

## Global Constraints

- User code is NEVER string-interpolated into harness code — it travels via sandbox stdin (spec §6).
- Sandbox: cpu=1, memory=2048 MiB, timeout=120 s, `block_network=True` (spec S2-D5).
- Gate: constant-time compare; absent/empty `BSDS_RUN_PASSCODE` ⇒ public (spec S2-D2).
- The lab page must render usefully with `{"endpoint": null}` (spec S2-D6).
- All work on `main`; commit per green task.

### Task 1: scenarios → absolute imports (template-compatibility refactor)
- [ ] Switch `sims/bsds_sims/scenarios/*.py` from `from ..recording import …` to `from bsds_sims.recording import …`; run `pytest sims/tests -q` (15 pass); commit.

### Task 2: backend core (TDD, no Modal dependency)
**Files:** `backend/bsds_backend/{__init__.py,core.py}`, `backend/tests/test_core.py`, `backend/pyproject.toml` (name `bsds-backend`, deps `modal>=1.0`; extras test=[pytest]).
**Interfaces:** `gate_ok(supplied: str|None, required: str|None) -> bool` (empty/None required ⇒ True; constant-time via hmac.compare_digest); `HARNESS: str` (the python source run inside the sandbox: reads user code from stdin, writes /tmp/user_scenario.py, imports as module `user_scenario`, calls `run({})`, exports BSD1 via bsds_sims.bsd1 to bytes, prints `BSDS_BEGIN`, base64, `BSDS_END`, then a JSON line `{"ok":true,"metrics":…,"title":…,"elapsed_s":…}`; on exception prints JSON `{"ok":false,"error":traceback tail}`); `parse_sandbox_output(stdout: str, stderr: str) -> RunOutcome` dataclass `{ok, bsd1_b64|None, info: dict, user_stdout: str (≤20 kB, truncated flag)}`.
- [ ] Failing tests: gate truthiness matrix; parse happy path (feed a synthetic sentinel block built from a real `bsd1.write_run` byte string); parse user-traceback path; parse garbage (no sentinels ⇒ ok=False with stderr excerpt); oversize stdout truncated. Run → red → implement → green → commit.

### Task 3: Modal app
**Files:** `backend/bsds_backend/app.py`.
Content: `modal.App("bsds-run")`; image = `modal.Image.debian_slim(python_version="3.12").pip_install("bsk==2.11.1","numpy").add_local_dir("../sims/bsds_sims", "/pkg/bsds_sims")` with `PYTHONPATH=/pkg`; secret `modal.Secret.from_name("bsds-run-gate", required_keys=[])` tolerated-if-missing; `@app.function` + `@modal.asgi_app()` FastAPI with CORS (github.io origin + localhost), `POST /run {code, passcode}` → gate → `modal.Sandbox.create(image=…, app=…, timeout=120, cpu=1, memory=2048, block_network=True)` → `sb.exec("python","-c",HARNESS)` writing code to stdin → collect stdout/stderr → `parse_sandbox_output` → JSON response; `GET /healthz` → `{ok, gated}`. (Exact Modal API names verified against the installed `modal` package before commit — import-time construction is testable offline.)
- [ ] `python -c "import bsds_backend.app"` succeeds locally (no network calls at import); commit.

### Task 4: lab page
**Files:** `web/lab.html`, `web/src/lab.ts`, `web/src/templates.ts`; npm deps `codemirror`, `@codemirror/lang-python`, `@codemirror/theme-one-dark`; `sims/bsds_sims/build.py` gains `--templates` output copying `scenarios/*.py` + a generated `templates.json` into the data dir; `index.html` gains a "Mission Lab" card/link.
Behavior: load `data/lab-config.json` (fallback `{"endpoint":null}`); template dropdown → editor; Run button → POST; while running show status; on `ok` → base64→ArrayBuffer→`decodeRun`→ reuse `initClock`/`buildScene`/`buildCharts`/metrics exactly like player.ts (factor the shared "present a RunData" block out of player.ts into `present.ts` used by both pages); on error → traceback panel; passcode field shown when `gated`, persisted to localStorage.
- [ ] vitest: config fallback + base64 decode roundtrip helper; build passes; Playwright screenshot of lab.html with `endpoint:null` notice + editor rendered; commit.

### Task 5: CI deploy job + config plumbing
**Files:** `.github/workflows/build-deploy.yml`.
- [ ] Add job `deploy-backend` (after test-and-simulate): guarded `if: ${{ secrets.MODAL_TOKEN_ID != '' }}` via env indirection (secrets can't be used directly in `if` — use a setup step exporting to `$GITHUB_OUTPUT`); steps: setup-python, `pip install modal`, `modal secret create bsds-run-gate BSDS_RUN_PASSCODE=… --force` (only when passcode secret present), `modal deploy backend/bsds_backend/app.py`, parse the printed URL, write `lab-config.json` artifact. `build-web` downloads it when present else writes `{"endpoint":null,"gated":false}` into `web/public/data/`.
- [ ] Push; confirm the job SKIPS cleanly with no secrets and the site still builds green; commit is the push.

### Task 6 (blocked on owner secrets): live verification
- [ ] After secrets land: re-run workflow; confirm deploy-backend runs; `curl healthz`; POST the basic_orbit template with the passcode from the owner; verify BSD1 decodes (n>100) and wrong passcode → 401; Playwright the live lab page end-to-end; report.

## Self-Review
Spec coverage: S2-D1/D6→T5, D2→T2/T3/T5, D3/D8→T1/T2, D4/D5→T3, D7→T4, D9→T3, D10→T2/T4, §6 tests→T2/T4/T6. No placeholders; interfaces named consistently (`gate_ok`, `HARNESS`, `parse_sandbox_output`, `lab-config.json`).
