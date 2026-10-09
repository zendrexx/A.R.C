"""Versioned, human-readable local storage; no serialized Python models."""

import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from arc.contracts import ACTIONS, FEATURE_LENGTH, GestureDefinition

PROFILE_VERSION = 1


@dataclass
class Profile:
    gestures: list[GestureDefinition] = field(default_factory=list)
    workshop_index: int = 0
    completed_steps: list[int] = field(default_factory=list)


def load_profile(path: Path) -> Profile:
    if not path.exists():
        return Profile()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != PROFILE_VERSION:
        raise ValueError("Unsupported profile version")
    gestures = []
    ids = set()
    for item in raw.get("gestures", []):
        gesture_id = item["gesture_id"]
        name = item["name"]
        action = item["action"]
        samples = item["samples"]
        if (not isinstance(gesture_id, str) or not gesture_id or gesture_id in ids
                or not isinstance(name, str) or not name.strip() or action not in ACTIONS
                or not isinstance(samples, list) or not samples):
            raise ValueError("Invalid saved gesture")
        ids.add(gesture_id)
        for sample in samples:
            if (not isinstance(sample, list) or len(sample) != FEATURE_LENGTH
                    or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                           for value in sample)):
                raise ValueError("Invalid saved gesture sample")
        gestures.append(GestureDefinition(gesture_id, name, action, samples))
    index = raw.get("workshop_index", 0)
    completed = raw.get("completed_steps", [])
    if (not isinstance(index, int) or not 0 <= index < 5
            or not isinstance(completed, list)
            or any(not isinstance(step, int) or not 0 <= step < 5 for step in completed)):
        raise ValueError("Invalid workshop progress")
    return Profile(gestures, index, sorted(set(completed)))


def save_profile(path: Path, profile: Profile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PROFILE_VERSION,
        "gestures": [
            {"gesture_id": gesture.gesture_id, "name": gesture.name,
             "action": gesture.action, "samples": gesture.samples}
            for gesture in profile.gestures
        ],
        "workshop_index": profile.workshop_index,
        "completed_steps": profile.completed_steps,
    }
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".profile-", suffix=".json", delete=False) as temp:
            temp_name = temp.name
            json.dump(payload, temp, indent=2, allow_nan=False)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)

