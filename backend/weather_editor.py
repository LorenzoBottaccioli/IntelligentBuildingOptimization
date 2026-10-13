"""Weather page: the session's EPW, a library of weather files, edits, and annual files from Open-Meteo.

    GET    /weather/config             models, editable variables, last complete year
    GET    /weather/files              the session weather file and the library
    GET    /weather/inspect?source=    summary of one file;  POST with edits adds the edited summary
    POST   /weather/save               write the edited file to the library (and optionally use it)
    POST   /weather/upload             put an EPW in the library
    GET    /weather/download?source=
    DELETE /weather/files/<name>
    POST   /weather/use                make a file the session's weather
    GET    /weather/geocode?q=         places, from Open-Meteo's geocoding
    POST   /weather/openmeteo          build the EPW of one year and keep it in the library

`source` is 'session' (the EPW in uploads/) or 'lib:<file name>' (user_files/weather_library/).
The library lives in user_files/, so it travels with a saved session and is emptied by Reset session.
"""

import datetime as dt
import glob
import os
import re
import shutil
import subprocess
import threading

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

import idf_session
import weather_catalog as wc
import weather_epw as we
import weather_info

weather_bp = Blueprint('weather', __name__)

UPLOAD_FOLDER = 'uploads'
LIBRARY = os.path.join('user_files', 'weather_library')

_lock = threading.RLock()


class SourceError(Exception):
    def __init__(self, message, status=404):
        super().__init__(message)
        self.status = status


def _session_path():
    found = sorted(glob.glob(os.path.join(UPLOAD_FOLDER, '*.epw')))
    return found[0] if found else None


def _lib_path(name):
    name = secure_filename(name or '')
    if not name.lower().endswith('.epw'):
        raise SourceError('A weather file name must end in .epw', 400)
    return os.path.join(LIBRARY, name)


def resolve(source):
    """The path a `source` names, or SourceError."""
    if source == 'session':
        path = _session_path()
        if not path:
            raise SourceError('The session has no weather file yet: upload a model and an EPW first.')
        return path
    if source and source.startswith('lib:'):
        path = _lib_path(source[4:])
        if not os.path.isfile(path):
            raise SourceError(f'{source[4:]} is not in the weather library.')
        return path
    raise SourceError('Unknown weather source.', 400)


def _header(path):
    """(city, country, latitude, longitude) from the LOCATION line, without reading the whole file."""
    try:
        with open(path, 'r', errors='replace') as f:
            parts = f.readline().strip().split(',')
        return {'city': parts[1], 'country': parts[3], 'latitude': float(parts[6]), 'longitude': float(parts[7])}
    except (OSError, IndexError, ValueError):
        return {'city': '', 'country': '', 'latitude': None, 'longitude': None}


def _years_of(path):
    """The years in the data rows and whether they are one real year or a typical year (`yearKind`: `kind` is
    session or library). Empty when the file cannot be read."""
    try:
        d = weather_info.describe(path)
        return {'years': d['years'], 'yearKind': d['kind']}
    except OSError:
        return {'years': [], 'yearKind': ''}


def _entry(path, source, kind):
    st = os.stat(path)
    return {'id': source, 'name': os.path.basename(path), 'kind': kind, 'size': st.st_size,
            'modified': dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
            **_header(path), **_years_of(path)}


def _round(value, digits=2):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: _round(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v, digits) for v in value]
    return value


def _summary(path):
    return _round(we.summary(we.read(path)))


def _error(message, status):
    return jsonify({'success': False, 'error': message}), status


TUTORIALS = os.path.join('surrogate_notebooks', 'tutorials')


def point_tutorials_at(path, name):
    """The tutorial notebooks read the weather beside them (`epw_file = '<name>.epw'`): copy the file there and
    rewrite that line. Returns the notebooks changed."""
    import nbformat
    changed = []
    if not os.path.isdir(TUTORIALS):
        return changed
    shutil.copyfile(path, os.path.join(TUTORIALS, name))
    pattern = re.compile(r"^(epw_file\s*=\s*)(?P<q>['\"])[^'\"]+\.epw(?P=q)", re.MULTILINE)
    for nb_path in sorted(glob.glob(os.path.join(TUTORIALS, '*.ipynb'))):
        nb = nbformat.read(nb_path, as_version=4)
        hit = False
        for cell in nb.cells:
            if cell.cell_type == 'code':
                new = pattern.sub(lambda m: f"{m.group(1)}'{name}'", cell.source)
                if new != cell.source:
                    cell.source, hit = new, True
        if hit:
            nbformat.write(nb, nb_path)
            changed.append(os.path.basename(nb_path))
    return changed


