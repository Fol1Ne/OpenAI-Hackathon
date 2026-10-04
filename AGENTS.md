# AGENTS.md: Safe Routes Home (5-hour hackathon build)

Read this fully before writing any code. It is the shared context for every person and every coding agent on this repo.

## What we're building

A map app that gives women **facts** about routes home at night: which streets have consistent foot traffic and which are well lit. We do not compute a "safety score". We show measured information and let the user decide.

**Pitch line:** "We don't watch people. We measure how busy and well-lit a street is right now, and give women a choice about their route home."

## Data sources

| Fact | Source | Coverage |
|---|---|---|
| Foot traffic | Live camera stream, YOLOv8 person count, rolling average | 2 Dublin streets (real) |
| Lighting (camera streets) | Average frame brightness via OpenCV | 2 streets |
| Lighting (everywhere else) | OpenStreetMap `lit=yes/no` tag via Overpass API | City-wide |
| Foot traffic (everywhere else) | **Unknown**, shown grey. Optional synthetic data, always labelled `"synthetic"` | n/a |

## Principles (non-negotiable)

1. **No footage stored.** Process frames in memory, discard immediately. Persist only street-level numbers (count, brightness, timestamp).
2. **No identification.** No face recognition, no re-identification, no per-person history. Any tracking IDs are anonymous, in-memory, and short-lived.
3. **No arbitrary score.** Every number shown to the user is something measured. Routes are described with plain facts ("60% well lit"), not ranked by an opaque number.
4. **Honest about unknowns.** No data means grey "unknown", never a guess. Synthetic data is always badged "simulated".
5. **Information, not enforcement.** Nothing is reported to anyone. Data flows one way: camera to street facts to the user's route choice.
6. **No judgement language.** Never use words like "dangerous", "unsafe", "crime", or "antisocial" in the UI or code. Use "quiet", "steady", "busy", "well lit", "no data".
7. The app is decision support, not a guarantee of safety. Show a short disclaimer.

## Cut list (do NOT build)

- Antisocial or incident detection (future-work slide only)
- Custom pathfinding (fetch alternative routes and compare them)
- Training any model (use pretrained YOLOv8n)
- Auth, accounts, database (in-memory state or a JSON file)
- WebSockets (poll every 5-10 seconds)
- A composite safety score

## Stack (locked)

- **Backend + CV:** Python 3.11+, FastAPI, OpenCV, `yt-dlp` or `streamlink`, `ultralytics` (YOLOv8n)
- **Routing:** OSRM public server with `alternatives=true`, or Mapbox Directions if a token is available
- **Lighting data:** Overpass API (OpenStreetMap)
- **Frontend:** Vite + React + Leaflet + OpenStreetMap tiles
- **OpenAI (optional):** one function, `explain_routes()`, turns route facts into a plain-English sentence. Keep all vendor calls behind this one function so it is swappable. Never send images or frames to any external API unless the team agrees.

## The contract

### `GET /segments`

```json
[
  {
    "id": "seg1",
    "name": "Street A",
    "coords": [[53.3400, -6.2600], [53.3410, -6.2590]],
    "foot_traffic": "steady",
    "avg_people_30min": 6.2,
    "lit": "yes",
    "brightness": 0.41,
    "source": "live"
  }
]
```

- `foot_traffic`: `"steady" | "quiet" | "busy" | "unknown"`
- `lit`: `"yes" | "no" | "unknown"`
- `source`: `"live" | "osm" | "synthetic"`
- `brightness` and `avg_people_30min` are `null` when not measured

### `GET /route?from=lat,lng&to=lat,lng`

```json
{
  "fastest": {
    "coords": [[53.34, -6.26]],
    "minutes": 12,
    "pct_lit": 60,
    "streets_with_live_traffic": 1,
    "total_streets": 5
  },
  "well_lit": {
    "coords": [[53.34, -6.26]],
    "minutes": 15,
    "pct_lit": 95,
    "streets_with_live_traffic": 2,
    "total_streets": 5
  },
  "explanation": "The well-lit route adds 3 minutes but stays on lit streets, including Street A, which has steady foot traffic."
}
```

