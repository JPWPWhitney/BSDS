"""BSDS Mission Lab backend — Modal app.

Deploy (CI does this): `modal deploy backend/bsds_backend/app.py`
Endpoint: POST /run {code, passcode} -> {ok, bsd1_b64?, info, user_stdout}
          GET /healthz -> {ok, gated}

The optional Modal secret `bsds-run-gate` supplies BSDS_RUN_PASSCODE; when it is
absent or empty the gate is open (public) per spec S2-D2.
"""

from __future__ import annotations

import os
from pathlib import Path

import modal

from .core import HARNESS, gate_ok, parse_sandbox_output

app = modal.App("bsds-run")

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Image for BOTH the web endpoint and the sandboxes: Basilisk + the repo's
# bsds_sims package (added at deploy time so it versions with the repo).
sandbox_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("bsk==2.11.1", "numpy")
    .env({"PYTHONPATH": "/pkg"})
    .add_local_dir(str(_REPO_ROOT / "sims" / "bsds_sims"), "/pkg/bsds_sims")
)

web_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "fastapi[standard]"
).add_local_python_source("bsds_backend")

# The gate secret is optional: try to reference it, fall back to none.
try:
    _gate_secrets = [modal.Secret.from_name("bsds-run-gate")]
except Exception:  # pragma: no cover - resolution happens server-side anyway
    _gate_secrets = []

SANDBOX_TIMEOUT_S = 120
SANDBOX_CPU = 1.0
SANDBOX_MEMORY_MB = 2048
MAX_CODE_BYTES = 200_000

ALLOWED_ORIGINS = [
    "https://jpwpwhitney.github.io",
    "http://localhost:4173",
    "http://localhost:5173",
]


@app.function(image=web_image, secrets=_gate_secrets, timeout=SANDBOX_TIMEOUT_S + 30)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    api = FastAPI(title="BSDS Mission Lab")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _required_passcode() -> str | None:
        return os.environ.get("BSDS_RUN_PASSCODE") or None

    class RunRequest(BaseModel):
        code: str
        passcode: str | None = None

    @api.get("/healthz")
    def healthz():
        return {"ok": True, "gated": _required_passcode() is not None}

    @api.post("/run")
    def run(req: RunRequest):
        from fastapi import HTTPException

        if not gate_ok(req.passcode, _required_passcode()):
            raise HTTPException(status_code=401, detail="Bad or missing passcode.")
        if len(req.code.encode("utf-8")) > MAX_CODE_BYTES:
            raise HTTPException(status_code=413, detail="Scenario code too large.")

        sb = modal.Sandbox.create(
            app=app,
            image=sandbox_image,
            timeout=SANDBOX_TIMEOUT_S,
            cpu=SANDBOX_CPU,
            memory=SANDBOX_MEMORY_MB,
            block_network=True,
        )
        try:
            with sb.open("/tmp/user_code.py", "w") as f:
                f.write(req.code)
            with sb.open("/tmp/harness.py", "w") as f:
                f.write(HARNESS)
            proc = sb.exec("bash", "-c", "python /tmp/harness.py < /tmp/user_code.py")
            proc.wait()
            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
        finally:
            sb.terminate()

        outcome = parse_sandbox_output(stdout, stderr)
        return {
            "ok": outcome.ok,
            "bsd1_b64": outcome.bsd1_b64,
            "info": outcome.info,
            "user_stdout": outcome.user_stdout,
            "truncated": outcome.truncated,
        }

    return api
