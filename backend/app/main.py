import json, pathlib
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from . import config
from .services import camera, lighting, routing, analysis, explanation
from .services.traffic import classify_activity

app = FastAPI(title="Safe Routes Home")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"ok": True, "demo_mode": config.DEMO_MODE}

@app.get("/status")
def status():
    cs = camera.cameras()
    return {"mode": "demo" if config.DEMO_MODE else "live", "routing": "demo" if config.DEMO_MODE else "osrm (demo fallback)",
            "lighting": lighting.load_ways()[1], "cameras": "live" if any(c["source"] == "live" for c in cs) else "demo",
            "ai": "openai" if config.ENABLE_AI and config.OPENAI_API_KEY else "disabled"}

@app.get("/segments")
def segments():
    ways, src = lighting.load_ways()
    cams = {c["street"]: c for c in camera.cameras()}
    out = []
    for w in ways:
        c = cams.get(w["name"])
        live = bool(c)
        out.append({"id": w["id"], "name": w["name"], "coords": w["coords"], "lit": w["lit"],
                    "foot_traffic": classify_activity(c["avg_people_30min"]) if live else "unknown",
                    "avg_people_30min": c["avg_people_30min"] if live else None,
                    "brightness": c["brightness"] if live else None,
                    "source": c["source"] if live else ("live" if src == "osm-live" else "osm" if src.startswith("osm") else "demo")})
    return out

@app.get("/cameras")
def cams(): return camera.cameras()

def _parse(s):
    try: a, b = s.split(","); return [float(a), float(b)]
    except Exception: raise HTTPException(400, "Use lat,lon")

@app.get("/route")
def get_route(from_: str = Query(alias="from"), to: str = Query()):
    routes, rsrc = routing.get_routes(_parse(from_), _parse(to))
    ways, lsrc = lighting.load_ways()
    an = [analysis.analyse(r, ways) for r in routes]
    fast, well = analysis.pick(an); text, esrc = explanation.explain(fast, well)
    return {"fastest": fast, "well_lit": well, "routes_available": len(an),
            "explanation": text,
            "sources": {"routing": rsrc, "lighting": lsrc, "explanation": esrc, "demo_mode": config.DEMO_MODE},
            "disclaimer": "Decision support, not a safety guarantee. Data coverage varies by location and time."}
