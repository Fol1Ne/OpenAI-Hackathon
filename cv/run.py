"""Privacy-preserving CV loop: frame -> YOLOv8n(person only) -> count + brightness -> aggregate JSON. Frames are never written to disk.
Usage: python run.py   (CAMERA_n_URL env, or VIDEO_n path for a RECORDED DEMO)"""
import os, json, time, pathlib, collections
import cv2, numpy as np
from ultralytics import YOLO
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "cache" / "camera_metrics.json"
INTERVAL, WINDOW = 7, 30 * 60 // 7
try: model = YOLO("yolov8n.pt")
except Exception as e:  # missing/undownloadable weights must never break the demo
    raise SystemExit(f"YOLO weights unavailable ({e}). Backend will keep serving DEMO CAMERA data.")
def brightness(f): return float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() / 255.0)
def count(f): return sum(1 for b in model(f, classes=[0], verbose=False)[0].boxes)
caps = {f"cam{i}": os.getenv(f"CAMERA_{i}_URL") or os.getenv(f"VIDEO_{i}") for i in (1, 2)}
caps = {k: cv2.VideoCapture(v) for k, v in caps.items() if v}
hist = {k: collections.deque(maxlen=WINDOW) for k in caps}; state = {}
while caps:
    for k, cap in caps.items():
        ok, frame = cap.read()
        if not ok: cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue  # loop recorded video
        n = count(frame); hist[k].append(n)
        state[k] = {"ts": time.time(), "people_now": n, "rolling_average": round(float(np.mean(hist[k])), 1),
                    "brightness": round(brightness(frame), 2)}  # frame discarded here
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(state)); time.sleep(INTERVAL)
print("No camera URLs or VIDEO_n files set.")
