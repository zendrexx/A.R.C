"""On-device MediaPipe tracking, normalized features, and KNN recognition."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import cv2
import mediapipe as mp
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from arc.contracts import FEATURE_LENGTH, FrameResult, GestureDefinition, Prediction
from arc.gate import ActivationGate


def normalize_landmarks(landmarks: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Translate to wrist, scale by palm length, rotate palm toward +y."""
    if len(landmarks) != 21 or any(len(point) != 3 for point in landmarks):
        raise ValueError("Expected 21 landmarks with x, y, z coordinates")
    points = np.asarray(landmarks, dtype=np.float64)
    if not np.isfinite(points).all():
        raise ValueError("Landmarks must be finite")
    origin = points[0]
    palm = points[9, :2] - origin[:2]
    scale = float(np.linalg.norm(palm))
    if scale < 1e-5:
        raise ValueError("Hand landmarks are too small to normalize")
    forward = palm / scale
    right = np.array([forward[1], -forward[0]])
    shifted = points - origin
    xy = np.column_stack((shifted[:, :2] @ right, shifted[:, :2] @ forward)) / scale
    z = shifted[:, 2:3] / scale
    return tuple(float(value) for value in np.column_stack((xy, z)).ravel())


class GestureClassifier:
    """KNN chooses a candidate; absolute distance and class margin reject uncertainty."""

    def __init__(self, max_distance: float = 0.18, min_margin: float = 0.035):
        self.max_distance = max_distance
        self.min_margin = min_margin
        self._model: KNeighborsClassifier | None = None
        self._features: np.ndarray | None = None
        self._labels: np.ndarray | None = None

    def fit(self, gestures: Sequence[GestureDefinition]) -> None:
        features: list[list[float]] = []
        labels: list[str] = []
        for gesture in gestures:
            for sample in gesture.samples:
                if len(sample) != FEATURE_LENGTH or not np.isfinite(sample).all():
                    raise ValueError(f"Invalid training sample for {gesture.name}")
                features.append(sample)
                labels.append(gesture.gesture_id)
        if not features:
            self._model = self._features = self._labels = None
            return
        self._features = np.asarray(features, dtype=np.float64)
        self._labels = np.asarray(labels)
        self._model = KNeighborsClassifier(n_neighbors=min(3, len(features)), weights="distance")
        self._model.fit(self._features, self._labels)

    def predict(self, features: Sequence[float]) -> Prediction:
        if self._model is None or self._features is None or self._labels is None:
            return Prediction(reason="no trained gestures")
        if len(features) != FEATURE_LENGTH or not np.isfinite(features).all():
            return Prediction(reason="invalid hand features")
        query = np.asarray(features, dtype=np.float64).reshape(1, -1)
        candidate = str(self._model.predict(query)[0])
        distances = np.linalg.norm(self._features - query, axis=1) / math.sqrt(FEATURE_LENGTH)
        class_distances = {
            label: float(np.min(distances[self._labels == label]))
            for label in np.unique(self._labels)
        }
        nearest = class_distances[candidate]
        others = [distance for label, distance in class_distances.items() if label != candidate]
        margin = min(others) - nearest if others else None
        if nearest > self.max_distance:
            return Prediction(distance=nearest, margin=margin, reason="unfamiliar pose")
        if margin is not None and margin < self.min_margin:
            return Prediction(distance=nearest, margin=margin, reason="ambiguous pose")
        return Prediction(candidate, nearest, margin, "recognized")


class GestureEngine:
    def __init__(self, model_path: Path):
        if not model_path.is_file():
            raise FileNotFoundError(f"Missing MediaPipe model: {model_path}")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._tracker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._classifier = GestureClassifier()
        self._last_timestamp = -1

    def fit(self, gestures: Sequence[GestureDefinition]) -> None:
        self._classifier.fit(gestures)

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> FrameResult:
        if timestamp_ms <= self._last_timestamp:
            timestamp_ms = self._last_timestamp + 1
        self._last_timestamp = timestamp_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._tracker.detect_for_video(image, timestamp_ms)
        if not result.hand_landmarks:
            return FrameResult(prediction=Prediction(reason="no hand"))
        points = tuple((float(p.x), float(p.y), float(p.z)) for p in result.hand_landmarks[0])
        try:
            features = normalize_landmarks(points)
        except ValueError:
            return FrameResult(landmarks=points, prediction=Prediction(reason="invalid hand"))
        return FrameResult(points, features, self._classifier.predict(features))

    def close(self) -> None:
        self._tracker.close()
