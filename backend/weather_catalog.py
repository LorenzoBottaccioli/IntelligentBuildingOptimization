"""Where to find a weather file: the EnergyPlus weather site and PVGIS.

EnergyPlus publishes its weather data (3000+ locations, typical-year files) on energyplus.net/weather. The page is
drawn from one JSON file, https://energyplus.net/assets/weather/master.geojson (location, coordinates, and the
address of the .epw on S3). That file is not a documented API, so it is read defensively: cached on disk, a
stale copy is used when the site cannot be reached, and a download is only accepted for an address on the
EnergyPlus bucket.

PVGIS (European Commission JRC) builds a typical meteorological year for any point and can return it as EPW:
    https://re.jrc.ec.europa.eu/api/tmy?lat=..&lon=..&outputformat=epw
"""

import json
import math
import os
import re
import time

import requests

CATALOG_URL = 'https://energyplus.net/assets/weather/master.geojson'
CACHE_FILE = os.path.join('instance', 'energyplus_weather_catalog.json')
CACHE_SECONDS = 7 * 24 * 3600
ALLOWED_HOST = 'https://energyplus-weather.s3.amazonaws.com/'
PVGIS_URL = 'https://re.jrc.ec.europa.eu/api/tmy'
MAX_EPW_BYTES = 25 * 1024 * 1024

_memory = {'loaded': 0.0, 'items': None}


class CatalogError(RuntimeError):
    """A weather service did not answer as expected; the message is shown to the student."""


def _href(anchor):
    m = re.search(r'href=([^\s>]+)', anchor or '')
    return m.group(1).strip('"\'') if m else None


def _parse(geojson):
    items = []
    for feat in geojson.get('features', []):
        p = feat.get('properties', {})
        epw = _href(p.get('epw'))
        coords = (feat.get('geometry') or {}).get('coordinates') or []
        if not epw or not epw.startswith(ALLOWED_HOST) or len(coords) < 2:
            continue
        title = p.get('title') or os.path.basename(epw)[:-4]
        parts = epw[len(ALLOWED_HOST):].split('/')
        country = parts[1] if len(parts) > 2 else ''
        kind = title.rsplit('_', 1)[-1].split('.')[-1] if '_' in title else ''
        items.append({
            'id': title, 'name': re.sub(r'^[A-Z]{3}_', '', title), 'country': country,
            'region': parts[0].replace('_', ' ') if parts else '', 'kind': kind,
            'latitude': coords[1], 'longitude': coords[0], 'epw': epw,
            'folder': _href(p.get('dir')),
        })
    return items


def load(force=False):
    """The catalogue: memory, then the disk cache, then the site (a stale cache beats no answer)."""
    now = time.time()
    if _memory['items'] and not force and now - _memory['loaded'] < CACHE_SECONDS:
        return _memory['items']
    cached = None
    if os.path.isfile(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
        except (OSError, ValueError):
            cached = None
    if cached and not force and now - cached.get('fetched', 0) < CACHE_SECONDS:
        _memory.update(loaded=cached['fetched'], items=cached['items'])
        return cached['items']
    try:
        r = requests.get(CATALOG_URL, timeout=60, headers={'User-Agent': 'smart-building-platform'})
        r.raise_for_status()
        items = _parse(r.json())
        if not items:
            raise ValueError('no locations in the file')
    except (requests.RequestException, ValueError) as exc:
        if cached:
            _memory.update(loaded=now, items=cached['items'])
            return cached['items']
        raise CatalogError(f'The EnergyPlus weather list could not be read ({exc}).')
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump({'fetched': now, 'items': items}, f)
    _memory.update(loaded=now, items=items)
    return items


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def search(items, query='', latitude=None, longitude=None, limit=25):
    """Locations whose name contains every word of `query`; nearest first when a point is given."""
    words = [w for w in re.split(r'\W+', (query or '').lower()) if w]
    hits = []
    for it in items:
        hay = f"{it['id']} {it['country']} {it['region']}".lower().replace('_', ' ').replace('.', ' ')
        if all(w in hay for w in words):
            hit = dict(it)
            if latitude is not None and longitude is not None:
                hit['distance_km'] = round(distance_km(latitude, longitude, it['latitude'], it['longitude']), 1)
            hits.append(hit)
    if latitude is not None and longitude is not None:
        hits.sort(key=lambda h: h['distance_km'])
    else:
        hits.sort(key=lambda h: h['id'])
    return {'total': len(hits), 'results': hits[:limit]}


def fetch_epw(url, timeout=120):
    """The text of an EPW at `url`; only addresses of the EnergyPlus bucket are fetched."""
    if not url.startswith(ALLOWED_HOST) or not url.lower().endswith('.epw'):
        raise CatalogError('That is not a file of the EnergyPlus weather list.')
    try:
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        body = b''
        for chunk in r.iter_content(1 << 20):
            body += chunk
            if len(body) > MAX_EPW_BYTES:
                raise CatalogError('The file is larger than 25 MB: not an EPW.')
    except requests.RequestException as exc:
        raise CatalogError(f'Download failed: {exc}')
    return body.decode('utf-8', errors='replace')


def fetch_pvgis(latitude, longitude, startyear=None, endyear=None, timeout=180):
    """PVGIS typical meteorological year at a point, as EPW text."""
    params = {'lat': latitude, 'lon': longitude, 'outputformat': 'epw'}
    if startyear:
        params['startyear'] = int(startyear)
    if endyear:
        params['endyear'] = int(endyear)
    try:
        r = requests.get(PVGIS_URL, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise CatalogError(f'PVGIS is not reachable from the backend: {exc}')
    if r.status_code == 429:
        raise CatalogError('PVGIS rate limit reached: wait a moment and try again.')
    text = r.text
    if r.status_code != 200 or not text.startswith('LOCATION'):
        reason = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text))[:200]
        raise CatalogError(f'PVGIS did not return a weather file (HTTP {r.status_code}): {reason}')
    return text
