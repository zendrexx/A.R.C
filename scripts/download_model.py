"""One-time download of Google's MediaPipe Hand Landmarker bundle."""

from pathlib import Path
from urllib.request import urlopen

URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
       "hand_landmarker/float16/1/hand_landmarker.task")
DESTINATION = Path(__file__).resolve().parents[1] / "assets" / "hand_landmarker.task"


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists() and DESTINATION.stat().st_size > 1_000_000:
        print(f"Model already present: {DESTINATION}")
        return
    print(f"Downloading model to {DESTINATION}")
    with urlopen(URL, timeout=60) as response:
        data = response.read()
    if len(data) < 1_000_000:
        raise RuntimeError("Model download was unexpectedly small")
    temporary = DESTINATION.with_suffix(".download")
    temporary.write_bytes(data)
    temporary.replace(DESTINATION)
    print("Model ready. Inference can now run offline.")


if __name__ == "__main__":
    main()
