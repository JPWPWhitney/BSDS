"""Pure logic for the Mission Lab backend: the access gate, the sandbox
harness source, and the sandbox-output parser. No Modal imports here — this
module is fully unit-testable offline (see backend/tests/test_core.py).

Harness protocol (stdout of the sandboxed python process):
- anything the user prints passes through untouched (captured, size-capped);
- on success the harness emits a sentinel block

      BSDS_RESULT_BEGIN_7f3a
      <base64 of the BSD1 run file>
      BSDS_RESULT_END_7f3a

- and ALWAYS emits, as its final act, one tagged JSON line
  {"__bsds_info__": true, "ok": ..., "metrics"/"title"/"elapsed_s" or "error": ...}.
"""

from __future__ import annotations

import base64
import hmac
import json
from dataclasses import dataclass, field

SENTINEL_BEGIN = "BSDS_RESULT_BEGIN_7f3a"
SENTINEL_END = "BSDS_RESULT_END_7f3a"
INFO_TAG = "__bsds_info__"
MAX_USER_STDOUT = 20_000  # characters kept from user prints
MAX_ERROR_CHARS = 4_000


def gate_ok(supplied: str | None, required: str | None) -> bool:
    """True when access is allowed. An absent/empty required passcode means the
    gate is open (public). Comparison is constant-time."""
    if not required:
        return True
    if not supplied:
        return False
    return hmac.compare_digest(supplied.encode("utf-8"), required.encode("utf-8"))


# The code below runs INSIDE the sandbox via `python -c HARNESS`, with the
# user's code arriving on stdin — never interpolated into this source.
HARNESS = r'''
import base64, io, json, sys, time, traceback

SENTINEL_BEGIN = "BSDS_RESULT_BEGIN_7f3a"
SENTINEL_END = "BSDS_RESULT_END_7f3a"

def emit_info(payload):
    payload["__bsds_info__"] = True
    sys.stdout.flush()
    print(json.dumps(payload))
    sys.stdout.flush()

def main():
    user_code = sys.stdin.read()
    path = "/tmp/user_scenario.py"
    with open(path, "w") as f:
        f.write(user_code)
    t0 = time.time()
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("user_scenario", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["user_scenario"] = mod
        spec.loader.exec_module(mod)
        if not hasattr(mod, "run"):
            raise RuntimeError(
                "Your scenario must define a function run(params) -> RunResult "
                "(see the templates)."
            )
        result = mod.run({})

        from bsds_sims import bsd1
        channels = []
        for name, data in result.channels.items():
            unit = "m" if name in ("r_BN_N", "altitude") else ""
            frame = "inertial" if name.endswith("_N") else ""
            channels.append(bsd1.Channel(name, data, unit=unit, frame=frame, dtype="f32"))
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".bsd1")
        os.close(fd)
        bsd1.write_run(
            tmp,
            scenario="lab",
            run="user",
            title=getattr(result, "title", "Lab run"),
            epoch=result.epoch,
            params={},
            time_s=result.time_s,
            channels=channels,
            bodies=result.bodies,
            metrics=result.metrics,
        )
        with open(tmp, "rb") as f:
            raw = f.read()
        os.unlink(tmp)

        sys.stdout.flush()
        print(SENTINEL_BEGIN)
        print(base64.b64encode(raw).decode())
        print(SENTINEL_END)
        emit_info({
            "ok": True,
            "metrics": {k: v for k, v in result.metrics.items()},
            "title": getattr(result, "title", "Lab run"),
            "n": int(len(result.time_s)),
            "elapsed_s": round(time.time() - t0, 3),
        })
    except BaseException:
        tb = traceback.format_exc()
        emit_info({"ok": False, "error": tb[-4000:], "elapsed_s": round(time.time() - t0, 3)})

main()
'''


@dataclass
class RunOutcome:
    ok: bool
    bsd1_b64: str | None
    info: dict = field(default_factory=dict)
    user_stdout: str = ""
    truncated: bool = False


def parse_sandbox_output(stdout: str, stderr: str) -> RunOutcome:
    lines = stdout.splitlines()

    info: dict | None = None
    b64: str | None = None
    user_lines: list[str] = []

    in_block = False
    block: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == SENTINEL_BEGIN:
            in_block = True
            block = []
            continue
        if stripped == SENTINEL_END:
            in_block = False
            b64 = "".join(block)
            continue
        if in_block:
            block.append(stripped)
            continue
        if stripped.startswith("{"):
            try:
                candidate = json.loads(stripped)
            except json.JSONDecodeError:
                candidate = None
            if isinstance(candidate, dict) and candidate.get(INFO_TAG):
                candidate.pop(INFO_TAG, None)
                info = candidate
                continue
        user_lines.append(line)

    user_stdout = "\n".join(user_lines)
    truncated = len(user_stdout) > MAX_USER_STDOUT
    if truncated:
        user_stdout = user_stdout[:MAX_USER_STDOUT] + "\n…[truncated]"

    if info is None:
        err = f"Run produced no result. stderr: {stderr[-MAX_ERROR_CHARS:]}" if stderr else "Run produced no result."
        return RunOutcome(ok=False, bsd1_b64=None, info={"error": err}, user_stdout=user_stdout, truncated=truncated)

    ok = bool(info.get("ok")) and b64 is not None
    if ok:
        # Validate the base64 decodes and looks like a BSD1 file.
        try:
            raw = base64.b64decode(b64, validate=True)
            if raw[:8] != b"BSDS0001":
                raise ValueError("bad magic")
        except Exception:
            return RunOutcome(
                ok=False,
                bsd1_b64=None,
                info={"error": "Result payload was corrupted in transit."},
                user_stdout=user_stdout,
                truncated=truncated,
            )
        return RunOutcome(ok=True, bsd1_b64=b64, info=info, user_stdout=user_stdout, truncated=truncated)

    return RunOutcome(ok=False, bsd1_b64=None, info=info, user_stdout=user_stdout, truncated=truncated)