def use_in_session(path, name, tutorials=False):
    """Make `path` the session's weather: uploads/, the exported FMUs, the student's problem notebook."""
    from model_converter import replace_weather_in_all_fmus
    name = secure_filename(name)
    with _lock:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        dest = os.path.join(UPLOAD_FOLDER, name)
        staged = dest + '.new'
        shutil.copyfile(path, staged)
        kept = None
        for old in glob.glob(os.path.join(UPLOAD_FOLDER, '*.epw')):
            # The file the session had is not lost: it goes to the library (unless it is the same file).
            library_copy = os.path.join(LIBRARY, os.path.basename(old))
            if os.path.abspath(old) != os.path.abspath(dest) and not os.path.exists(library_copy):
                os.makedirs(LIBRARY, exist_ok=True)
                shutil.copyfile(old, library_copy)
                kept = os.path.basename(old)
            os.remove(old)
        os.replace(staged, dest)
        os.makedirs('user_files', exist_ok=True)
        shutil.copyfile(dest, os.path.join('user_files', 'weather.epw'))
        fmus, fmu_errors = replace_weather_in_all_fmus(os.path.join('user_files', 'weather.epw'))
        notebook = None
        if idf_session.has_model():
            idf_name = os.path.basename(idf_session.working_path())
            run = subprocess.run(['python', 'inject_data.py', idf_name, name], capture_output=True, text=True,
                                 timeout=120)
            notebook = run.returncode == 0
        tutorial_notebooks = point_tutorials_at(dest, name) if tutorials else None
    return {'epw': name, 'fmus': fmus, 'fmu_errors': fmu_errors, 'notebook': notebook, 'kept': kept,
            'tutorials': tutorial_notebooks}


# ---------------------------------------------------------------------------
@weather_bp.route('/config', methods=['GET'])
def config():
    last = dt.date.today().year - 1
    return jsonify({
        'last_year': last,
        'models': [{'id': k, **v} for k, v in we.MODELS.items()],
        'variables': [{'id': k, **v} for k, v in we.VARIABLES.items()],
        'operations': list(we.OPERATIONS),
    })


@weather_bp.route('/files', methods=['GET'])
def files():
    out = []
    session = _session_path()
    if session:
        out.append(_entry(session, 'session', 'session'))
    if os.path.isdir(LIBRARY):
        for p in sorted(glob.glob(os.path.join(LIBRARY, '*.epw'))):
            out.append(_entry(p, 'lib:' + os.path.basename(p), 'library'))
    return jsonify({'files': out})


@weather_bp.route('/inspect', methods=['GET', 'POST'])
def inspect():
    body = request.get_json(silent=True) or {}
    source = request.args.get('source') or body.get('source')
    try:
        path = resolve(source)
        epw = we.read(path)
        result = {'success': True, 'source': source, 'name': os.path.basename(path),
                  'base': _round(we.summary(epw))}
        if request.method == 'POST' and (body.get('location') or body.get('adjustments')):
            result['done'] = we.apply_edits(epw, body.get('location'), body.get('adjustments'))
            result['edited'] = _round(we.summary(epw))
        return jsonify(result)
    except SourceError as exc:
        return _error(str(exc), exc.status)
    except (we.EditError, we.EpwReadError) as exc:
        return _error(str(exc), 400)


@weather_bp.route('/series', methods=['GET', 'POST'])
def series():
    """Hourly values of a file for the chart; a POST with edits also returns the edited values."""
    body = request.get_json(silent=True) or {}
    source = request.args.get('source') or body.get('source')
    try:
        epw = we.read(resolve(source))
        result = {'success': True, 'base': we.hourly(epw)}
        if request.method == 'POST' and (body.get('location') or body.get('adjustments')):
            we.apply_edits(epw, body.get('location'), body.get('adjustments'))
            result['edited'] = {k: v['values'] for k, v in we.hourly(epw)['vars'].items()}
        return jsonify(result)
    except SourceError as exc:
        return _error(str(exc), exc.status)
    except (we.EditError, we.EpwReadError) as exc:
        return _error(str(exc), 400)


