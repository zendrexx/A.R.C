"""Time-based gesture activation, independent of camera and UI libraries."""

from __future__ import annotations

import math

from arc.contracts import Prediction


class ActivationGate:
    """One activation per held pose, with deliberate release and cooldown."""

    def __init__(self, hold_seconds: float = 0.65, release_seconds: float = 0.35,
                 cooldown_seconds: float = 1.0):
        self.hold_seconds = hold_seconds
        self.release_seconds = release_seconds
        self.cooldown_seconds = cooldown_seconds
        self.reset()

    def reset(self) -> None:
        self._candidate: str | None = None
        self._candidate_since = 0.0
        self._latched: str | None = None
        self._release_since: float | None = None
        self._last_trigger = -math.inf

    def update(self, prediction: Prediction, now: float) -> str | None:
        gesture_id = prediction.gesture_id
        if self._latched is not None:
            if gesture_id == self._latched:
                self._release_since = None
            elif self._release_since is None:
                self._release_since = now
            elif now - self._release_since >= self.release_seconds:
                self._latched = None
                self._release_since = None
            self._candidate = None
            return None
        if gesture_id is None:
            self._candidate = None
            return None
        if gesture_id != self._candidate:
            self._candidate = gesture_id
            self._candidate_since = now
            return None
        if now - self._candidate_since < self.hold_seconds:
            return None
        if now - self._last_trigger < self.cooldown_seconds:
            return None
        self._last_trigger = now
        self._latched = gesture_id
        self._candidate = None
        return gesture_id
