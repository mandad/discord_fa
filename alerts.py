"""Kp >= threshold alert dedupe.

State is a JSON map {time_tag: kp_value_already_alerted}. A predicted window fires once;
it re-fires only if its predicted Kp rises above what we last pinged for that window.
"""
from __future__ import annotations

import json
from pathlib import Path

import swpc


_DAILY_KEY = "_last_daily_date"  # reserved key; not a Kp time_tag, so it never collides


def load_state(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2))


def daily_already_posted(path: Path, date_key: str) -> bool:
    """True if the once-daily post already ran for `date_key` (a local YYYY-MM-DD)."""
    return load_state(path).get(_DAILY_KEY) == date_key


def mark_daily_posted(path: Path, date_key: str) -> None:
    """Record that the daily post ran for `date_key`, preserving the Kp-alert state."""
    state = load_state(path)
    state[_DAILY_KEY] = date_key
    save_state(path, state)


def check_kp_alert(rows: list[dict], state: dict, threshold: float, keep=None) -> list[dict]:
    """Return predicted windows newly at/above threshold; mutate `state` to record them.

    `keep`, if given, is a predicate `keep(row) -> bool`; rows it rejects (e.g. windows that
    fall in daylight at the ship) are skipped and not recorded, so they can be reconsidered
    later. Caller persists `state` (save_state) after acting on the result.
    """
    new = []
    for r in swpc.predicted_ge(rows, threshold):
        if keep is not None and not keep(r):
            continue
        prev = state.get(r["time_tag"])
        if prev is None or r["kp"] > prev:
            new.append(r)
            state[r["time_tag"]] = r["kp"]
    return new
