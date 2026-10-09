# A.R.C — two-developer implementation plan

**Hackathon:** AppBuildersPH Local AI Hackathon  
**Team:** two developers  
**MVP window:** 48 hours  
**Target:** macOS laptop with webcam, with PC/laptop portability after MVP  
**Success definition:** a user teaches a new static gesture, assigns an action, saves it, and uses it to control a real workshop instruction while disconnected from the internet.

The supplied concept used the name GestureForge and listed three people. For this repository, the product name is **A.R.C** and the work is split between **two developers**. UI, testing, documentation, and demo preparation are owned inside the two tracks below. Functionality and repeatable action triggering are the first priority; visual polish follows a stable end-to-end flow.

## Immediate proof of concept

The repository already contains a runnable vertical slice. Follow the exact macOS commands in [`README.md`](../README.md). The app opens a mirrored webcam preview, estimates 21 MediaPipe hand landmarks locally, turns them into 63 normalized values, records 16 examples per new gesture, fits a scikit-learn KNN classifier, rejects distant or ambiguous poses, and triggers an internal Workshop action after a stable hold. Gestures, mappings, and progress are stored as local JSON. These are implementation capabilities, not measured accuracy claims.

## Independent development tracks

| Owner | Files owned | Deliverable | Acceptance checkpoint |
|---|---|---|---|
| **Developer A — AI and vision** | `arc/engine.py`, `arc/gate.py`, model download and vision tests | Local hand tracking, normalization, sample classification, unknown/ambiguous rejection, stable activation | Camera hand points track; three trained poses are recognized and unfamiliar poses fail the defined test set |
| **Developer B — desktop and workflow** | `arc/app.py`, `arc/profile.py`, `arc/workshop.py`, UI and persistence tests | Training flow, camera preview, action mapping, Workshop, local profile save/reload, demo experience | A user records a gesture, maps it, advances a five-step task, and retains it across restart |

`arc/contracts.py` is the jointly approved interface. Neither developer changes its fields or semantics unilaterally. If an interface change is necessary, agree on it first and update the contract, example call, persistence version, and both tracks together. Each developer can run their part with stubbed `FrameResult` objects or manual Workshop buttons while the other track is in progress.

### Shared interface, version 1

```python
from arc.contracts import GestureDefinition, FrameResult, Prediction
from arc.engine import GestureEngine
from arc.gate import ActivationGate

engine = GestureEngine(model_path)
engine.fit(list_of_gesture_definitions)
result: FrameResult = engine.process_frame(frame_bgr, timestamp_ms)
fired_id = gate.update(result.prediction, monotonic_seconds)
engine.close()
```

- `frame_bgr`: OpenCV `uint8` BGR image. The app mirrors it before calling the engine.
- `timestamp_ms`: monotonic milliseconds; the engine makes equal or stale timestamps increasing for MediaPipe VIDEO mode.
- `FrameResult.landmarks`: zero or 21 `(x, y, z)` camera-normalized coordinates for drawing only.
- `FrameResult.features`: `None` or exactly 63 finite floats: wrist-relative, palm-scaled and palm-rotation-normalized landmark coordinates. **Only this vector is saved for training.** Changing the feature formula requires a profile migration or retraining.
- `Prediction.gesture_id`: `None` means no action candidate, including no hand, invalid, unknown, or ambiguous poses. `distance` is nearest training sample RMS over the 63 values; `margin` is the next class distance minus the winning class distance. These are diagnostics, not probabilities.
- `ActivationGate.update`: returns a gesture ID once after a roughly 0.65-second steady hold. It requires about 0.35 seconds of release and enforces a 1-second cooldown. Call `reset()` when entering or leaving training mode.
- `GestureDefinition`: `gesture_id` is an immutable UUID string; `name` is user text; `action` is one of `next_step`, `previous_step`, `complete_step`, `replay_step`; `samples` is a list of 63-float vectors.
- `data/profile.json` uses `version: 1` and stores gestures plus workshop progress. Do not store pickled scikit-learn objects. Refit KNN from samples at startup so the file remains inspectable and portable.

**Integration rule:** the engine never imports Qt or calls workflow actions. The application never interprets raw hand landmarks or decides classifier thresholds. The only connection is `FrameResult` → `ActivationGate` → gesture ID → saved action → `Workshop.apply(action)`.

## Implementation order and 48-hour checkpoints

