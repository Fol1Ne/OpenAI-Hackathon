"""Fetch an A-to-B pedestrian route. Unavailable routing never invents a path."""
import httpx
from .. import config


class RoutingUnavailable(Exception):
    pass


class OSRMRoutingService:
    def routes(self, a, b):
        url = f"{config.OSRM_URL.rstrip('/')}/route/v1/foot/{a[1]},{a[0]};{b[1]},{b[0]}"
        response = httpx.get(url, params={
            'alternatives': 'false', 'steps': 'true', 'overview': 'full',
            'geometries': 'geojson', 'radiuses': '50;50',
        }, timeout=8)
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 'Ok':
            raise RoutingUnavailable('No walking route found for these points')
        routes = []
        for route in data.get('routes', []):
            coords = [[y, x] for x, y in route['geometry']['coordinates']]
            if len(coords) < 2:
                continue
            routes.append({'coords': coords, 'minutes': round(route['duration'] / 60, 1),
                           'distance_m': round(route['distance']),
                           'street_names': sorted({step['name'] for leg in route.get('legs', [])
                               for step in leg.get('steps', []) if step.get('name')})})
        return routes


def get_routes(a, b):
    try:
        routes = OSRMRoutingService().routes(a, b)
        if not routes:
            raise RoutingUnavailable('No walking route found for these points')
        return routes, 'osrm-foot'
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise RoutingUnavailable('Walking routing is unavailable. Try again shortly.') from error
