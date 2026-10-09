# A.R.C

**Your hands. Your gestures. Your control.**

A.R.C is an offline-first desktop proof of concept for teaching a computer personal static hand gestures and using them to control a five-step workshop task. GestureForge was the working name in the supplied concept plan; this repository uses **A.R.C** throughout.

## Run on macOS

Use a Mac with a webcam and [Homebrew](https://brew.sh/). Python 3.11 is the team baseline; the system Python 3.9 on some Macs is too old for this setup. The first installation and model download require internet. Gesture capture, training, recognition, actions, and profile reload then run locally.

```bash
brew install python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m arc.app
```

Run the dependency-free core checks with `python -m unittest discover -s tests`.

Run these commands from the repository root. On first camera use, grant Terminal or your Python launcher access in **System Settings → Privacy & Security → Camera**. If the default camera is wrong, use `python -m arc.app --camera 1`.

## First working demo

1. In **Gesture Studio**, name a pose, choose **Next step**, and press **Record gesture**. Hold the pose in view until all 16 samples are saved.
2. Teach a visibly different pose for **Previous step** or **Mark complete**.
3. Open **Workshop**. Hold a trained pose for about 0.65 seconds. The mapped action changes the real workshop state; lowering your hand releases the trigger.
4. Quit and restart the app. Saved gestures, mappings, and workshop progress load from `data/profile.json`.
5. Disconnect networking and repeat steps 1–4 to verify local training and operation. The model must already be downloaded.

Manual Workshop buttons let the application track be tested before a webcam or gesture is available. Camera frames are processed in memory and are never written by this app. The profile stores only normalized 63-number landmark samples, gesture names and mappings, and workshop progress.

## Project files

```text
A.R.C/
├── README.md
├── requirements.txt
├── docs/
│   └── DEVELOPMENT_PLAN.md       # two-person tracks, interface contract, 48-hour schedule
├── scripts/
│   └── download_model.py         # one-time MediaPipe model download
├── tests/
│   └── test_core.py              # activation, persistence, workflow checks
├── assets/
│   ├── README.md                  # model setup note
│   └── hand_landmarker.task       # downloaded locally; ignored by Git
├── data/
│   ├── README.md                  # local profile note
│   └── profile.json              # created at first save; ignored by Git
└── arc/
    ├── contracts.py              # shared data and method interface
    ├── engine.py                 # Track A: MediaPipe, features, KNN, rejection
    ├── gate.py                   # Track A: stable hold, release, and cooldown
    ├── app.py                    # Track B: PySide6 UI, OpenCV camera, action wiring
    ├── profile.py                # Track B: versioned JSON persistence
    └── workshop.py               # Track B: five-step tutorial state
```

## Current scope and limitations

The implementation handles one hand and static poses. It uses a fixed starting distance threshold and class margin; these are deliberately conservative defaults that need calibration with actual users and cameras. Gesture samples captured during one short session can be similar, so record distinct poses and vary the hand angle slightly. Recognition results are not benchmarked yet. Camera processing currently runs on the UI event loop, so slower machines may show a lower preview frame rate. Kitchen Mode, external application control, multiple profiles, audio playback, and moving gestures are outside this proof of concept.

The model file comes from the [official MediaPipe Hand Landmarker model link](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker). The [MediaPipe Python API](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/HandLandmarker) supports the video-frame call used here. [PySide6's official setup guide](https://doc.qt.io/qtforpython-6/gettingstarted.html) recommends a virtual environment and pip installation. [scikit-learn's KNN documentation](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsClassifier.html) describes the local classifier.

The OpenCV binding is installed through `opencv-contrib-python`, which provides `cv2` and avoids installing two competing OpenCV wheel variants alongside MediaPipe. See [OpenCV's Python installation guide](https://docs.opencv.org/doc/doxygen/html/db/dd1/tutorial_py_pip_install.html).

