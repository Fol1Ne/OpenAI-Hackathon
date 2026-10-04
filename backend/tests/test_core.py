import os
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.services.traffic import classify_activity
from app.services.lighting import classify_lit, match_route
from app.services.analysis import pick
from app.services import explanation
c = TestClient(app)
Q = {"from": "53.3438,-6.2546", "to": "53.3392,-6.2600"}  # Trinity -> St Stephen's Green

def test_activity():
    assert classify_activity(1.2) == "quiet" and classify_activity(5.4) == "steady"
    assert classify_activity(12.1) == "busy" and classify_activity(None) == "unknown"
def test_unknown_stays_unknown():
    assert classify_lit(None) == "unknown"
    r = match_route([[0, 0], [0, 0.001]], [{"name": "X", "lit": "yes", "coords": [[1, 1], [1, 1.001]]}])
    assert r["pct_unknown"] == 100 and r["pct_lit"] == 0
def test_selection_and_tiebreak():
    a = {"minutes": 12, "pct_lit": 60, "streets_with_live_traffic": 1}; b = {"minutes": 15, "pct_lit": 95, "streets_with_live_traffic": 0}
    d = {"minutes": 16, "pct_lit": 95, "streets_with_live_traffic": 2}
    assert pick([a, b]) == (a, b) and pick([a, b, d])[1] is d
def test_demo_route_deterministic_and_comparison():
    r1, r2 = c.get("/route", params=Q).json(), c.get("/route", params=Q).json()
    assert r1 == r2 and r1["sources"]["routing"] == "demo" and r1["sources"]["lighting"] == "demo"
    assert r1["well_lit"]["pct_lit"] > r1["fastest"]["pct_lit"] and r1["fastest"]["minutes"] < r1["well_lit"]["minutes"]
    assert r1["fastest"]["pct_unknown"] > 0 and "longer" in r1["explanation"]
def test_cameras_labelled_demo_never_live():
    cams = c.get("/cameras").json()
    assert all(x["source"] == "demo" and x["status"] == "DEMO CAMERA" for x in cams)
def test_status_and_segments():
    s = c.get("/status").json()
    assert s["mode"] == "demo" and s["ai"] == "disabled" and s["cameras"] == "demo"
    assert c.get("/segments").status_code == 200
def test_osrm_failure_falls_back_to_demo(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False); monkeypatch.setattr(config, "OSRM_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "OVERPASS_URL", "http://127.0.0.1:1")
    r = c.get("/route", params=Q); assert r.status_code == 200 and r.json()["sources"]["routing"] == "demo"
def test_ai_failure_uses_template(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_AI", True); monkeypatch.setattr(config, "OPENAI_API_KEY", "bad")
    monkeypatch.setattr(explanation.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("net")))
    t, src = explanation.explain({"minutes": 12, "pct_lit": 60}, {"minutes": 15, "pct_lit": 95})
    assert src == "template" and "3 minutes longer" in t
def test_no_unsafe_wording():
    txt = c.get("/route", params=Q).text.lower().replace("not a safety guarantee", "")
    assert "safest" not in txt and "unsafe" not in txt and "safety score" not in txt
