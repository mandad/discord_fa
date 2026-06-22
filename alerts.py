"""Kp >= threshold alert dedupe.

State is a JSON map {time_tag: kp_value_already_alerted}. A predicted window fires once;
it re-fires only if its predicted Kp rises above what we last pinged for that window.
"""
from __future__ import annotations

import json
from pathlib import Path

import swpc


def load_state(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2))


def check_kp_alert(rows: list[dict], state: dict, threshold: float) -> list[dict]:
    """Return predicted windows newly at/above threshold; mutate `state` to record them.

    Caller is responsible for persisting `state` (save_state) after acting on the result.
    """
    new = []
    for r in swpc.predicted_ge(rows, threshold):
        prev = state.get(r["time_tag"])
        if prev is None or r["kp"] > prev:
            new.append(r)
            state[r["time_tag"]] = r["kp"]
    return new
