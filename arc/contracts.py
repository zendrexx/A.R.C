"""Stable boundary between the vision and desktop development tracks.

Change this file only with both developers' agreement. Profile schema version 1
stores the feature vectors produced by this contract.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence, Tuple

FEATURE_LENGTH = 63  # 21 landmarks x (x, y, z), wrist/palm normalized
ACTIONS = ("next_step", "previous_step", "complete_step", "replay_step")


@dataclass
class GestureDefinition:
    gesture_id: str
    name: str
    action: str
    samples: list[list[float]] = field(default_factory=list)


@dataclass(frozen=True)
class Prediction:
    gesture_id: Optional[str] = None
    distance: Optional[float] = None  # nearest sample RMS over 63 features
    margin: Optional[float] = None  # runner-up distance minus winner distance
    reason: str = "unknown"


@dataclass(frozen=True)
class FrameResult:
    landmarks: Tuple[Tuple[float, float, float], ...] = ()  # 21 image-normalized points
    features: Optional[Tuple[float, ...]] = None
    prediction: Prediction = Prediction()


class RecognitionEngine(Protocol):
    def fit(self, gestures: Sequence[GestureDefinition]) -> None: ...

    def process_frame(self, frame_bgr: Any, timestamp_ms: int) -> FrameResult: ...

    def close(self) -> None: ...

