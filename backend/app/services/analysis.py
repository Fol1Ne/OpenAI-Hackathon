"""Select by journey time; attach observations without changing the route."""
from .lighting import match_route, _dist
from .camera import cameras


def route_cameras(coords, camera_list):
    # Only observations near the route geometry apply. A road name alone cannot
    # make one camera represent every segment of a long road.
    matched = []
    for camera in camera_list:
        if camera['latitude'] is None or camera['longitude'] is None:
            continue
        point = [camera['latitude'], camera['longitude']]
        if any(_dist(point, a, b, point[0]) <= 15 for a, b in zip(coords, coords[1:])):
            matched.append(camera)
    return matched


def analyse(route, ways, camera_list=None):
    facts = match_route(route['coords'], ways)
    observed = route_cameras(route['coords'], cameras() if camera_list is None else camera_list)
    live = [c for c in observed if c['source'] == 'live' and c['status'] in ('collecting', 'complete')]
    warnings = [{
        'camera_id': c['id'], 'street': c['street'], 'updated': c['updated'],
        'message': (f"{c['street']}: no pedestrian passages recorded at the camera-covered section in the last 10 minutes."
                    if c.get('window_complete') and c.get('passages_10min') == 0 else
                    f"{c['street']}: no pedestrians detected in the latest camera frame at the camera-covered section."),
    } for c in live if (c.get('window_complete') and c.get('passages_10min') == 0) or c.get('people_now') == 0]
    return {**route, **facts, 'streets_with_live_traffic': len({c['street'] for c in live}),
            'total_streets': len(route.get('street_names') or facts['streets']),
            'live_streets': sorted({c['street'] for c in live}),
            'camera_ids': [c['id'] for c in observed], 'traffic_warnings': warnings}


def pick(routes):
    fastest = min(routes, key=lambda route: (route['minutes'], route.get('distance_m', 0)))
    # Preserve the old response keys for clients; both now refer to the same route.
    return fastest, fastest