@weather_bp.route('/save', methods=['POST'])
def save():
    body = request.get_json(silent=True) or {}
    try:
        path = resolve(body.get('source'))
        name = secure_filename(body.get('name') or '')
        if not name:
            return _error('Give the new file a name.', 400)
        if not name.lower().endswith('.epw'):
            name += '.epw'
        epw = we.read(path)
        done = we.apply_edits(epw, body.get('location'), body.get('adjustments'))
        os.makedirs(LIBRARY, exist_ok=True)
        dest = os.path.join(LIBRARY, name)
        if os.path.exists(dest) and not body.get('overwrite'):
            return _error(f'{name} already exists in the library: choose another name.', 409)
        if done:
            note = 'Edited in the platform: ' + '; '.join(done)
            old = str(epw.comments_2.comments_2 or '')
            epw.comments_2.comments_2 = (old + ' | ' + note.replace(',', ';'))[:2000]
        we.save(epw, dest)
        result = {'success': True, 'file': _entry(dest, 'lib:' + name, 'library'), 'done': done}
        if body.get('use'):
            result['used'] = use_in_session(dest, name, bool(body.get('tutorials')))
        return jsonify(result)
    except SourceError as exc:
        return _error(str(exc), exc.status)
    except (we.EditError, we.EpwReadError) as exc:
        return _error(str(exc), 400)


@weather_bp.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('epw')
    if not f or not f.filename.lower().endswith('.epw'):
        return _error('Choose a .epw file.', 400)
    name = secure_filename(f.filename)
    os.makedirs(LIBRARY, exist_ok=True)
    dest = os.path.join(LIBRARY, name)
    tmp = dest + '.part'
    f.save(tmp)
    try:
        we.read(tmp)          # refuse what cannot be edited, instead of listing a file that fails later
    except we.EpwReadError as exc:
        os.remove(tmp)
        return _error(str(exc), 400)
    os.replace(tmp, dest)
    return jsonify({'success': True, 'file': _entry(dest, 'lib:' + name, 'library')})


@weather_bp.route('/download', methods=['GET'])
def download():
    try:
        path = resolve(request.args.get('source'))
    except SourceError as exc:
        return _error(str(exc), exc.status)
    return send_file(os.path.abspath(path), as_attachment=True, download_name=os.path.basename(path))


@weather_bp.route('/files/<name>', methods=['DELETE'])
def delete(name):
    try:
        path = _lib_path(name)
    except SourceError as exc:
        return _error(str(exc), exc.status)
    if not os.path.isfile(path):
        return _error(f'{name} is not in the weather library.', 404)
    os.remove(path)
    return jsonify({'success': True})


@weather_bp.route('/use', methods=['POST'])
def use():
    body = request.get_json(silent=True) or {}
    try:
        path = resolve(body.get('source'))
        if body.get('source') == 'session':
            return _error('That already is the session weather.', 400)
        import direct_run
        from bms_api import _building_running
        if _building_running() or direct_run.is_active():
            return _error('The building or the annual run is running: stop it before changing the weather file.', 409)
        return jsonify({'success': True,
                        'used': use_in_session(path, os.path.basename(path), bool(body.get('tutorials')))})
    except SourceError as exc:
        return _error(str(exc), exc.status)
    except subprocess.TimeoutExpired:
        return _error('Updating the notebook took too long.', 500)


@weather_bp.route('/geocode', methods=['GET'])
def geocode():
    try:
        return jsonify({'success': True, 'places': we.geocode(request.args.get('q', ''))})
    except we.OpenMeteoError as exc:
        return _error(str(exc), 502)


