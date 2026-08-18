#!/usr/bin/env python3
"""Compare two BSK_RESULT_JSON captures (wasm vs native).

Usage: compare_results.py wasm.json native.json [--kind utils|orbit]
Prints a relative-error table; exits 1 if max relative error > --tol.
"""

import argparse
import json
import math
import sys


def load(path):
    text = open(path).read()
    for line in text.splitlines():
        if line.startswith("BSK_RESULT_JSON "):
            return json.loads(line[len("BSK_RESULT_JSON "):])
    return json.loads(text)  # allow bare json


def rel(a, b):
    denom = max(abs(a), abs(b), 1e-300)
    return abs(a - b) / denom


def vec_rel(va, vb):
    na = math.sqrt(sum(x * x for x in va))
    diff = math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb)))
    return diff / max(na, 1e-300)


ANGLE_KEYS = {"i", "Omega", "omega", "f"}


def ang_rel(a, b):
    """Relative error for angles: wrapped difference over the 2*pi scale
    (0 and 2*pi-eps are the same angle on different branches)."""
    d = abs(a - b) % (2 * math.pi)
    d = min(d, 2 * math.pi - d)
    return d / (2 * math.pi)


def cmp_utils(w, n):
    rows = []
    rows.append(("elem2rv r vector", vec_rel(w["r"], n["r"])))
    rows.append(("elem2rv v vector", vec_rel(w["v"], n["v"])))
    for k in w["roundtrip"]:
        f = ang_rel if k in ANGLE_KEYS else rel
        rows.append((f"rv2elem.{k}", f(w["roundtrip"][k], n["roundtrip"][k])))
    rows.append(("MRP2C dcm", vec_rel(w["dcm9"], n["dcm9"])))
    rows.append(("C2MRP roundtrip", vec_rel(w["sigma_rt"], n["sigma_rt"])))
    rows.append(("|r x v|", rel(w["hmag"], n["hmag"])))
    return rows


def cmp_orbit(w, n):
    rows = []
    tw, tn = w["t"], n["t"]
    if tw != tn:
        rows.append(("time grids identical", 1.0))
        print(f"  !! time grids differ: wasm {len(tw)} pts vs native {len(tn)} pts",
              file=sys.stderr)
        common = min(len(tw), len(tn))
    else:
        common = len(tw)
    rows.append(("samples", 0.0))
    rows.append(("initial r vector", vec_rel(w["rN0"], n["rN0"])))
    rows.append(("initial v vector", vec_rel(w["vN0"], n["vN0"])))
    max_r = max(vec_rel(w["r"][i], n["r"][i]) for i in range(common))
    max_v = max(vec_rel(w["v"][i], n["v"][i]) for i in range(common))
    end_r = vec_rel(w["r"][common - 1], n["r"][common - 1])
    end_v = vec_rel(w["v"][common - 1], n["v"][common - 1])
    rows.append((f"max |Δr|/|r| over {common} samples", max_r))
    rows.append((f"max |Δv|/|v| over {common} samples", max_v))
    rows.append(("final-sample |Δr|/|r|", end_r))
    rows.append(("final-sample |Δv|/|v|", end_v))
    return rows


def cmp_drag(w, n):
    rows = []
    tw, tn = w["t"], n["t"]
    if tw != tn:
        rows.append(("time grids identical", 1.0))
        print(f"  !! time grids differ: wasm {len(tw)} pts vs native {len(tn)} pts",
              file=sys.stderr)
        common = min(len(tw), len(tn))
    else:
        common = len(tw)
    rows.append(("samples", 0.0))
    rows.append(("deorbit_time_h",
                 rel(w["metrics"]["deorbit_time_h"], n["metrics"]["deorbit_time_h"])))
    rows.append(("capped flag equal",
                 0.0 if w["metrics"]["capped"] == n["metrics"]["capped"] else 1.0))
    rows.append(("final_alt_km",
                 rel(w["metrics"]["final_alt_km"], n["metrics"]["final_alt_km"])))
    max_r = max(vec_rel(w["r"][i], n["r"][i]) for i in range(common))
    max_v = max(vec_rel(w["v"][i], n["v"][i]) for i in range(common))
    rows.append((f"max |Δr|/|r| over {common} samples", max_r))
    rows.append((f"max |Δv|/|v| over {common} samples", max_v))
    rows.append(("final-sample |Δr|/|r|", vec_rel(w["r"][common - 1], n["r"][common - 1])))
    rows.append(("final-sample |Δv|/|v|", vec_rel(w["v"][common - 1], n["v"][common - 1])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wasm")
    ap.add_argument("native")
    ap.add_argument("--kind", choices=["utils", "orbit", "drag"], default="orbit")
    ap.add_argument("--tol", type=float, default=1e-9)
    args = ap.parse_args()

    w, n = load(args.wasm), load(args.native)
    rows = {"utils": cmp_utils, "orbit": cmp_orbit, "drag": cmp_drag}[args.kind](w, n)

    width = max(len(r[0]) for r in rows) + 2
    print(f"{'quantity':<{width}} relative error")
    print("-" * (width + 16))
    worst = 0.0
    for name, err in rows:
        if name == "samples":
            continue
        worst = max(worst, err)
        print(f"{name:<{width}} {err:.3e}")
    print("-" * (width + 16))
    verdict = "PASS" if worst <= args.tol else "FAIL"
    print(f"worst relative error: {worst:.3e}  (tol {args.tol:.1e})  -> {verdict}")
    sys.exit(0 if worst <= args.tol else 1)


if __name__ == "__main__":
    main()
