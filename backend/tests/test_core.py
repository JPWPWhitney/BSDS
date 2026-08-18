import base64
import json

import numpy as np
import pytest

from bsds_backend import core
from bsds_sims import bsd1


def _bsd1_bytes(tmp_path) -> bytes:
    t = np.linspace(0, 100, 20)
    path = tmp_path / "r.bsd1"
    bsd1.write_run(
        path,
        scenario="s",
        run="r",
        title="t",
        epoch="2026-01-01T00:00:00Z",
        params={},
        time_s=t,
        channels=[bsd1.Channel("r_BN_N", np.ones((20, 3)))],
        bodies=[{"name": "earth", "mu": 1.0, "radius_km": 1.0}],
        metrics={"m": 1.0},
    )
    return path.read_bytes()


class TestGate:
    def test_no_required_passcode_is_public(self):
        assert core.gate_ok(None, None)
        assert core.gate_ok("anything", None)
        assert core.gate_ok(None, "")
        assert core.gate_ok("x", "")

    def test_required_passcode_enforced(self):
        assert core.gate_ok("secret", "secret")
        assert not core.gate_ok("wrong", "secret")
        assert not core.gate_ok(None, "secret")
        assert not core.gate_ok("", "secret")


class TestParseSandboxOutput:
    def test_happy_path(self, tmp_path):
        raw = _bsd1_bytes(tmp_path)
        b64 = base64.b64encode(raw).decode()
        info = {"ok": True, "metrics": {"m": 1.0}, "title": "t", "elapsed_s": 0.02}
        stdout = "\n".join([
            "user print line",
            core.SENTINEL_BEGIN,
            b64,
            core.SENTINEL_END,
            json.dumps({"__bsds_info__": True, **info}),
        ])
        out = core.parse_sandbox_output(stdout, "")
        assert out.ok
        assert base64.b64decode(out.bsd1_b64) == raw
        assert out.info["metrics"] == {"m": 1.0}
        assert "user print line" in out.user_stdout
        assert not out.truncated

    def test_user_error_path(self):
        info = {"ok": False, "error": "Traceback ... ZeroDivisionError"}
        stdout = "\n".join(["partial output", json.dumps({"__bsds_info__": True, **info})])
        # Error path uses the tagged JSON line, no sentinels
        out = core.parse_sandbox_output(stdout, "")
        assert not out.ok
        assert "ZeroDivisionError" in out.info["error"]
        assert out.bsd1_b64 is None
        assert "partial output" in out.user_stdout

    def test_garbage_output(self):
        out = core.parse_sandbox_output("segfault noise", "stderr noise")
        assert not out.ok
        assert out.bsd1_b64 is None
        assert "stderr noise" in out.info["error"]

    def test_oversize_stdout_truncated(self, tmp_path):
        raw = _bsd1_bytes(tmp_path)
        b64 = base64.b64encode(raw).decode()
        big = "x" * (core.MAX_USER_STDOUT + 5000)
        stdout = "\n".join([
            big,
            core.SENTINEL_BEGIN,
            b64,
            core.SENTINEL_END,
            json.dumps({"__bsds_info__": True, "ok": True, "metrics": {}, "title": "t", "elapsed_s": 0.1}),
        ])
        out = core.parse_sandbox_output(stdout, "")
        assert out.ok
        assert out.truncated
        assert len(out.user_stdout) <= core.MAX_USER_STDOUT + 100


class TestHarness:
    def test_harness_is_self_contained_python(self):
        compile(core.HARNESS, "<harness>", "exec")

    def test_harness_reads_stdin_not_interpolated(self):
        # The harness must take user code via stdin, never via string formatting.
        assert "sys.stdin" in core.HARNESS
        assert "{code}" not in core.HARNESS
        assert "%s" not in core.HARNESS

    @pytest.mark.slow
    def test_harness_end_to_end_subprocess(self, tmp_path):
        """Run the actual harness in a subprocess with a stub scenario (no Basilisk),
        exactly as the sandbox would."""
        import subprocess
        import sys

        user_code = (
            "import numpy as np\n"
            "from bsds_sims.recording import RunResult\n"
            "def run(params):\n"
            "    t = np.linspace(0, 10, 30)\n"
            "    return RunResult(time_s=t, channels={'r_BN_N': np.ones((30, 3))},\n"
            "                     bodies=[{'name': 'earth', 'mu': 1.0, 'radius_km': 1.0}],\n"
            "                     metrics={'z': 2.0}, epoch='2026-01-01T00:00:00Z', title='stub')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", core.HARNESS],
            input=user_code.encode(),
            capture_output=True,
            timeout=60,
        )
        out = core.parse_sandbox_output(proc.stdout.decode(), proc.stderr.decode())
        assert out.ok, out.info
        raw = base64.b64decode(out.bsd1_b64)
        assert raw[:8] == b"BSDS0001"
        assert out.info["metrics"] == {"z": 2.0}
