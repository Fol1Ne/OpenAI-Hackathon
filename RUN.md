# Run Safe Routes Home

From the repository root, in separate terminals:

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open http://127.0.0.1:5173. Route and lighting fixtures remain labelled demo.
Camera counts are never fabricated: missing/stale observations show “No current data”.

## Pedestrian passage worker

Install once, from the repository root (CPU install avoids large GPU packages):

```bash
python3 -m venv cv/.venv
cv/.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
cv/.venv/bin/python -m pip install -r cv/requirements.txt
curl --fail --location --max-time 60 --retry 1 --output cv/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

Node.js must be on PATH for yt-dlp YouTube resolution. Camera configuration is
`backend/app/data/cameras.json`. Temple Bar uses the supplied YouTube URL.
Provide `CAMERA_2_URL` for Cabra Road and `CAMERA_3_URL` for North Circular Road
in the root `.env` or shell; fill their coordinates only after checking the camera
location. Root `.env` loads automatically. Empty camera URLs remain unavailable.

Temple Bar has an initial line placed from the supplied live view. The counter can
start immediately with the final monitoring command below. Recheck that line
against observed crossings before relying on its estimates.

Before counting a new camera, calibrate its finite line across the visible pavement:

```bash
cv/.venv/bin/python cv/run.py --calibrate cam1
```

Click two endpoints, press Enter to save, R to reset, Escape to cancel. This opens
a local OpenCV window and stores only normalized coordinates and the source URL.
Use cam2/cam3 for the other feeds. Repeat calibration if the view changes. The
placeholder lines are inactive until confirmed; source changes require calibration.

Start continuous monitoring of all configured and calibrated feeds:

```bash
cv/.venv/bin/python cv/run.py
```

On a headless machine, inspect the camera view and provide confirmed normalized
endpoints explicitly (x1,y1,x2,y2); this command only runs the selected camera:

```bash
cv/.venv/bin/python cv/run.py --camera cam1 --line 0.2,0.65,0.8,0.65
```

Those coordinates are an example, not a calibrated Temple Bar line.
Run only one worker supervisor at a time; it owns the atomic aggregate metrics file.
The backend/frontend can stay running during worker restarts.

Replay a local clip in real time through the same detector/counter, labelled SIMULATED:

```bash
cv/.venv/bin/python cv/run.py --camera cam1 --video /absolute/path/clip.mp4 --line 0.2,0.65,0.8,0.65
```

Frames and tracks stay in memory. Tracking uses geometric proximity, has no face or
appearance matching, and expires after one second unseen or 30 seconds lifetime.
Crossings count once per track in either direction; occlusion and crowded scenes
can cause missed or duplicate estimates. Manually compare crossings before using
counts in a demonstration. A camera measures only its visible pavement.

Coverage measures intervals between processed fresh frames, at most one second
apart. Startup and gaps show “Collecting data: X of 10 minutes”; only a complete
window says “in the last 10 minutes”. Slow processing and read failures interrupt
coverage. The API expires observations after five seconds; the UI also ages out
cached data. Disconnects reset tracks, keep trailing aggregate counts in memory,
and never add zeros for an unobserved interval. Reconnects retry every ten seconds;
a supervisor restarts stalled workers. Restarting the worker begins a new window.
No process continues when this local worker is stopped.

## Checks

```bash
(cd backend && .venv/bin/python -m pytest)
python3 -m unittest discover -s cv -p 'test_*.py'
(cd frontend && npm run build)
```

## Temple Bar green-box live demo

Open http://127.0.0.1:5173/demo/temple-bar after starting the backend, frontend
and `cv/.venv/bin/python cv/run.py`. The Temple Bar activity card also links here.
The preview refreshes about four times per second using the existing detector.
Green boxes mark detected pedestrians; the yellow line marks the passage counter.
Detected person regions are blurred before display. Only one latest JPEG per
camera is held in memory; no preview images are saved. The CV workers bind local
preview ports 8101–8103. The backend proxies `/frames/cam1.jpg`; stale frames
expire after three seconds and all image responses disable browser caching.
