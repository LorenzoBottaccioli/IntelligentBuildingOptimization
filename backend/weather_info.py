"""Which weather file the session runs on, in a line the Control room can show.

The session holds ONE weather file, the .epw in uploads/ (weather_editor.use_in_session replaces it and keeps the old
one in the library). The annual EnergyPlus run, the probe and a new FMU export read that file; the exported FMUs
carry a copy of it, replaced whenever a file is put in use. Read from the text of the file (header and year column),
cached by modification time: the Control room asks every second or so.
"""

import glob
import os
import threading

_lock = threading.Lock()
_cache = {}


def _read(path):
    years = set()
    with open(path, encoding='latin-1') as handle:
        lines = handle.read().splitlines()
    head = lines[0].split(',') if lines else []
    for line in lines[8:]:
        cell = line.split(',', 1)[0].strip()
        if cell.isdigit():
            years.add(int(cell))
    def num(i):
        try:
            return float(head[i])
        except (IndexError, ValueError):
            return None
    years = sorted(years)
    return {
        'file': os.path.basename(path),
        'city': head[1].strip() if len(head) > 1 else '',
        'country': head[3].strip() if len(head) > 3 else '',
        'source': head[4].strip() if len(head) > 4 else '',
        'latitude': num(6), 'longitude': num(7),
        'years': years,
        # One year in the data rows: a real year (Open-Meteo, a station year). Several: a typical year assembled from months.
        'kind': 'real' if len(years) == 1 else 'typical',
        'hours': max(0, len(lines) - 8),
    }


def describe(path):
    """What `_read` finds in one file, read again only when the file changes."""
    stamp = (os.path.getmtime(path), os.path.getsize(path))
    with _lock:
        hit = _cache.get(path)
        if hit is None or hit[0] != stamp:
            hit = (stamp, _read(path))
            _cache[path] = hit
        return dict(hit[1])


def info(upload_folder='uploads'):
    """The weather file of the session ({} when there is none), and how many other .epw sit beside it."""
    found = sorted(glob.glob(os.path.join(upload_folder, '*.epw')))
    if not found:
        return {}
    value = describe(found[0])
    value['others'] = len(found) - 1
    return value
