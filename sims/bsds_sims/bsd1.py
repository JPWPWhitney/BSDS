"""BSD1 run-file format: writer and reader.

Layout (spec docs/superpowers/specs/2026-08-18-basilisk-missions-stage1-design.md §4):

    bytes 0..7    magic ASCII "BSDS0001"
    bytes 8..11   uint32 LE header_length
    next          UTF-8 JSON header
    next          binary payload

The payload holds the time array (float64 LE) followed by each channel's
columns stored contiguously, column-major per channel (all samples of
component 0, then component 1, ...). Channel dtype is "f32" (float32 LE) or
"i16" (int16 LE, quantized). Quantization per component:

    offset = min(col)
    scale  = (max(col) - min(col)) / 65534   (scale = 1.0 when the range is 0)
    stored = round((x - offset) / scale) - 32767        # int16
    real   = (stored + 32767) * scale + offset

so round-trip error is bounded by scale/2. The TypeScript decoder in
web/src/bsd1.ts mirrors these formulas exactly — change both or neither.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MAGIC = b"BSDS0001"
_QSPAN = 65534  # int16 span used by quantization (symmetric about -32767..32767)
_QBIAS = 32767


@dataclass
class Channel:
    """One recorded signal: (n, components) float64 array plus metadata."""

    name: str
    data: np.ndarray
    unit: str = ""
    frame: str = ""
    dtype: str = "f32"  # "f32" | "i16"

    def __post_init__(self) -> None:
        arr = np.asarray(self.data, dtype=np.float64)
        if arr.ndim == 1:
            arr = arr[:, None]
        if arr.ndim != 2:
            raise ValueError(f"channel {self.name!r}: data must be 1-D or 2-D")
        if self.dtype not in ("f32", "i16"):
            raise ValueError(f"channel {self.name!r}: dtype must be f32 or i16")
        self.data = arr


@dataclass
class RunData:
    header: dict
    time_s: np.ndarray
    _channels: dict[str, np.ndarray] = field(default_factory=dict)

    def channel(self, name: str) -> np.ndarray | None:
        return self._channels.get(name)


def _quantize(col: np.ndarray) -> tuple[np.ndarray, float, float]:
    lo = float(col.min())
    hi = float(col.max())
    scale = (hi - lo) / _QSPAN if hi > lo else 1.0
    stored = np.round((col - lo) / scale).astype(np.int64) - _QBIAS
    return stored.astype("<i2"), scale, lo


def _dequantize(stored: np.ndarray, scale: float, offset: float) -> np.ndarray:
    return (stored.astype(np.float64) + _QBIAS) * scale + offset


def write_run(
    path: str | Path,
    *,
    scenario: str,
    run: str,
    title: str,
    epoch: str,
    params: dict,
    time_s: np.ndarray,
    channels: list[Channel],
    bodies: list[dict],
    metrics: dict,
) -> int:
    """Write one run file; returns total bytes written."""
    t = np.asarray(time_s, dtype=np.float64)
    if t.ndim != 1 or len(t) < 2:
        raise ValueError("time_s must be a 1-D array with at least 2 samples")
    if np.any(np.diff(t) <= 0):
        raise ValueError("time_s must be strictly increasing")
    n = len(t)

    payload = bytearray()
    payload += t.astype("<f8").tobytes()
    time_info = {"dtype": "f64", "unit": "s", "byte_offset": 0, "byte_length": n * 8}

    channel_infos = []
    for ch in channels:
        if ch.data.shape[0] != n:
            raise ValueError(f"channel {ch.name!r}: {ch.data.shape[0]} samples, expected {n}")
        comps = ch.data.shape[1]
        info: dict = {
            "name": ch.name,
            "components": comps,
            "unit": ch.unit,
            "frame": ch.frame,
            "dtype": ch.dtype,
            "byte_offset": len(payload),
        }
        if ch.dtype == "f32":
            for c in range(comps):
                payload += ch.data[:, c].astype("<f4").tobytes()
            info["byte_length"] = n * 4 * comps
        else:
            scales, offsets = [], []
            for c in range(comps):
                stored, scale, offset = _quantize(ch.data[:, c])
                payload += stored.tobytes()
                scales.append(scale)
                offsets.append(offset)
            info["byte_length"] = n * 2 * comps
            info["scale"] = scales
            info["offset"] = offsets
        channel_infos.append(info)

    header = {
        "schema": 1,
        "scenario": scenario,
        "run": run,
        "title": title,
        "epoch": epoch,
        "params": params,
        "n": n,
        "bodies": bodies,
        "time": time_info,
        "channels": channel_infos,
        "metrics": metrics,
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")

    out = Path(path)
    with out.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", len(header_bytes)))
        f.write(header_bytes)
        f.write(bytes(payload))
    return 8 + 4 + len(header_bytes) + len(payload)


def read_run(path: str | Path) -> RunData:
    raw = Path(path).read_bytes()
    if len(raw) < 12 or raw[:8] != MAGIC:
        raise ValueError("not a BSD1 file (bad magic)")
    (hlen,) = struct.unpack("<I", raw[8:12])
    if len(raw) < 12 + hlen:
        raise ValueError("truncated BSD1 file (header)")
    header = json.loads(raw[12 : 12 + hlen].decode("utf-8"))
    payload = memoryview(raw)[12 + hlen :]

    def _view(offset: int, length: int) -> memoryview:
        if offset + length > len(payload):
            raise ValueError("truncated BSD1 file (payload)")
        return payload[offset : offset + length]

    tinfo = header["time"]
    n = header["n"]
    time_s = np.frombuffer(_view(tinfo["byte_offset"], tinfo["byte_length"]), dtype="<f8").copy()
    if len(time_s) != n:
        raise ValueError("time length mismatch")

    channels: dict[str, np.ndarray] = {}
    for ch in header["channels"]:
        comps = ch["components"]
        buf = _view(ch["byte_offset"], ch["byte_length"])
        out = np.empty((n, comps), dtype=np.float64)
        if ch["dtype"] == "f32":
            flat = np.frombuffer(buf, dtype="<f4")
            for c in range(comps):
                out[:, c] = flat[c * n : (c + 1) * n]
        elif ch["dtype"] == "i16":
            flat = np.frombuffer(buf, dtype="<i2")
            for c in range(comps):
                out[:, c] = _dequantize(flat[c * n : (c + 1) * n], ch["scale"][c], ch["offset"][c])
        else:
            continue  # unknown dtype: ignore channel (forward compatibility)
        channels[ch["name"]] = out

    return RunData(header=header, time_s=time_s, _channels=channels)