| Time | Developer A | Developer B | Shared checkpoint |
|---|---|---|---|
| 0–4 h | Validate camera frame format, model load, and 21 landmarks | Run app shell and manual Workshop buttons | Live preview plus landmark overlay |
| 4–10 h | Confirm feature normalization and KNN refit from two poses | Make recording flow and JSON save/reload robust | Two gestures can be taught and persist |
| 10–16 h | Tune unknown rejection and class margin from recordings | Show recognized/unknown feedback and mapped action | Known poses activate; unfamiliar poses are rejected in trial set |
| 16–24 h | Check latency under real camera conditions | Finish five-step Workshop and all internal actions | Hand pose advances actual workshop state |
| 24–30 h | Add useful conflict feedback if core is stable | Improve gesture management, error messages, and UI | Restart retains mapping and progress |
| 30–36 h | Tune hold, release, cooldown from observed false triggers | Handle camera loss and capture retry; help run tests | Repeated deliberate activation works without rapid retriggers |
| 36–42 h | Run three-gesture and unknown-pose trials; log results | Run offline restart and unfamiliar-user workflow trial | Measured evidence is written down |
| 42–48 h | Freeze model/threshold settings; prepare backup demo | Polish and rehearse three-minute presentation | Stable end-to-end demo and recording |

Run Kitchen Mode only if the shared checkpoint at 36–42 hours is solid. A third workstream would create avoidable integration overhead for two developers.

## Reliability and safety behavior

1. No detected hand produces `gesture_id=None`.
2. KNN produces a candidate, but the closest sample must be inside the distance threshold (`0.18` RMS initially).
3. With multiple classes, the winning class needs at least `0.035` RMS separation from the next closest class; otherwise it is ambiguous.
4. A stable accepted candidate must persist for `0.65` seconds before an action.
5. The same held pose fires once. It must be released or become unrecognized for `0.35` seconds, and at least `1.0` second must pass since the prior trigger.
6. These thresholds are starting values. Record actual test results and tune them on the demo camera; do not present them as guaranteed accuracy.
7. A new gesture that resembles an existing one should be redone with a more distinct pose. Automated conflict coaching is secondary after MVP reliability.

Only in-app Workshop actions are available in this MVP. External shortcuts, OS control, and clinical use are outside scope.

## Acceptance tests and evidence sheet

Record the date, hardware, camera, lighting, model file, trained poses, and threshold settings alongside the results. Development targets are not results.

| Test | Procedure | Target | Actual result |
|---|---|---|---|
| Local AI | Disconnect networking; create a new pose, train, and use it | All steps work offline after setup | To measure |
| Recognition | For each of three distinct poses, try ten deliberate activations | At least 9/10 per pose in controlled conditions | To measure |
| Unknown rejection | Present at least 20 unregistered poses or ordinary movements | Zero action activations in this controlled trial | To measure |
| Workshop | Ask an unfamiliar tester to finish all five steps | Task completed with gesture controls | To measure |
| Persistence | Quit and restart offline | Gestures, actions, and progress still work | To measure |
| Usability | Compare manual and gesture operation; record time, interruptions, false activations, feedback | Document observed tradeoffs | To measure |
| Performance | Log frame processing and action latency on demo hardware | Stable enough for live interaction | To measure |

If the unknown-rejection target fails, tighten the distance/margin thresholds and collect more varied samples. If deliberate activations fail, inspect camera tracking, sample quality, and per-gesture distances before loosening thresholds. Avoid improving one metric by silently hurting the other.

## Demo and deliverables

**Three-minute story:** problem (0:00–0:30), local personalized control (0:30–1:00), teach a new pose (1:00–1:40), turn networking off (1:40–2:00), advance the real Workshop and show an unknown pose is ignored (2:00–2:35), then explain future modes (2:35–3:00). Record a short backup video of the same flow.

The handoff package is: source code, this architecture and setup documentation, the one-time model download instruction, a working desktop app, a completed evidence sheet with actual measurements, and a presentation recording. MediaPipe hand tracking and scikit-learn KNN run locally; no LLM is needed. Kitchen Mode, multiple profiles, external application control, and moving gestures follow only after the MVP passes its offline and reliability trials.

## Sources for the implementation choices

- [MediaPipe Hand Landmarker model and task guide](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
- [MediaPipe Python HandLandmarker API](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/HandLandmarker)
- [PySide6 installation guide](https://doc.qt.io/qtforpython-6/gettingstarted.html)
- [scikit-learn KNeighborsClassifier API](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsClassifier.html)
