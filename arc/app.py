"""Runnable PySide6 proof of concept: teach gestures and control Workshop Mode."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from uuid import uuid4

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QTabWidget, QVBoxLayout, QWidget,
)

from arc.contracts import ACTIONS, FrameResult, GestureDefinition
from arc.engine import GestureEngine
from arc.gate import ActivationGate
from arc.profile import Profile, load_profile, save_profile
from arc.workshop import STEPS, Workshop

ROOT = Path(__file__).resolve().parents[1]
ACTION_LABELS = {
    "next_step": "Next step",
    "previous_step": "Previous step",
    "complete_step": "Mark complete",
    "replay_step": "Replay instruction",
}
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


class ArcWindow(QMainWindow):
    def __init__(self, model_path: Path, profile_path: Path, camera_index: int):
        super().__init__()
        self.profile_path = profile_path
        self.profile: Profile = load_profile(profile_path)
        self.workshop = Workshop(self.profile.workshop_index, set(self.profile.completed_steps))
        self.engine = GestureEngine(model_path)
        self.engine.fit(self.profile.gestures)
        self.gate = ActivationGate()
        backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
        self.camera = cv2.VideoCapture(camera_index, backend)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._capture_name = ""
        self._capture_action = ""
        self._capture_samples: list[list[float]] = []
        self._capture_last_sample = 0.0
        self._capture_deadline = 0.0
        self._build_ui()
        self._refresh_gestures()
        self._refresh_workshop()
        self.setWindowTitle("A.R.C — Your hands. Your gestures. Your control.")
        self.resize(1200, 760)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._on_frame)
        if self.camera.isOpened():
            self.timer.start()
            self._set_status("Camera ready. Record a gesture in Studio, then use it in Workshop.")
        else:
            self.preview.setText("Camera unavailable\nCheck macOS camera permission and camera index.")
            self._set_status("Camera unavailable. Manual Workshop controls still work.")

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 20, 26, 22)
        outer.setSpacing(16)

        title = QLabel("A.R.C")
        title.setObjectName("title")
        subtitle = QLabel("YOUR HANDS. YOUR GESTURES. YOUR CONTROL.")
        subtitle.setObjectName("subtitle")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)

        camera_card = QFrame()
        camera_card.setObjectName("card")
        camera_layout = QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(18, 18, 18, 18)
        camera_layout.setSpacing(12)
        camera_header = QLabel("LIVE CAMERA  •  ON DEVICE")
        camera_header.setObjectName("section")
        camera_layout.addWidget(camera_header)
        self.preview = QLabel("Starting camera…")
        self.preview.setObjectName("preview")
        self.preview.setMinimumSize(560, 420)
        self.preview.setAlignment(Qt.AlignCenter)
        camera_layout.addWidget(self.preview, 1)
        self.recognition = QLabel("No gesture yet")
        self.recognition.setObjectName("recognition")
        camera_layout.addWidget(self.recognition)
        hint = QLabel("Hold a trained pose for about 0.65 seconds. Lower your hand before repeating it.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        camera_layout.addWidget(hint)
        body.addWidget(camera_card, 3)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_studio(), "Gesture Studio")
        self.tabs.addTab(self._build_workshop(), "Workshop")
        self.tabs.currentChanged.connect(lambda _index: self.gate.reset())
        body.addWidget(self.tabs, 2)

        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

    def _build_studio(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(12)
        heading = QLabel("Teach a new gesture")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        help_text = QLabel("Choose a distinct static hand pose. Keep it in view while 16 samples are collected.")
        help_text.setWordWrap(True)
        help_text.setObjectName("muted")
        layout.addWidget(help_text)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Gesture name, e.g. Open palm")
        layout.addWidget(self.name_input)
        self.action_input = QComboBox()
        for action in ACTIONS:
            self.action_input.addItem(ACTION_LABELS[action], action)
        layout.addWidget(self.action_input)
        self.record_button = QPushButton("Record gesture")
        self.record_button.setObjectName("primary")
        self.record_button.clicked.connect(self._start_capture)
        layout.addWidget(self.record_button)
        self.capture_feedback = QLabel("Ready to record")
        self.capture_feedback.setObjectName("muted")
        layout.addWidget(self.capture_feedback)
        layout.addSpacing(14)
        manage_heading = QLabel("Saved gestures")
        manage_heading.setObjectName("heading")
        layout.addWidget(manage_heading)
        self.gesture_list = QListWidget()
        self.gesture_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.gesture_list, 1)
        self.edit_action = QComboBox()
        for action in ACTIONS:
            self.edit_action.addItem(ACTION_LABELS[action], action)
        layout.addWidget(self.edit_action)
        row = QHBoxLayout()
        assign_button = QPushButton("Assign action")
        assign_button.clicked.connect(self._assign_action)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_gesture)
        row.addWidget(assign_button)
        row.addWidget(delete_button)
        layout.addLayout(row)
        return tab

    def _build_workshop(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(16)
        heading = QLabel("Workshop Mode")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        description = QLabel("Build a simple desk stand, one instruction at a time.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.step_counter = QLabel()
        self.step_counter.setObjectName("section")
        layout.addWidget(self.step_counter)
        self.step_title = QLabel()
        self.step_title.setObjectName("stepTitle")
        self.step_title.setWordWrap(True)
        layout.addWidget(self.step_title)
        self.step_body = QLabel()
        self.step_body.setObjectName("stepBody")
        self.step_body.setWordWrap(True)
        self.step_body.setAlignment(Qt.AlignTop)
        layout.addWidget(self.step_body, 1)
        self.step_done = QLabel()
        self.step_done.setObjectName("muted")
        layout.addWidget(self.step_done)
        self.progress = QProgressBar()
        self.progress.setRange(0, len(STEPS))
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        for label, action in (("Previous", "previous_step"), ("Next", "next_step")):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=action: self._run_action(value))
            row.addWidget(button)
        layout.addLayout(row)
        complete = QPushButton("Mark step complete")
        complete.setObjectName("primary")
        complete.clicked.connect(lambda _checked=False: self._run_action("complete_step"))
        layout.addWidget(complete)
        replay = QPushButton("Replay instruction")
        replay.clicked.connect(lambda _checked=False: self._run_action("replay_step"))
        layout.addWidget(replay)
        return tab

    def _on_frame(self) -> None:
        ok, frame = self.camera.read()
        if not ok:
            self.timer.stop()
            self._set_status("Camera stream stopped. Restart the app after checking the camera.")
            return
        frame = cv2.flip(frame, 1)
        now = time.monotonic()
        try:
            result = self.engine.process_frame(frame, time.monotonic_ns() // 1_000_000)
        except (RuntimeError, ValueError) as error:
            self.timer.stop()
            self._set_status(f"Hand tracking stopped: {error}")
            return
        self._show_frame(frame, result)
        if self._capture_name:
            self._collect_sample(result, now)
            self.recognition.setText(f"Recording • {len(self._capture_samples)}/16 samples")
            return
        gesture = self._find_gesture(result.prediction.gesture_id)
        if gesture:
            self.recognition.setText(f"Recognized: {gesture.name}  →  {ACTION_LABELS[gesture.action]}")
        else:
            self.recognition.setText(f"No action • {result.prediction.reason}")
        if self.tabs.currentIndex() == 1:
            fired_id = self.gate.update(result.prediction, now)
            fired = self._find_gesture(fired_id)
            if fired:
                self._run_action(fired.action, fired.name)

    def _show_frame(self, frame, result: FrameResult) -> None:
        height, width = frame.shape[:2]
        if result.landmarks:
            points = [(int(x * width), int(y * height)) for x, y, _ in result.landmarks]
            for start, end in HAND_CONNECTIONS:
                cv2.line(frame, points[start], points[end], (92, 230, 180), 2)
            for point in points:
                cv2.circle(frame, point, 4, (255, 255, 255), -1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _start_capture(self) -> None:
        name = self.name_input.text().strip()
        if not self.camera.isOpened():
            self._set_status("A working camera is required to record a gesture.")
            return
        if not name:
            self._set_status("Enter a gesture name first.")
            return
        if any(gesture.name.casefold() == name.casefold() for gesture in self.profile.gestures):
            self._set_status("That gesture name already exists. Choose another name.")
            return
        self._capture_name = name
        self._capture_action = self.action_input.currentData()
        self._capture_samples = []
        self._capture_last_sample = 0.0
        self._capture_deadline = time.monotonic() + 12.0
        self.record_button.setEnabled(False)
        self.gate.reset()
        self.capture_feedback.setText("Hold the pose steadily and vary its angle slightly.")
        self._set_status(f"Recording {name}…")

    def _collect_sample(self, result: FrameResult, now: float) -> None:
        if now >= self._capture_deadline:
            self._capture_name = ""
            self.record_button.setEnabled(True)
            self.capture_feedback.setText("Recording timed out. Try again with your hand visible.")
            return
        if result.features is None or now - self._capture_last_sample < 0.12:
            return
        self._capture_last_sample = now
        self._capture_samples.append(list(result.features))
        self.capture_feedback.setText(f"Collected {len(self._capture_samples)} of 16 samples")
        if len(self._capture_samples) < 16:
            return
        gesture = GestureDefinition(uuid4().hex, self._capture_name,
                                    self._capture_action, self._capture_samples)
        self.profile.gestures.append(gesture)
        self.engine.fit(self.profile.gestures)
        self._save()
        self._capture_name = ""
        self.record_button.setEnabled(True)
        self.name_input.clear()
        self.capture_feedback.setText(f"Saved {gesture.name} with 16 samples")
        self._refresh_gestures()
        self._set_status(f"{gesture.name} is ready. Open Workshop and hold the pose to test it.")

    def _find_gesture(self, gesture_id: str | None) -> GestureDefinition | None:
        return next((item for item in self.profile.gestures if item.gesture_id == gesture_id), None)

    def _refresh_gestures(self) -> None:
        self.gesture_list.clear()
        for gesture in self.profile.gestures:
            item = QListWidgetItem(f"{gesture.name}  →  {ACTION_LABELS[gesture.action]}  ({len(gesture.samples)})")
            item.setData(Qt.UserRole, gesture.gesture_id)
            self.gesture_list.addItem(item)

    def _on_selection_changed(self, item: QListWidgetItem | None, _previous) -> None:
        gesture = self._find_gesture(item.data(Qt.UserRole)) if item else None
        if gesture:
            self.edit_action.setCurrentIndex(ACTIONS.index(gesture.action))

    def _assign_action(self) -> None:
        item = self.gesture_list.currentItem()
        gesture = self._find_gesture(item.data(Qt.UserRole)) if item else None
        if not gesture:
            self._set_status("Select a saved gesture first.")
            return
        gesture.action = self.edit_action.currentData()
        self._save()
        self._refresh_gestures()
        self._set_status(f"{gesture.name} now runs {ACTION_LABELS[gesture.action]}.")

    def _delete_gesture(self) -> None:
        item = self.gesture_list.currentItem()
        gesture = self._find_gesture(item.data(Qt.UserRole)) if item else None
        if not gesture:
            self._set_status("Select a saved gesture first.")
            return
        self.profile.gestures.remove(gesture)
        self.engine.fit(self.profile.gestures)
        self.gate.reset()
        self._save()
        self._refresh_gestures()
        self._set_status(f"Deleted {gesture.name}.")

    def _run_action(self, action: str, gesture_name: str | None = None) -> None:
        message = self.workshop.apply(action)
        self.profile.workshop_index = self.workshop.index
        self.profile.completed_steps = sorted(self.workshop.completed)
        self._save()
        self._refresh_workshop()
        source = f"{gesture_name}: " if gesture_name else ""
        self._set_status(source + message)

    def _refresh_workshop(self) -> None:
        index = self.workshop.index
        title, instruction = STEPS[index]
        self.step_counter.setText(f"STEP {index + 1:02d} / {len(STEPS):02d}")
        self.step_title.setText(title)
        self.step_body.setText(instruction)
        self.step_done.setText("✓ Complete" if index in self.workshop.completed else "Not completed")
        self.progress.setValue(len(self.workshop.completed))

    def _save(self) -> None:
        save_profile(self.profile_path, self.profile)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.camera.release()
        self.engine.close()
        super().closeEvent(event)


STYLESHEET = """
QMainWindow, QWidget { background: #101b24; color: #ecf5f3; font-family: 'Helvetica Neue'; font-size: 14px; }
QLabel#title { font-size: 32px; font-weight: 800; color: #71e7c1; }
QLabel#subtitle { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #95b9b0; }
QLabel#section { font-size: 12px; font-weight: 700; color: #71e7c1; }
QLabel#heading { font-size: 22px; font-weight: 700; }
QLabel#muted { color: #a9c0bd; }
QLabel#recognition { font-size: 17px; font-weight: 700; color: #e7fffa; }
QLabel#status { background: #18343b; border-radius: 8px; padding: 11px 15px; color: #c9eee4; }
QLabel#stepTitle { font-size: 27px; font-weight: 750; color: #f9ffff; }
QLabel#stepBody { font-size: 18px; line-height: 1.3; color: #d3e6e2; padding-top: 10px; }
QLabel#preview { background: #071016; border: 1px solid #2b4a4c; border-radius: 8px; color: #9ec2bd; }
QFrame#card, QTabWidget::pane { background: #172831; border: 1px solid #34515a; border-radius: 12px; }
QTabBar::tab { background: #1b343d; padding: 11px 18px; border-radius: 8px; margin-right: 5px; }
QTabBar::tab:selected { background: #2c5b58; color: #ffffff; }
QLineEdit, QComboBox, QListWidget { background: #0e2029; border: 1px solid #3a5960; border-radius: 7px; padding: 9px; color: #f5fffc; }
QListWidget { padding: 4px; }
QListWidget::item { padding: 8px; }
QListWidget::item:selected { background: #285850; }
QPushButton { background: #29434b; border: 1px solid #52716f; border-radius: 7px; padding: 10px; font-weight: 700; }
QPushButton:hover { background: #37625f; }
QPushButton#primary { background: #69ddb6; color: #09251f; border: none; }
QPushButton#primary:hover { background: #8df1cf; }
QPushButton:disabled { background: #3b5857; color: #9cafab; }
QProgressBar { background: #0e2029; border: none; border-radius: 6px; height: 10px; text-align: center; }
QProgressBar::chunk { background: #69ddb6; border-radius: 6px; }
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="A.R.C local gesture proof of concept")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    parser.add_argument("--model", type=Path, default=ROOT / "assets" / "hand_landmarker.task")
    parser.add_argument("--profile", type=Path, default=ROOT / "data" / "profile.json")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setStyleSheet(STYLESHEET)
    try:
        window = ArcWindow(args.model, args.profile, args.camera)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        QMessageBox.critical(None, "A.R.C could not start", str(error))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
