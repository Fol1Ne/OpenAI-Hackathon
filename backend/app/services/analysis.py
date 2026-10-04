from .lighting import match_route, load_ways
from .camera import cameras

def analyse(route, ways):
    m = match_route(route["coords"], ways)
    live_names = {c["street"] for c in cameras() if c["source"] == "live" and c["status"] in ("collecting", "complete")}
    live = [s for s in m["streets"] if s in live_names]
    return {**route, **m, "streets_with_live_traffic": len(live), "total_streets": len(m["streets"]),
            "live_streets": live}

def pick(routes):
    fastest = min(routes, key=lambda r: r["minutes"])
    well = max(routes, key=lambda r: (r["pct_lit"], r["streets_with_live_traffic"], -r["minutes"]))
    return fastest, well
