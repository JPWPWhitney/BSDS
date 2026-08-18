import json
import struct

import numpy as np
import pytest

from bsds_sims import bsd1


def _sample_run(tmp_path, channels, n=500):
    t = np.linspace(0.0, 5400.0, n)
    path = tmp_path / "run.bsd1"
    nbytes = bsd1.write_run(
        path,
        scenario="test_scn",
        run="run01",
        title="Test run",
        epoch="2026-01-01T00:00:00Z",
        params={"x": 1.5},
        time_s=t,
        channels=channels,
        bodies=[{"name": "earth", "mu": 3.986004415e14, "radius_km": 6378.1366}],
        metrics={"score": 42.0},
    )
    assert nbytes == path.stat().st_size
    return path, t


def test_f32_round_trip_exact(tmp_path):
    n = 500
    rng = np.random.default_rng(1)
    data = rng.normal(scale=7.0e6, size=(n, 3)).astype(np.float32).astype(np.float64)
    path, t = _sample_run(tmp_path, [bsd1.Channel("r_BN_N", data, unit="m", frame="inertial", dtype="f32")], n)

    run = bsd1.read_run(path)
    np.testing.assert_array_equal(run.time_s, t)
    back = run.channel("r_BN_N")
    np.testing.assert_array_equal(back, data)  # f32-representable values survive exactly
    assert run.header["scenario"] == "test_scn"
    assert run.header["metrics"]["score"] == 42.0


def test_i16_round_trip_within_bound(tmp_path):
    n = 800
    rng = np.random.default_rng(2)
    data = np.cumsum(rng.normal(size=(n, 3)), axis=0) * 123.4 + 5.0e5
    path, _ = _sample_run(tmp_path, [bsd1.Channel("sigma_BN", data, dtype="i16")], n)

    run = bsd1.read_run(path)
    back = run.channel("sigma_BN")
    for c in range(3):
        col = data[:, c]
        scale = (col.max() - col.min()) / 65534.0
        assert np.max(np.abs(back[:, c] - col)) <= scale / 2 + 1e-9


def test_i16_constant_channel_exact(tmp_path):
    n = 100
    data = np.full((n, 2), 3.25)
    path, _ = _sample_run(tmp_path, [bsd1.Channel("flat", data, dtype="i16")], n)
    back = bsd1.read_run(path).channel("flat")
    np.testing.assert_allclose(back, data, atol=1e-12)


def test_framing_and_offsets(tmp_path):
    n = 64
    data = np.arange(n * 3, dtype=np.float64).reshape(n, 3)
    path, _ = _sample_run(tmp_path, [bsd1.Channel("r_BN_N", data)], n)

    raw = path.read_bytes()
    assert raw[:8] == b"BSDS0001"
    (hlen,) = struct.unpack("<I", raw[8:12])
    header = json.loads(raw[12 : 12 + hlen].decode("utf-8"))
    assert header["schema"] == 1
    payload_len = len(raw) - 12 - hlen
    tinfo = header["time"]
    assert tinfo["dtype"] == "f64" and tinfo["byte_offset"] == 0
    assert tinfo["byte_length"] == n * 8
    for ch in header["channels"]:
        assert ch["byte_offset"] + ch["byte_length"] <= payload_len


def test_truncated_file_raises(tmp_path):
    n = 64
    data = np.zeros((n, 3))
    path, _ = _sample_run(tmp_path, [bsd1.Channel("r_BN_N", data)], n)
    raw = path.read_bytes()
    bad = tmp_path / "bad.bsd1"
    bad.write_bytes(raw[: len(raw) - 10])
    with pytest.raises(ValueError):
        bsd1.read_run(bad)


def test_unknown_header_keys_survive(tmp_path):
    n = 32
    data = np.ones((n, 1))
    path, _ = _sample_run(tmp_path, [bsd1.Channel("x", data)], n)
    raw = bytearray(path.read_bytes())
    (hlen,) = struct.unpack("<I", raw[8:12])
    header = json.loads(bytes(raw[12 : 12 + hlen]).decode("utf-8"))
    header["future_field"] = {"v": 2}
    new_header = json.dumps(header).encode("utf-8")
    out = bytearray()
    out += raw[:8]
    out += struct.pack("<I", len(new_header))
    out += new_header
    out += raw[12 + hlen :]
    p2 = tmp_path / "fwd.bsd1"
    p2.write_bytes(bytes(out))
    run = bsd1.read_run(p2)
    assert run.header["future_field"] == {"v": 2}
    np.testing.assert_array_equal(run.channel("x"), data)


def test_missing_channel_returns_none(tmp_path):
    n = 16
    path, _ = _sample_run(tmp_path, [bsd1.Channel("x", np.ones((n, 1)))], n)
    assert bsd1.read_run(path).channel("nope") is None
