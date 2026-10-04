"""LightingService: OverpassLightingService (live, updates cache) -> cached OSM -> CachedLightingService (bundled demo fixture)."""
import json, math, pathlib, httpx
from .. import config
ROOT = pathlib.Path(__file__).resolve().parents[3] / "data"
CACHE, DEMO = ROOT / "cache" / "overpass.json", ROOT / "lighting" / "dublin_demo_lighting.json"

def classify_lit(tag): return {"yes": "yes", "no": "no"}.get(tag, "unknown")  # missing stays unknown

def demo_data(): return json.loads(DEMO.read_text())
def demo_ways():
    d = demo_data(); n = d["nodes"]
    return [{"id": w["id"], "name": w["name"], "lit": w["lit"], "coords": [n[w["a"]], n[w["b"]]]} for w in d["ways"]]

def fetch_overpass(bbox="53.33,-6.28,53.35,-6.24"):
    q = f'[out:json][timeout:25];way["highway"~"footway|pedestrian|residential|service|primary|secondary|tertiary|unclassified|living_street"]({bbox});out geom tags;'
    r = httpx.post(config.OVERPASS_URL, data={"data": q}, timeout=30); r.raise_for_status()
    ways = [{"id": f"w{e['id']}", "name": e["tags"].get("name", "Unnamed"), "lit": classify_lit(e["tags"].get("lit")),
             "coords": [[g["lat"], g["lon"]] for g in e["geometry"]]} for e in r.json()["elements"] if "geometry" in e]
    CACHE.parent.mkdir(parents=True, exist_ok=True); CACHE.write_text(json.dumps(ways)); return ways

def load_ways():
    """Returns (ways, source) with source in {'osm-live','osm-cached','demo'}. Never raises."""
    if config.DEMO_MODE: return demo_ways(), "demo"   # deterministic, aligned with demo routes
    try: return fetch_overpass(), "osm-live"
    except Exception: pass
    try:
        if CACHE.exists(): return json.loads(CACHE.read_text()), "osm-cached"
    except Exception: pass
    return demo_ways(), "demo"

def _xy(p, lat0): return (p[1] * 111320 * math.cos(math.radians(lat0)), p[0] * 110540)
def _dist(p, a, b, lat0):
    px, py = _xy(p, lat0); ax, ay = _xy(a, lat0); bx, by = _xy(b, lat0)
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
def seg_len(a, b):
    ax, ay = _xy(a, a[0]); bx, by = _xy(b, a[0]); return math.hypot(ax - bx, ay - by)

def match_route(coords, ways, max_m=35):
    out = {"yes": 0.0, "no": 0.0, "unknown": 0.0}; streets = set()
    for a, b in zip(coords, coords[1:]):
        L = seg_len(a, b); mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; best = (1e9, None)
        for w in ways:
            for p, q in zip(w["coords"], w["coords"][1:]):
                d = _dist(mid, p, q, mid[0])
                if d < best[0]: best = (d, w)
        if best[1] is not None and best[0] <= max_m: out[best[1]["lit"]] += L; streets.add(best[1]["name"])
        else: out["unknown"] += L
    tot = sum(out.values()) or 1
    return {"lit_length": out["yes"], "unlit_length": out["no"], "unknown_length": out["unknown"],
            "pct_lit": round(100 * out["yes"] / tot), "pct_unlit": round(100 * out["no"] / tot),
            "pct_unknown": round(100 * out["unknown"] / tot), "streets": sorted(streets)}
