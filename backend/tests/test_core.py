import os
import pytest
import httpx
from app.services import routing, analysis
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
@pytest.fixture(autouse=True)
def offline_routing(monkeypatch):
    monkeypatch.setattr(config, 'DEMO_MODE', True)
    monkeypatch.setattr(config, 'ENABLE_AI', False)
    monkeypatch.setattr(routing.OSRMRoutingService, 'routes', lambda self, a, b: [
        {'coords': [a, [53.3416, -6.2569], b], 'minutes': 10, 'distance_m': 800, 'street_names': ['Nassau Street', 'Kildare Street']},
        {'coords': [a, [53.3425, -6.2600], b], 'minutes': 14, 'distance_m': 1000, 'street_names': ['Grafton Street']},
    ])


def test_selection_ignores_lighting_and_traffic():
    a = {'minutes': 12, 'pct_lit': 0, 'streets_with_live_traffic': 0}
    b = {'minutes': 15, 'pct_lit': 100, 'streets_with_live_traffic': 5}
    assert pick([a, b]) == (a, a)


def test_route_uses_fastest_with_compatibility_aliases():
    response = c.get('/route', params=Q)
    assert response.status_code == 200
    result = response.json()
    assert result['route']['minutes'] == 10
    assert result['route'] == result['fastest'] == result['well_lit']
    assert result['sources']['routing'] == 'osrm-foot'
    assert result['route']['coords'][0] == [53.3438, -6.2546]
    assert result['route']['coords'][-1] == [53.3392, -6.26]

def test_cameras_without_metrics_are_unknown(monkeypatch, tmp_path):
    from app.services import camera
    monkeypatch.setattr(camera, "METRICS", tmp_path / "missing.json")
    cams = c.get("/cameras").json()
    assert len(cams) == 3
    assert all(x["source"] == "unknown" and x["status"] == "no_data" and x["passages_10min"] is None for x in cams)
def test_status_and_segments(monkeypatch, tmp_path):
    from app.services import camera
    monkeypatch.setattr(camera, "METRICS", tmp_path / "missing.json")
    s = c.get("/status").json()
    assert s["mode"] == "demo" and s["ai"] == "disabled" and s["cameras"] == "no_data"
    assert c.get("/segments").status_code == 200
def test_routing_failure_returns_retry_error(monkeypatch):
    def fail(*args):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(routing.OSRMRoutingService, 'routes', fail)
    response = c.get('/route', params=Q)
    assert response.status_code == 503
    assert 'Try again' in response.json()['detail']

def test_ai_failure_uses_template(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_AI", True); monkeypatch.setattr(config, "OPENAI_API_KEY", "bad")
    monkeypatch.setattr(explanation.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("net")))
    t, src = explanation.explain({"minutes": 12, "pct_lit": 60}, {"minutes": 15, "pct_lit": 95})
    assert src == "template" and "3 minutes longer" in t
def test_no_unsafe_wording():
    txt = c.get("/route", params=Q).text.lower().replace("not a safety guarantee", "")
    assert "safest" not in txt and "unsafe" not in txt and "safety score" not in txt


def test_camera_observation_states(monkeypatch, tmp_path):
    import json
    from app.services import camera
    path = tmp_path / 'metrics.json'
    monkeypatch.setattr(camera, 'METRICS', path)
    monkeypatch.setattr(camera.time, 'time', lambda: 1000)
    metric = {'ts': 998, 'state': 'observing', 'source': 'live', 'passages_10min': 18,
              'observed_seconds': 180, 'window_complete': False, 'people_now': 2,
              'brightness': .4, 'rolling_average': 2.5}
    path.write_text(json.dumps({'cam1': metric}))
    result = c.get('/cameras').json()[0]
    assert result['status'] == 'collecting' and result['passages_10min'] == 18
    assert result['observed_seconds'] == 180 and result['source'] == 'live'
    metric.update(observed_seconds=600, window_complete=True)
    path.write_text(json.dumps({'cam1': metric}))
    assert c.get('/cameras').json()[0]['status'] == 'complete'
    metric['ts'] = 994
    path.write_text(json.dumps({'cam1': metric}))
    result = c.get('/cameras').json()[0]
    assert result['status'] == 'no_data' and result['passages_10min'] is None
    assert result['updated'] is not None
    metric.update(ts=998, state='no_data')
    path.write_text(json.dumps({'cam1': metric}))
    assert c.get('/cameras').json()[0]['passages_10min'] is None


def test_replay_is_simulated_and_not_route_live_coverage(monkeypatch, tmp_path):
    import json
    from app.services import camera, analysis
    path = tmp_path / 'metrics.json'
    monkeypatch.setattr(camera, 'METRICS', path)
    monkeypatch.setattr(camera.time, 'time', lambda: 1000)
    path.write_text(json.dumps({'cam1': {'ts': 999, 'state': 'observing', 'source': 'synthetic',
        'passages_10min': 0, 'observed_seconds': 600, 'window_complete': True,
        'people_now': 0, 'brightness': .5, 'rolling_average': 0}}))
    result = c.get('/cameras').json()[0]
    assert result['source'] == 'synthetic' and result['passages_10min'] == 0
    monkeypatch.setattr(analysis, 'match_route', lambda *_: {'streets': ['Temple Bar']})
    assert analysis.analyse({'coords': []}, [])['streets_with_live_traffic'] == 0


def test_corrupt_camera_metrics_are_unknown(monkeypatch, tmp_path):
    from app.services import camera
    path = tmp_path / 'metrics.json'
    monkeypatch.setattr(camera, 'METRICS', path)
    for contents in ['{', '[]', '{"cam1": null}', '{"cam1": {"state": "observing", "ts": "bad"}}']:
        path.write_text(contents)
        assert c.get('/cameras').json()[0]['passages_10min'] is None


def test_route_notices_only_for_nearby_current_observations():
    cam = {'id': 'cam1', 'street': 'Temple Bar', 'latitude': 53.3455, 'longitude': -6.2643,
           'source': 'live', 'status': 'complete', 'window_complete': True,
           'passages_10min': 0, 'people_now': 0, 'updated': '2026-10-04T22:00:00Z'}
    near = {'coords': [[53.3455, -6.265], [53.3455, -6.263]], 'minutes': 1, 'distance_m': 100}
    route = analysis.analyse(near, [], [cam])
    assert route['camera_ids'] == ['cam1'] and len(route['traffic_warnings']) == 1
    assert 'last 10 minutes' in route['traffic_warnings'][0]['message']
    for change in [{'source': 'synthetic'}, {'source': 'unknown', 'status': 'no_data'},
                   {'status': 'collecting', 'window_complete': False, 'people_now': 3}]:
        assert analysis.analyse(near, [], [{**cam, **change}])['traffic_warnings'] == []
    partial = {**cam, 'status': 'collecting', 'window_complete': False}
    assert 'latest camera frame' in analysis.analyse(near, [], [partial])['traffic_warnings'][0]['message']
    far = {**near, 'coords': [[53.34, -6.27], [53.34, -6.26]]}
    assert analysis.analyse(far, [], [cam])['camera_ids'] == []


@pytest.mark.parametrize('point', ['nan,-6.26', '91,-6.26', '53.34,181', 'bad'])
def test_invalid_route_points(point):
    assert c.get('/route', params={'from': point, 'to': Q['to']}).status_code == 400


def test_equal_route_points():
    assert c.get('/route', params={'from': Q['from'], 'to': Q['from']}).status_code == 400
