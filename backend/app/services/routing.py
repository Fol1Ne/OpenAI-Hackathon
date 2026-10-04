"""RoutingService: OSRMRoutingService (public, no key) -> DemoRoutingService (deterministic fixture graph)."""
import httpx
from .. import config
from .lighting import seg_len, demo_data

def _mins(d): return round(d / 1.35 / 60, 1)  # ~4.9 km/h walking

class OSRMRoutingService:
    def routes(self, a, b):
        url = f"{config.OSRM_URL}/route/v1/foot/{a[1]},{a[0]};{b[1]},{b[0]}"
        r = httpx.get(url, params={"alternatives": "true", "steps": "true", "overview": "full", "geometries": "geojson"}, timeout=8)
        r.raise_for_status()
        return [{"coords": [[y, x] for x, y in o["geometry"]["coordinates"]], "minutes": round(o["duration"] / 60, 1),
                 "distance_m": round(o["distance"])} for o in r.json()["routes"]]

class DemoRoutingService:
    """Enumerates simple paths over the tiny demo street graph; deterministic. Click points snap to the nearest demo node."""
    def routes(self, a, b):
        d = demo_data(); nodes = d["nodes"]
        near = lambda p: min(nodes, key=lambda k: seg_len(p, nodes[k]))
        s, t = near(a), near(b)
        adj = {}
        for w in d["ways"]:
            L = seg_len(nodes[w["a"]], nodes[w["b"]]); adj.setdefault(w["a"], []).append((w["b"], L)); adj.setdefault(w["b"], []).append((w["a"], L))
        paths = []
        def dfs(n, path, L):
            if n == t: paths.append((L, path)); return
            for m, l in sorted(adj.get(n, [])):
                if m not in path: dfs(m, path + [m], L + l)
        dfs(s, [s], 0.0)
        paths.sort(key=lambda x: (x[0], x[1]))
        out = []
        for L, p in paths[:3]:
            c = [list(a)] if a != nodes[s] else []
            c += [nodes[k] for k in p] + ([list(b)] if b != nodes[t] else [])
            dist = sum(seg_len(x, y) for x, y in zip(c, c[1:])); out.append({"coords": c, "minutes": _mins(dist), "distance_m": round(dist)})
        if not out:  # start == destination node
            c = [list(a), list(b)]; dist = seg_len(a, b); out = [{"coords": c, "minutes": _mins(dist), "distance_m": round(dist)}]
        return out

def get_routes(a, b):
    """Returns (routes, source) source in {'osrm','demo'}. DEMO_MODE uses the deterministic demo graph; otherwise OSRM with automatic demo fallback."""
    if not config.DEMO_MODE:
        try:
            rs = OSRMRoutingService().routes(a, b)
            if rs: return rs, "osrm"
        except Exception: pass
    return DemoRoutingService().routes(a, b), "demo"
