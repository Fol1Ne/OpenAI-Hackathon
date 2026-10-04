"""Read aggregate camera metrics. Missing, failed or stale observations stay unknown."""
import datetime
import json
import math
import pathlib
import time

from .traffic import classify_activity

D = pathlib.Path(__file__).resolve().parents[1] / 'data'
METRICS = pathlib.Path(__file__).resolve().parents[3] / 'data/cache/camera_metrics.json'
STALE_SECONDS = 5


def _number(value, minimum=0, maximum=float('inf')):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and minimum <= value <= maximum


def _iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat() if _number(ts, maximum=253402300799) else None


def cameras():
    metadata = json.loads((D / 'cameras.json').read_text())
    try:
        metrics = json.loads(METRICS.read_text())
        if not isinstance(metrics, dict):
            metrics = {}
    except (OSError, ValueError):
        metrics = {}
    now = time.time()
    out = []
    for camera in metadata:
        metric = metrics.get(camera['id'], {})
        if not isinstance(metric, dict):
            metric = {}
        ts = metric.get('ts')
        valid = (metric.get('state') == 'observing' and _number(ts) and 0 <= now - ts <= STALE_SECONDS
                 and metric.get('source') in ('live', 'synthetic')
                 and _number(metric.get('passages_10min'))
                 and _number(metric.get('observed_seconds'), maximum=600)
                 and _number(metric.get('people_now'))
                 and _number(metric.get('brightness'), maximum=1))
        seconds = metric['observed_seconds'] if valid else 0
        complete = valid and metric.get('window_complete') is True and seconds >= 599.99
        source = metric['source'] if valid else 'unknown'
        status = 'complete' if complete else 'collecting' if valid else 'no_data'
        average = metric.get('rolling_average') if valid else None
        out.append({
            'id': camera['id'], 'street': camera['street'],
            'latitude': camera['latitude'], 'longitude': camera['longitude'],
            'location_note': camera.get('location_note', ''),
            'source': source, 'status': status,
            'people_now': metric['people_now'] if valid else None,
            'avg_people_30min': average if _number(average) else None,
            'brightness': metric['brightness'] if valid else None,
            'activity': classify_activity(average) if _number(average) else 'unknown',
            'updated': _iso(ts),
            'frame_url': f"/frames/{camera['id']}.jpg" if valid else None,
            'passages_10min': int(metric['passages_10min']) if valid else None,
            'observed_seconds': seconds, 'window_seconds': 600,
            'window_complete': bool(complete),
            'unavailable_reason': 'YouTube is requesting sign-in before this feed can be analysed.' if not valid and metric.get('error') == 'youtube_sign_in' else None,
            'needs_calibration': metric.get('state') == 'needs_calibration',
        })
    return out
