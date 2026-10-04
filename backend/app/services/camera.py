"""CameraService: LiveCameraService (metrics written by cv/run.py, <120s old) -> DemoCameraService (deterministic fixture, labelled DEMO)."""
import json, pathlib, time, datetime
from .traffic import classify_activity
D = pathlib.Path(__file__).resolve().parents[1] / "data"
METRICS = pathlib.Path(__file__).resolve().parents[3] / "data" / "cache" / "camera_metrics.json"
DEMO = {"cam1": (5, 6.2, 0.41), "cam2": (2, 3.1, 0.33)}  # DEMO DATA, deterministic

def _iso(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
def cameras():
    cams = json.loads((D / "cameras.json").read_text())
    try: live = json.loads(METRICS.read_text()) if METRICS.exists() else {}
    except Exception: live = {}
    out = []
    for c in cams:
        m = live.get(c["id"])
        if m and time.time() - m["ts"] < 120:
            src, now, avg, br, ts = "live", m["people_now"], m["rolling_average"], m["brightness"], m["ts"]
        else:
            (now, avg, br), src, ts = DEMO[c["id"]], "demo", time.time() - 12
        out.append({"id": c["id"], "street": c["street"], "latitude": c["latitude"], "longitude": c["longitude"], "source": src,
                    "status": "LIVE" if src == "live" else "DEMO CAMERA", "people_now": now, "avg_people_30min": avg, "brightness": br,
                    "activity": classify_activity(avg), "updated": _iso(ts)})
    return out
