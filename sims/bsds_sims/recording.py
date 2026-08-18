"""Shared scenario plumbing: RunResult container and recorder helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Basilisk.utilities import macros

EARTH_BODY = {"name": "earth", "mu": 3.986004415e14, "radius_km": 6378.1366}


@dataclass
class RunResult:
    """Everything a scenario produces for one run, in plain numpy."""

    time_s: np.ndarray
    channels: dict[str, np.ndarray]
    bodies: list[dict]
    metrics: dict
    epoch: str
    title: str


def attach_sc_recorder(scSim, task_name: str, scObject, min_update_s: float):
    """Attach a spacecraft state recorder to a task and return it."""
    rec = scObject.scStateOutMsg.recorder(macros.sec2nano(min_update_s))
    scSim.AddModelToTask(task_name, rec)
    return rec


def pull_sc_channels(rec) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Extract time base and the standard spacecraft channels from a recorder."""
    t = np.asarray(rec.times(), dtype=np.float64) * macros.NANO2SEC
    channels = {
        "r_BN_N": np.asarray(rec.r_BN_N, dtype=np.float64),
        "v_BN_N": np.asarray(rec.v_BN_N, dtype=np.float64),
        "sigma_BN": np.asarray(rec.sigma_BN, dtype=np.float64),
        "omega_BN_B": np.asarray(rec.omega_BN_B, dtype=np.float64),
    }
    return t, channels


def dedupe_time(t: np.ndarray, channels: dict[str, np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Drop repeated timestamps (recorders repeat samples across ExecuteSimulation
    resumes), keeping the last occurrence, so time is strictly increasing."""
    keep = np.ones(len(t), dtype=bool)
    keep[:-1] = np.diff(t) > 0
    return t[keep], {k: v[keep] for k, v in channels.items()}
