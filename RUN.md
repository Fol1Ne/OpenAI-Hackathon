# Run (no API keys needed)

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # DEMO_MODE=true works with no keys
uvicorn app.main:app --reload   # :8000
python -m pytest

# frontend (new terminal)
cd frontend && npm install && npm run dev   # proxies /api -> :8000

# CV (optional, live metrics)
cd cv && pip install -r requirements.txt
CAMERA_1_URL=<stream> CAMERA_2_URL=<stream> python run.py
# or recorded demo: VIDEO_1=clip1.mp4 VIDEO_2=clip2.mp4 python run.py
```
Demo mode: `DEMO_MODE=true` (default). Camera values are labelled SIMULATED until cv/run.py writes fresh metrics; sample lighting is synthetic fixture data until Overpass cache exists.