@weather_bp.route('/openmeteo', methods=['POST'])
def openmeteo():
    """The EPW of one year for one place. The page asks year by year, so it can show progress."""
    b = request.get_json(silent=True) or {}
    try:
        lat, lon = float(b['latitude']), float(b['longitude'])
        year = int(b['year'])
    except (KeyError, TypeError, ValueError):
        return _error('Latitude, longitude and year are required numbers.', 400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _error('Latitude must be within ±90 and longitude within ±180.', 400)
    model = b.get('model') or 'best_match'
    elevation = b.get('elevation')
    try:
        elevation = None if elevation in (None, '') else float(elevation)
    except ValueError:
        return _error('The elevation is not a number.', 400)
    city = (b.get('city') or '').strip()
    try:
        epw, report = we.build_from_openmeteo(
            lat, lon, year, model=model, elevation=elevation, timezone=b.get('timezone') or None,
            city=city, state=(b.get('state') or '').strip(), country=(b.get('country') or '').strip())
    except we.OpenMeteoError as exc:
        return _error(str(exc), 502)
    base = we.slug(city) if city else f'{abs(lat):.2f}{"N" if lat >= 0 else "S"}_{abs(lon):.2f}{"E" if lon >= 0 else "W"}'
    name = f'{base}_{year}' + ('' if model == 'best_match' else f'_{model}') + '_openmeteo.epw'
    os.makedirs(LIBRARY, exist_ok=True)
    dest = os.path.join(LIBRARY, name)
    we.save(epw, dest)
    return jsonify({'success': True, 'file': _entry(dest, 'lib:' + name, 'library'),
                    'annual': _round(we.summary(epw)['annual']), 'report': report})


# ---------------------------------------------------------------------------
@weather_bp.route('/catalog/search', methods=['GET'])
def catalog_search():
    """Locations of the EnergyPlus weather list: by words, and/or nearest to a point."""
    def number(name):
        value = request.args.get(name)
        return float(value) if value not in (None, '') else None
    try:
        lat, lon = number('lat'), number('lon')
        items = wc.load()
        found = wc.search(items, request.args.get('q', ''), lat, lon, limit=min(int(request.args.get('limit', 25)), 100))
        return jsonify({'success': True, 'catalog_size': len(items), **found})
    except ValueError:
        return _error('Latitude, longitude and limit must be numbers.', 400)
    except wc.CatalogError as exc:
        return _error(str(exc), 502)


@weather_bp.route('/catalog/download', methods=['POST'])
def catalog_download():
    """Put one file of the EnergyPlus weather list in the library."""
    body = request.get_json(silent=True) or {}
    try:
        item = next((i for i in wc.load() if i['id'] == body.get('id')), None)
        if not item:
            return _error('That location is not in the EnergyPlus weather list.', 404)
        epw = we.read_text(wc.fetch_epw(item['epw']))
        name = secure_filename(item['id']) + '.epw'
        os.makedirs(LIBRARY, exist_ok=True)
        dest = os.path.join(LIBRARY, name)
        we.save(epw, dest)
        return jsonify({'success': True, 'file': _entry(dest, 'lib:' + name, 'library'),
                        'annual': _round(we.summary(epw)['annual'])})
    except wc.CatalogError as exc:
        return _error(str(exc), 502)
    except we.EpwReadError as exc:
        return _error(str(exc), 422)


@weather_bp.route('/pvgis', methods=['POST'])
def pvgis():
    """A typical meteorological year for a point, from PVGIS, in the library."""
    b = request.get_json(silent=True) or {}
    try:
        lat, lon = float(b['latitude']), float(b['longitude'])
    except (KeyError, TypeError, ValueError):
        return _error('Latitude and longitude are required numbers.', 400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _error('Latitude must be within ±90 and longitude within ±180.', 400)
    try:
        epw = we.read_text(wc.fetch_pvgis(lat, lon, b.get('startyear') or None, b.get('endyear') or None))
    except (wc.CatalogError, ValueError) as exc:
        return _error(str(exc), 502)
    except we.EpwReadError as exc:
        return _error(str(exc), 422)
    city = (b.get('city') or '').strip()
    we.apply_edits(epw, {'city': city or f'{lat:.2f}N {lon:.2f}E', 'country': (b.get('country') or '').strip(),
                         'source': 'PVGIS TMY', 'wmo': '999999'})
    epw.comments_2.comments_2 = (str(epw.comments_2.comments_2 or '') +
                                 ' | Typical meteorological year from PVGIS (European Commission JRC; ERA5 based) '
                                 'for the requested point; downloaded by the Smart Building Educational Platform.'
                                 ).replace(',', ';')
    base = we.slug(city) if city else f'{abs(lat):.2f}{"N" if lat >= 0 else "S"}_{abs(lon):.2f}{"E" if lon >= 0 else "W"}'
    name = f'{base}_pvgis_tmy.epw'
    os.makedirs(LIBRARY, exist_ok=True)
    dest = os.path.join(LIBRARY, name)
    we.save(epw, dest)
    return jsonify({'success': True, 'file': _entry(dest, 'lib:' + name, 'library'),
                    'annual': _round(we.summary(epw)['annual'])})
