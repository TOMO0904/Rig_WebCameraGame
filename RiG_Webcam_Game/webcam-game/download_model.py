"""Download Google's official Hand Landmarker model once; no API key needed."""
from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen
import shutil
import sys

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"


def main() -> None:
    MODEL_PATH.parent.mkdir(parents=True,exist_ok=True)
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        print(f"Model already exists: {MODEL_PATH}")
        return
    temp=MODEL_PATH.with_suffix(".download")
    try:
        print(f"Downloading official MediaPipe model from: {MODEL_URL}")
        with urlopen(MODEL_URL,timeout=40) as response, temp.open("wb") as dst:
            shutil.copyfileobj(response,dst)
        if temp.stat().st_size < 1_000_000:
            raise RuntimeError("Model download appears incomplete")
        temp.replace(MODEL_PATH)
        print(f"Saved: {MODEL_PATH} ({MODEL_PATH.stat().st_size:,} bytes)")
    except Exception as exc:
        temp.unlink(missing_ok=True)
        sys.exit(f"Model download failed: {exc}\nDownload manually from {MODEL_URL}\nand save it to {MODEL_PATH}")

if __name__=="__main__":
    main()