**Route selection rule:** fetch alternatives, pick the one with the highest share of lit street length. Break ties by the number of streets with steady live foot traffic. `unknown` counts as neither lit nor unlit.

**Foot traffic labels:** based on a rolling average over the last 30-60 minutes. Thresholds (tune on real data): `quiet` < 2, `steady` 2-8, `busy` > 8 average people in frame.

### `GET /cameras`

```json
[
  {
    "id": "cam1",
    "street": "Street A",
    "people_now": 5,
    "avg_people_30min": 6.2,
    "brightness": 0.41,
    "frame_url": "/frames/cam1.jpg",
    "updated": "2025-01-01T22:10:00Z"
  }
]
```

`frame_url` is the latest annotated frame, **demo only**, held in memory and overwritten each cycle. Blur people if time allows.

## Roles (3 people, each drives their own coding agent(s))

### Person 1: CV pipeline (`/cv`)

Done when `/cameras` returns live counts, rolling averages and brightness.

- Test the stream grab FIRST (30 minutes max). This is the biggest risk. If YouTube fails, loop a recorded clip through the same pipeline.
- Grab a frame every 5-10 seconds, run YOLOv8n person detection, count people.
- Keep a rolling window (30-60 min) per camera. Compute `avg_people_30min`.
- Compute mean frame brightness (0-1) with OpenCV.
- Draw bounding boxes on the latest frame and save it to memory/disk (overwrite, never accumulate).
- Write a replay mode: `python cv/run.py --video clip.mp4` runs the identical pipeline on a file.
- Expose results as a Python module the backend can import, or a tiny FastAPI app on its own port.

### Person 2: Backend + routing + data (`/backend`)

Done when `/segments` and `/route` return correct JSON with mock inputs, then with real ones.

- FastAPI app implementing the contract above. Start with hardcoded mock JSON so Person 3 is never blocked.
- Camera metadata file (`cameras.json`): id, stream URL, lat/lng, which street segment it covers.
- Pull `lit` tags from Overpass for a bounding box around central Dublin. Cache the result to a JSON file so the demo works offline.
- Call OSRM/Mapbox with alternatives. Match each route's streets to segments, compute `pct_lit`, streets with live traffic, and apply the selection rule.
- `explain_routes()`: one OpenAI call that turns the two route fact blocks into one friendly sentence. Must fail gracefully (return a templated sentence) if the API is slow or down.
- Optional synthetic foot traffic generator, labelled `source: "synthetic"`, switchable by an env var.

### Person 3: Frontend + integration + pitch (`/frontend`)

Done when the full demo runs end to end from a clean checkout.

- Vite + React + Leaflet. Start against a mock JSON file, then switch to the real API with one env var.
- Colour-coded segments: lit vs unlit vs unknown (grey). Foot traffic shown as line style or markers, with a legend. Badge simulated data.
- Click to set start and end. Toggle "Fastest" / "Well lit". A comparison card with plain facts (minutes, % lit, live traffic coverage) and the explanation sentence.
- Camera markers that open the demo-only annotated frame panel.
- Footer disclaimer: "Decision support, not a guarantee of safety."
- **Integrator:** you own the seams. Check JSON shapes at every connection point. Keep a `RUN.md` with the exact start command for each piece.
- Pitch deck, demo script, and a recorded fallback demo video.

## Timeline

| Time | Goal |
|---|---|
| 0:00-0:30 | Everyone reads this file. Create repo and folders. Person 1 tests the stream grab. Person 2 publishes mock endpoints. |
| 0:30-2:30 | Parallel build against mocks. Commit small and often, only inside your own folder. |
| 2:30-3:30 | Integrate real CV output, backend, frontend. Fix seams. |
| 3:30-4:00 | Polish, legend, disclaimer, synthetic toggle, cached Overpass data. |
| **4:00** | **FEATURE FREEZE.** Bug fixes only. |
| 4:00-5:00 | Record fallback demo, rehearse the pitch twice, test on venue Wi-Fi. |

## Rules for coding agents

