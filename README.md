# Safe Routes Home — Know the route. Make the choice.

> **No API keys are required to run the demo.**

| | Demo mode (`DEMO_MODE=true`, default) | Live mode (`DEMO_MODE=false`) |
|---|---|---|
| Map | OSM tiles (override with `VITE_TILE_URL`) | same |
| Routing | deterministic demo routes (labelled DEMO ROUTE) | public OSRM, auto-fallback to demo routes |
| Lighting | bundled fixture `data/lighting/dublin_demo_lighting.json` (DEMO DATA, not real OSM tags) | Overpass -> `data/cache`, auto-fallback to cache, then demo |
| Cameras | DEMO CAMERA values (never shown as live) | `CAMERA_n_URL` + `cv/run.py` -> LIVE; otherwise DEMO CAMERA |
| Explanation | deterministic template | optional OpenAI (`ENABLE_AI=true`, backend-only key), silent template fallback |

`GET /status` shows which implementation is active. Demo fixtures exist only to guarantee a reliable presentation and make no claim about current conditions.

Night-time walking route comparison using measurable data: duration, OSM `lit=*` coverage, camera-derived pedestrian counts and brightness. **No safety score; not a safety claim.**

Flow: camera → YOLOv8n(person) + OpenCV brightness → aggregates (data/cache) → FastAPI ← OSRM, OSM/Overpass cache → route analysis → React + Leaflet.

Privacy: frames processed in memory and discarded; only timestamp, count, rolling average, brightness persisted. No faces, identities, tracking history, or LLM image input.
Activity labels (descriptive, not safety thresholds): quiet <2, steady 2–8, busy >8 people/frame average.
API: `GET /segments`, `GET /route?from=lat,lon&to=lat,lon`, `GET /cameras`, `GET /health`.
Limitations: pedestrian presence does not imply safety; OSM lighting is incomplete; camera coverage is limited; nearest-way matching (35 m) is approximate; real deployment needs permissions, a DPIA, and camera-operator agreements. Decision support, not a safety guarantee.