1. Stay inside your assigned folder. Never edit another person's folder.
2. Do not change the contract. If it needs to change, tell the whole team first, and update this file.
3. Build one runnable thing at a time. End every task by writing the exact command to run it.
4. Do not add features from the cut list.
5. Wrap every external call (stream, Overpass, OSRM, OpenAI) in a timeout and a fallback. A slow call must never freeze the UI.
6. Never commit API keys. Use a `.env` file listed in `.gitignore`.
7. Never write frames or images to a persistent location other than the single overwritten demo frame per camera.

## Pitch notes

- Say plainly: two streets are live, lighting is real city-wide from OpenStreetMap, everything else is labelled unknown or simulated.
- **"Isn't a crowd sometimes less safe?"** We don't claim more people means safer. We show consistent foot traffic as a fact and let the user decide.
- **Privacy:** counts people, stores no footage, identifies no one. A full rollout would need a data protection impact assessment and permission from the camera operator.
- **Scale story:** Dublin already has thousands of cameras. We show it works with two.
- Future work: more cameras, a user-reported layer, accessibility routing, and a DPIA before any real deployment.

## Passage-counting extension (user-requested, 2026-10-04)

This implementation spans CV, backend integration and frontend. `/cameras` keeps
its existing measurement fields and adds `passages_10min` (integer or null),
`observed_seconds` (0–600), `window_seconds` (600), `window_complete` (boolean),
`status` (`collecting`, `complete`, `no_data`), `needs_calibration` (boolean), and
`location_note`. Camera `source` is `live`, `synthetic` (recorded replay) or
`unknown`. `updated` is the last successful frame timestamp, null before first
observation; missing/stale counts are null. Pending camera coordinates are null.
`frame_url` points to `/frames/camN.jpg` while observations are current. The
user-requested live demo shows green person boxes and a yellow counting line.
Only the latest annotated JPEG is kept in worker memory, with detected people
blurred. Loopback-only preview servers use ports 8101–8103; FastAPI proxies
them with a two-second timeout and no-store headers. Stale images return 503.

Temple Bar, Cabra Road and North Circular Road replace the old demo cameras.
All three user-supplied feeds are configured with initial counting lines. Cabra
Road and North Circular Road map coordinates remain unconfirmed. Missing feeds show no current
data even when route/lighting demos are enabled. Count crossings of a calibrated
finite pavement line in either direction, once per short-lived geometric track.
Tracks expire after one second unseen or 30 seconds total and are never saved.
Only aggregate counts, coverage, brightness and timestamps are persisted.
The demo-only annotated frame can be read locally from worker memory.
A full-window label requires 600 seconds observed in the trailing 600 seconds;
partial windows show their actual coverage. Counts are detector estimates, not
unique identities or a measurement of the entire road. No red thresholds are
introduced by this change. Synthetic observations never count as live coverage.

## A-to-B routing update (user-requested, 2026-10-04)

The user's new direction supersedes the lighting-based route-selection rule.
Use the fastest available pedestrian route from a dedicated OSRM foot-profile
server. Lighting and pedestrian activity do not change the path. Remove fixture
routing and custom graph traversal; routing outages return HTTP 503 with a retry
message. `/route` adds `route` (selected path), `camera_ids`, `street_names` and
`traffic_warnings`; `fastest` and `well_lit` remain compatibility aliases of the
same route. Route cameras must be within 15m of its geometry; road names alone
cannot match an entire road. Notices describe zero pedestrians in a fresh frame,
or zero passages over a complete observed 10-minute window, limited to the
camera-covered section. Partial, stale or missing passage counts never imply
zero. The frontend refreshes notices using camera polling without rerouting.

## Shared-tab demo extension (user-requested)

`POST /tab-capture/detect` accepts a JPEG (max 1 MB), `X-Session` anonymous
session token and `X-Line` normalized endpoint JSON. It proxies only to the
loopback CV server on port 8110 with a two-second timeout and returns person
boxes plus rolling passage/coverage aggregates. Frames never persist. Tracking
sessions expire after inactivity. Browser permission and two-click line setup
are required. Results are explicitly shared-tab demo observations and do not
update verified camera or route facts.
