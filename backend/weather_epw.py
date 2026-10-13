"""Weather files (EPW): read, summarise, edit, and build from Open-Meteo.

The EPW reading and writing is pyepw (it round-trips the files in the course -- checked on the Torino
IWEC file: every one of the 8760 rows comes back with the same values). This module adds

    summary(epw)                       what the file contains: statistics, monthly table, daily series
    apply_edits(epw, location, adj)    change the header and/or scale, shift or set variables
    build_from_openmeteo(...)          one annual EPW for a year, from the Open-Meteo archive

Field conventions come from the EnergyPlus Auxiliary Programs, "EnergyPlus Weather File (EPW) Data
Dictionary" (units, valid ranges and MISSING VALUES of the 35 columns; hour 1 is 00:01 to 01:00; the
radiation columns are accumulated over the period preceding the time indicated). Open-Meteo's archive
reports its radiation as the mean of the PRECEDING hour, so the value stamped HH:00 goes into EPW hour
HH, and no shift is needed beyond the time zone.
"""

import datetime as dt
import math
import os
import re
import tempfile

import requests
from pyepw.epw import EPW, WeatherData

ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'

# Models of the archive that carry every variable an EPW needs (the radiation components in particular:
# ERA5-Land has none, so it is not offered). 'cerra' is Europe only and ends in June 2021; the IFS starts
# in 2017. Source: open-meteo.com/en/docs/historical-weather-api.
MODELS = {
    'best_match': {'label': 'Best match (Open-Meteo chooses per location)', 'first': 1940, 'last': None},
    'era5': {'label': 'ERA5 (ECMWF reanalysis, ~25 km, from 1940)', 'first': 1940, 'last': None},
    'ecmwf_ifs': {'label': 'ECMWF IFS (9 km, from 2017)', 'first': 2017, 'last': None},
    'cerra': {'label': 'CERRA (5 km, Europe only, until 2021)', 'first': 1985, 'last': 2021},
}

# Hourly variables requested, in the units the EPW wants (wind in m/s, set in the request).
HOURLY = [
    'temperature_2m', 'relative_humidity_2m', 'dew_point_2m', 'surface_pressure', 'cloud_cover',
    'wind_speed_10m', 'wind_direction_10m', 'shortwave_radiation', 'direct_normal_irradiance',
    'diffuse_radiation', 'precipitation', 'snow_depth',
]
# Without these an hour cannot be written; the others (precipitation, snow) default to none.
CRITICAL = HOURLY[:10]

# EPW missing-value codes (Auxiliary Programs, EPW data dictionary).
MISSING = {
    'dry_bulb_temperature': 99.9, 'dew_point_temperature': 99.9, 'relative_humidity': 999,
    'atmospheric_station_pressure': 999999, 'extraterrestrial_horizontal_radiation': 9999,
    'extraterrestrial_direct_normal_radiation': 9999, 'horizontal_infrared_radiation_intensity': 9999,
    'global_horizontal_radiation': 9999, 'direct_normal_radiation': 9999,
    'diffuse_horizontal_radiation': 9999, 'wind_direction': 999, 'wind_speed': 999,
    'liquid_precipitation_depth': 999, 'snow_depth': 999,
}

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def present(row, field):
    """The value of `field` in a data row, or None when the file marks it missing."""
    value = getattr(row, field)
    if value is None:
        return None
    code = MISSING.get(field)
    if code is not None and float(value) >= float(code):
        return None
    return float(value)


class EpwReadError(ValueError):
    """The file is not an EPW pyepw can load even after it was put in the strict form."""


def _read_strict(path):
    epw = EPW()
    try:
        epw.read(path)
    except (ValueError, IndexError, KeyError) as exc:
        raise EpwReadError(f'{os.path.basename(path)} cannot be read as an EPW file: {exc}.')
    return epw


def read(path):
    """Read an EPW. A file that is valid for EnergyPlus but not to pyepw's letter (integers written as
    decimals, a missing-value code in a column it range-checks) is normalised in memory and read again."""
    try:
        return _read_strict(path)
    except EpwReadError as first:
        with open(path, 'r', errors='replace') as f:
            text = f.read()
        try:
            return read_text(text)
        except EpwReadError:
            raise first


def _write_missing_codes(path):
    """pyepw writes a value it holds as None (read from an empty field) as an empty field; put the EPW
    missing-value code of the column there instead, as the format and EnergyPlus expect."""
    with open(path, 'r') as f:
        lines = f.read().split('\n')
    for n in range(_FIRST_DATA_LINE, len(lines)):
        fields = lines[n].split(',')
        if len(fields) < 35 or '' not in fields:
            continue
        for c, code in _MISSING_BY_COLUMN.items():
            if fields[c] == '':
                fields[c] = f'{code:g}' if code != 0.999 else '0.999'
        lines[n] = ','.join(fields)
    with open(path, 'w') as f:
        f.write('\n'.join(lines))


def save(epw, path):
    """Write atomically: a half-written weather file would break every simulation that reads it."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(suffix='.epw', dir=folder)
    os.close(fd)
    try:
        epw.save(tmp)
        _write_missing_codes(tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# --------------------------------------------------------------------------- psychrometrics
# Magnus formula, WMO coefficients (over water): good to ~0.1 K between -45 and 60 degC.
_MA, _MB = 17.62, 243.12


def dew_point(temp_c, rh):
    gamma = math.log(max(rh, 0.1) / 100.0) + _MA * temp_c / (_MB + temp_c)
    return _MB * gamma / (_MA - gamma)


def relative_humidity(temp_c, dew_c):
    dew_c = min(dew_c, temp_c)
    return 100.0 * math.exp(_MA * dew_c / (_MB + dew_c) - _MA * temp_c / (_MB + temp_c))


# --------------------------------------------------------------------------- summary
def _stats(values):
    return {'mean': sum(values) / len(values), 'min': min(values), 'max': max(values)} if values else None


def summary(epw):
    """Everything the editor shows about a file."""
    loc = epw.location
    rows = epw.weatherdata
    days = []                       # [(month, day)] in file order
    daily = {}                      # (month, day) -> {'t': [], 'g': []}
    monthly = {m: {'t': [], 'g': [], 'rh': [], 'w': []} for m in range(1, 13)}
    missing = {}
    years = set()
    counts = {'t': [], 'rh': [], 'w': [], 'p': [], 'g': [], 'b': [], 'd': [], 'rain': []}
    for r in rows:
        years.add(int(r.year))
        key = (int(r.month), int(r.day))
        if key not in daily:
            daily[key] = {'t': [], 'g': []}
            days.append(key)
        t = present(r, 'dry_bulb_temperature')
        rh = present(r, 'relative_humidity')
        w = present(r, 'wind_speed')
        p = present(r, 'atmospheric_station_pressure')
        g = present(r, 'global_horizontal_radiation')
        b = present(r, 'direct_normal_radiation')
        d = present(r, 'diffuse_horizontal_radiation')
        pr = present(r, 'liquid_precipitation_depth')
        for name, v in (('dry_bulb_temperature', t), ('relative_humidity', rh), ('wind_speed', w),
                        ('atmospheric_station_pressure', p), ('global_horizontal_radiation', g),
                        ('direct_normal_radiation', b), ('diffuse_horizontal_radiation', d)):
            if v is None:
                missing[name] = missing.get(name, 0) + 1
        m = key[0]
        if t is not None:
            daily[key]['t'].append(t)
            monthly[m]['t'].append(t)
            counts['t'].append(t)
        if g is not None:
            daily[key]['g'].append(g)
            monthly[m]['g'].append(g)
            counts['g'].append(g)
        if rh is not None:
            monthly[m]['rh'].append(rh)
            counts['rh'].append(rh)
        if w is not None:
            monthly[m]['w'].append(w)
            counts['w'].append(w)
        if p is not None:
            counts['p'].append(p)
        if b is not None:
            counts['b'].append(b)
        if d is not None:
            counts['d'].append(d)
        if pr is not None:
            counts['rain'].append(pr)

    def avg(v):
        return sum(v) / len(v) if v else None

    day_mean = [avg(daily[k]['t']) for k in days]
    hdd = sum(max(0.0, 18.0 - t) for t in day_mean if t is not None)
    cdd = sum(max(0.0, t - 24.0) for t in day_mean if t is not None)
    t_stats = _stats(counts['t'])
    annual = {
        'temp_mean': t_stats and t_stats['mean'], 'temp_min': t_stats and t_stats['min'],
        'temp_max': t_stats and t_stats['max'],
        'ghi_kwh_m2': sum(counts['g']) / 1000.0 if counts['g'] else None,
        'dni_kwh_m2': sum(counts['b']) / 1000.0 if counts['b'] else None,
        'dhi_kwh_m2': sum(counts['d']) / 1000.0 if counts['d'] else None,
        'rh_mean': avg(counts['rh']), 'wind_mean': avg(counts['w']), 'pressure_mean': avg(counts['p']),
        'rain_mm': sum(counts['rain']) if counts['rain'] else None,
        'hdd18': hdd, 'cdd24': cdd,
    }
    months = []
    for m in range(1, 13):
        v = monthly[m]
        ts = _stats(v['t'])
        months.append({
            'month': m, 'temp_mean': ts and ts['mean'], 'temp_min': ts and ts['min'],
            'temp_max': ts and ts['max'], 'ghi_kwh_m2': sum(v['g']) / 1000.0 if v['g'] else None,
            'rh_mean': avg(v['rh']), 'wind_mean': avg(v['w']),
        })
    first = days[0] if days else (1, 1)
    last = days[-1] if days else (12, 31)
    return {
        'location': {
            'city': loc.city, 'state_province_region': loc.state_province_region, 'country': loc.country,
            'source': loc.source, 'wmo': loc.wmo, 'latitude': loc.latitude, 'longitude': loc.longitude,
            'timezone': loc.timezone, 'elevation': loc.elevation,
        },
        'comments': [str(epw.comments_1.comments_1 or ''), str(epw.comments_2.comments_2 or '')],
        'period': {'rows': len(rows), 'start': f'{first[0]}/{first[1]}', 'end': f'{last[0]}/{last[1]}',
                   'years': sorted(years), 'days': len(days)},
        'annual': annual,
        'monthly': months,
        'daily': {
            'temp_mean': [avg(daily[k]['t']) for k in days],
            'temp_min': [min(daily[k]['t']) if daily[k]['t'] else None for k in days],
            'temp_max': [max(daily[k]['t']) if daily[k]['t'] else None for k in days],
            'ghi_kwh_m2': [sum(daily[k]['g']) / 1000.0 for k in days],
            'month': [k[0] for k in days], 'day': [k[1] for k in days],
        },
        'missing': missing,
    }


# --------------------------------------------------------------------------- hourly series
# What the hourly chart can show: field, label, unit shown, factor from the file's unit.
SERIES = [
    ('dry_bulb_temperature', 'Dry-bulb temperature', '°C', 1.0),
    ('dew_point_temperature', 'Dew point', '°C', 1.0),
    ('relative_humidity', 'Relative humidity', '%', 1.0),
    ('global_horizontal_radiation', 'Global horizontal radiation', 'W/m²', 1.0),
    ('direct_normal_radiation', 'Direct normal radiation', 'W/m²', 1.0),
    ('diffuse_horizontal_radiation', 'Diffuse horizontal radiation', 'W/m²', 1.0),
    ('wind_speed', 'Wind speed', 'm/s', 1.0),
    ('wind_direction', 'Wind direction', '°', 1.0),
    ('atmospheric_station_pressure', 'Atmospheric pressure', 'hPa', 0.01),
    ('total_sky_cover', 'Sky cover', 'tenths', 1.0),
    ('liquid_precipitation_depth', 'Precipitation', 'mm', 1.0),
    ('snow_depth', 'Snow depth', 'cm', 1.0),
]
_SERIES_MISSING = {'total_sky_cover': 99}


def hourly(epw):
    """Every hour of the file, for the chart: {'month','day','hour','vars': {field: [value or None]}}."""
    rows = epw.weatherdata
    out = {'month': [int(r.month) for r in rows], 'day': [int(r.day) for r in rows],
           'hour': [int(r.hour) for r in rows], 'vars': {}, 'order': [f[0] for f in SERIES]}
    for field, label, unit, factor in SERIES:
        values = []
        for r in rows:
            v = getattr(r, field)
            if v is None:
                values.append(None)
                continue
            code = MISSING.get(field, _SERIES_MISSING.get(field))
            if code is not None and float(v) >= float(code):
                values.append(None)
            else:
                values.append(round(float(v) * factor, 2))
        out['vars'][field] = {'label': label, 'unit': unit, 'values': values}
    return out


# --------------------------------------------------------------------------- edits
LOCATION_FIELDS = {
    'city': str, 'state_province_region': str, 'country': str, 'source': str, 'wmo': str,
    'latitude': float, 'longitude': float, 'timezone': float, 'elevation': float,
}

# What the editor can change: label, unit and the physical limits a result is clipped to.
VARIABLES = {
    'dry_bulb_temperature': {'label': 'Dry-bulb temperature', 'unit': '°C', 'lo': -69.0, 'hi': 69.0},
    'relative_humidity': {'label': 'Relative humidity', 'unit': '%', 'lo': 0.0, 'hi': 100.0},
    'wind_speed': {'label': 'Wind speed', 'unit': 'm/s', 'lo': 0.0, 'hi': 40.0},
    'solar_radiation': {'label': 'Solar radiation (global, direct and diffuse together)', 'unit': 'Wh/m²',
                        'lo': 0.0, 'hi': 9998.0},
    'atmospheric_station_pressure': {'label': 'Atmospheric pressure', 'unit': 'Pa', 'lo': 31001.0,
                                     'hi': 119999.0},
}
OPERATIONS = ('add', 'scale', 'set')
SOLAR = ('global_horizontal_radiation', 'direct_normal_radiation', 'diffuse_horizontal_radiation')


class EditError(ValueError):
    """The request cannot be applied; the message is shown to the student."""


def _apply_op(value, op, amount, lo, hi):
    if op == 'add':
        value += amount
    elif op == 'scale':
        value *= amount
    else:
        value = amount
    return min(hi, max(lo, value))


def apply_edits(epw, location=None, adjustments=None):
    """Change the file in memory. Returns a list of what was done (for the student to read)."""
    done = []
    for name, raw in (location or {}).items():
        if name not in LOCATION_FIELDS:
            raise EditError(f'Unknown location field: {name}')
        if raw is None or raw == '':
            continue
        try:
            value = LOCATION_FIELDS[name](raw)
        except (TypeError, ValueError):
            raise EditError(f'{name}: "{raw}" is not valid')
        if name == 'latitude' and not -90 <= value <= 90:
            raise EditError('Latitude must be between -90 and 90')
        if name == 'longitude' and not -180 <= value <= 180:
            raise EditError('Longitude must be between -180 and 180')
        if name == 'timezone' and not -12 <= value <= 12:
            raise EditError('Time zone must be between -12 and 12 hours')
        if getattr(epw.location, name) != value:
            setattr(epw.location, name, value)
            done.append(f'{name.replace("_", " ")} = {value}')

    for adj in adjustments or []:
        var, op = adj.get('variable'), adj.get('op')
        if var not in VARIABLES:
            raise EditError(f'Unknown variable: {var}')
        if op not in OPERATIONS:
            raise EditError(f'Unknown operation: {op}')
        try:
            amount = float(adj.get('value'))
        except (TypeError, ValueError):
            raise EditError(f'{VARIABLES[var]["label"]}: the value is not a number')
        months = adj.get('months') or list(range(1, 13))
        months = {int(m) for m in months}
        if not months <= set(range(1, 13)):
            raise EditError('Months must be between 1 and 12')
        lim = VARIABLES[var]
        keep = adj.get('keep', 'rh')
        touched = 0
        for r in epw.weatherdata:
            if int(r.month) not in months:
                continue
            if var == 'dry_bulb_temperature':
                t = present(r, 'dry_bulb_temperature')
                if t is None:
                    continue
                new_t = _apply_op(t, op, amount, lim['lo'], lim['hi'])
                rh, dew = present(r, 'relative_humidity'), present(r, 'dew_point_temperature')
                if keep == 'dew' and dew is not None:
                    dew = min(dew, new_t)
                    r.relative_humidity = round(relative_humidity(new_t, dew))
                    r.dew_point_temperature = round(dew, 1)
                elif rh is not None:
                    r.dew_point_temperature = round(dew_point(new_t, rh), 1)
                r.dry_bulb_temperature = round(new_t, 1)
            elif var == 'relative_humidity':
                rh = present(r, 'relative_humidity')
                if rh is None:
                    continue
                new_rh = _apply_op(rh, op, amount, lim['lo'], lim['hi'])
                r.relative_humidity = round(new_rh)
                t = present(r, 'dry_bulb_temperature')
                if t is not None:
                    r.dew_point_temperature = round(dew_point(t, new_rh), 1)
            elif var == 'solar_radiation':
                for field in SOLAR:
                    v = present(r, field)
                    if v is not None:
                        setattr(r, field, round(_apply_op(v, op, amount, lim['lo'], lim['hi'])))
            else:
                v = present(r, var)
                if v is None:
                    continue
                r_value = _apply_op(v, op, amount, lim['lo'], lim['hi'])
                setattr(r, var, round(r_value, 2) if var == 'wind_speed' else round(r_value))
            touched += 1
        where = 'the whole year' if len(months) == 12 else 'months ' + ','.join(str(m) for m in sorted(months))
        verb = {'add': 'added', 'scale': 'multiplied by', 'set': 'set to'}[op]
        done.append(f'{lim["label"]} {verb} {amount:g} for {where} ({touched} hours)')
    return done


# --------------------------------------------------------------------------- Open-Meteo
class OpenMeteoError(RuntimeError):
    """Open-Meteo refused, was unreachable, or answered with data an EPW cannot be made from."""


def geocode(query, count=8):
    """Places matching a name, with the coordinates, elevation and IANA time zone Open-Meteo knows."""
    query = (query or '').strip()
    if len(query) < 2:
        return []
    try:
        r = requests.get(GEOCODING_URL, params={'name': query, 'count': count, 'language': 'en'}, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise OpenMeteoError(f'Place search failed: {exc}')
    out = []
    for p in r.json().get('results') or []:
        out.append({k: p.get(k) for k in ('name', 'admin1', 'country', 'country_code', 'latitude',
                                           'longitude', 'elevation', 'timezone', 'population')})
    return out


def standard_offset(tzname, year, longitude):
    """Hours east of UTC without daylight saving (what an EPW calls its time zone), rounded to a whole hour.

    EnergyPlus uses local STANDARD time; the smallest offset a zone has during the year is its standard
    one in both hemispheres. A zone on a half hour (India) is rounded: the hourly grid of the file cannot
    follow it.
    """
    if tzname:
        try:
            from zoneinfo import ZoneInfo
            z = ZoneInfo(tzname)
            offsets = [dt.datetime(year, m, 1, 12, tzinfo=z).utcoffset().total_seconds() / 3600.0
                       for m in (1, 4, 7, 10)]
            raw = min(offsets)
            return int(round(raw)), raw
        except Exception:
            pass
    raw = longitude / 15.0
    return int(round(raw)), raw


def _fetch(params):
    try:
        r = requests.get(ARCHIVE_URL, params=params, timeout=180)
    except requests.RequestException as exc:
        raise OpenMeteoError(f'Open-Meteo is not reachable from the backend: {exc}')
    if r.status_code == 429:
        raise OpenMeteoError('Open-Meteo rate limit reached (the free service allows a limited number of '
                             'requests per minute, hour and day). Wait a while and try again.')
    try:
        body = r.json()
    except ValueError:
        raise OpenMeteoError(f'Open-Meteo answered HTTP {r.status_code} with something that is not JSON')
    if r.status_code != 200 or body.get('error'):
        raise OpenMeteoError(f'Open-Meteo: {body.get("reason") or "HTTP " + str(r.status_code)}')
    return body


def _fill(values, max_gap=6):
    """Fill short gaps (<= max_gap hours) by linear interpolation; longer ones are left as None."""
    n = len(values)
    out = list(values)
    i = 0
    while i < n:
        if out[i] is not None:
            i += 1
            continue
        j = i
        while j < n and out[j] is None:
            j += 1
        if j - i <= max_gap:
            left = out[i - 1] if i > 0 else None
            right = out[j] if j < n else None
            for k in range(i, j):
                if left is not None and right is not None:
                    out[k] = left + (right - left) * (k - i + 1) / (j - i + 1)
                else:
                    out[k] = left if left is not None else right
        i = j
    return out


def valid_year(year, model, today=None):
    today = today or dt.date.today()
    if year >= today.year:
        raise OpenMeteoError(f'{year} is not a complete year yet (the archive lags a few days behind): '
                             f'choose {today.year - 1} or earlier.')
    info = MODELS[model]
    if year < info['first']:
        raise OpenMeteoError(f'The model {model} starts in {info["first"]}.')
    if info['last'] and year > info['last']:
        raise OpenMeteoError(f'The model {model} ends in {info["last"]}.')


def build_from_openmeteo(latitude, longitude, year, model='best_match', elevation=None, timezone=None,
                         city='', state='', country=''):
    """One annual EPW for `year`. Returns (EPW, report)."""
    if model not in MODELS:
        raise OpenMeteoError(f'Unknown model: {model}')
    year = int(year)
    valid_year(year, model)
    std, raw_std = standard_offset(timezone, year, longitude)
    warnings = []
    if raw_std != std:
        warnings.append(f'The time zone is UTC{raw_std:+g}; it was rounded to UTC{std:+d} because an EPW '
                        'works on whole hours.')

    # Local standard time: EPW hour h of a day ends at local midnight + h hours = UTC (that - std).
    first_utc = dt.datetime(year, 1, 1, 1) - dt.timedelta(hours=std)
    last_utc = dt.datetime(year + 1, 1, 1, 0) - dt.timedelta(hours=std)
    params = {
        'latitude': latitude, 'longitude': longitude,
        'start_date': first_utc.date().isoformat(), 'end_date': last_utc.date().isoformat(),
        'hourly': ','.join(HOURLY), 'wind_speed_unit': 'ms', 'timezone': 'GMT',
    }
    if model != 'best_match':
        params['models'] = model
    if elevation is not None:
        params['elevation'] = elevation
    body = _fetch(params)
    hourly = body.get('hourly') or {}
    times = hourly.get('time') or []
    index = {t: i for i, t in enumerate(times)}

    # The EPW year: 365 days (a leap day is left out; see the comment written in the file).
    stamps = []
    for month in range(1, 13):
        for day in range(1, MONTH_DAYS[month - 1] + 1):
            for hour in range(1, 25):
                utc = dt.datetime(year, month, day) + dt.timedelta(hours=hour) - dt.timedelta(hours=std)
                stamps.append((month, day, hour, utc.strftime('%Y-%m-%dT%H:%M')))
    series = {}
    for name in HOURLY:
        raw = hourly.get(name)
        if raw is None:
            if name in CRITICAL:
                raise OpenMeteoError(f'Open-Meteo returned no "{name}" for this place and model.')
            series[name] = [None] * len(stamps)
            continue
        values = []
        for _, _, _, key in stamps:
            i = index.get(key)
            values.append(raw[i] if i is not None else None)
        n_missing = sum(v is None for v in values)
        values = _fill(values)
        left = sum(v is None for v in values)
        if left and name in CRITICAL:
            raise OpenMeteoError(f'"{name}" has {left} hours missing in {year} (gaps longer than 6 h); '
                                 'try another model.')
        if n_missing and name in CRITICAL:
            warnings.append(f'{name}: {n_missing} missing hour(s) filled by interpolation.')
        series[name] = values

    grid_lat, grid_lon = body.get('latitude'), body.get('longitude')
    used_elev = body.get('elevation')
    if elevation is not None:
        used_elev = elevation
    place = (city or f'{latitude:.3f}N {longitude:.3f}E').replace(',', ' ')
    weekday = dt.date(year, 1, 1).strftime('%A')
    comment1 = (f'Generated by the Smart Building Educational Platform from Open-Meteo (open-meteo.com, '
                f'CC BY 4.0; model {model}; contains modified Copernicus Climate Change Service information). '
                f'Year {year}. Requested point {latitude:.4f} {longitude:.4f}; the model grid cell is at '
                f'{grid_lat} {grid_lon}; elevation {used_elev} m.').replace(',', ';')
    comment2 = (f'Reanalysis, not a weather station. Time stamps converted to local standard time UTC{std:+d}. '
                'Radiation is the mean of the preceding hour, as an EPW expects. Horizontal infrared, '
                'visibility, illuminance and extraterrestrial radiation are marked missing: EnergyPlus '
                'derives the sky temperature from the opaque sky cover. 29 February is left out.').replace(',', ';')

    def n(x, default=''):
        return default if x is None else x

    header = [
        f'LOCATION,{place},{n(state, "-").replace(",", " ") or "-"},{n(country, "-").replace(",", " ") or "-"},'
        f'Open-Meteo {model},999999,{latitude},{longitude},{std},{used_elev if used_elev is not None else 0}',
        'DESIGN CONDITIONS,0',
        'TYPICAL/EXTREME PERIODS,0',
        'GROUND TEMPERATURES,0',
        'HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0',
        f'COMMENTS 1,{comment1}',
        f'COMMENTS 2,{comment2}',
        f'DATA PERIODS,1,1,Data,{weekday},1/1,12/31',
    ]
    fd, tmp = tempfile.mkstemp(suffix='.epw')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write('\n'.join(header) + '\n')
        epw = EPW()
        epw.read(tmp)
    finally:
        os.remove(tmp)

    flags = '?0' * 22
    for i, (month, day, hour, _) in enumerate(stamps):
        w = WeatherData()
        w.year, w.month, w.day, w.hour, w.minute = year, month, day, hour, 60
        w.data_source_and_uncertainty_flags = flags
        t = series['temperature_2m'][i]
        w.dry_bulb_temperature = round(t, 1)
        w.dew_point_temperature = round(min(series['dew_point_2m'][i], t), 1)
        w.relative_humidity = min(100, max(0, round(series['relative_humidity_2m'][i])))
        w.atmospheric_station_pressure = round(series['surface_pressure'][i] * 100)
        w.extraterrestrial_horizontal_radiation = 9999
        w.extraterrestrial_direct_normal_radiation = 9999
        w.horizontal_infrared_radiation_intensity = 9999
        w.global_horizontal_radiation = max(0, round(series['shortwave_radiation'][i]))
        w.direct_normal_radiation = max(0, round(series['direct_normal_irradiance'][i]))
        w.diffuse_horizontal_radiation = max(0, round(series['diffuse_radiation'][i]))
        w.global_horizontal_illuminance = 999999
        w.direct_normal_illuminance = 999999
        w.diffuse_horizontal_illuminance = 999999
        w.zenith_luminance = 9999
        w.wind_direction = int(round(series['wind_direction_10m'][i])) % 360
        w.wind_speed = round(min(40.0, max(0.0, series['wind_speed_10m'][i])), 2)
        cover = min(10, max(0, round(series['cloud_cover'][i] / 10.0)))
        w.total_sky_cover = cover
        w.opaque_sky_cover = cover
        w.visibility = 9999
        w.ceiling_height = 99999
        w.present_weather_observation = 9
        w.present_weather_codes = '999999999'
        w.precipitable_water = 999
        w.aerosol_optical_depth = 0.999
        snow = series['snow_depth'][i]
        w.snow_depth = round((snow or 0.0) * 100.0)
        w.days_since_last_snowfall = 99
        w.albedo = 999
        rain = series['precipitation'][i]
        w.liquid_precipitation_depth = round(rain or 0.0, 1)
        w.liquid_precipitation_quantity = 1
        epw.add_weatherdata(w)

    if all(v is None for v in series['snow_depth']):
        warnings.append('This model has no snow depth: it is written as 0 cm.')
    report = {'year': year, 'model': model, 'grid_latitude': grid_lat, 'grid_longitude': grid_lon,
              'elevation': used_elev, 'time_zone': std, 'warnings': warnings}
    return epw, report


# --------------------------------------------------------------------------- files from elsewhere
# pyepw checks every value against the format's type and range. Files from other sources are valid for
# EnergyPlus but not always to that letter (PVGIS writes a humidity of 84.85, a radiation of -0.00 and
# minute 0), so they are put in the strict form before pyepw sees them.
_INT_COLUMNS = (0, 1, 2, 3, 4, 8, 9, 26, 27, 31)       # year .. minute, humidity, pressure, weather, snow days
_RADIATION_COLUMNS = range(10, 20)                      # extraterrestrial .. zenith luminance
_FIRST_DATA_LINE = 8
# The missing-value code of each column (EPW data dictionary). pyepw range-checks a code written out, but
# accepts an empty field as "missing" and writes the code back.
_MISSING_BY_COLUMN = {6: 99.9, 7: 99.9, 8: 999, 9: 999999, 10: 9999, 11: 9999, 12: 9999, 13: 9999, 14: 9999,
                      15: 9999, 16: 999999, 17: 999999, 18: 999999, 19: 9999, 20: 999, 21: 999, 22: 99, 23: 99,
                      24: 9999, 25: 99999, 28: 999, 29: 0.999, 30: 999, 31: 99, 32: 999, 33: 999, 34: 99}


def normalize_text(text):
    """EPW text -> the same file with integer columns as integers, no negative radiation, minute 60."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = []
    for n, line in enumerate(lines):
        if n < _FIRST_DATA_LINE:
            out.append(line.replace('HOLIDAYS/DAYLIGHT SAVING,', 'HOLIDAYS/DAYLIGHT SAVINGS,'))
            continue
        f = line.strip().split(',')
        if len(f) < 35:
            if line.strip():
                out.append(line)
            continue
        for c, code in _MISSING_BY_COLUMN.items():
            try:
                if float(f[c]) == code:
                    f[c] = ''
            except ValueError:
                pass
        for c in _INT_COLUMNS:
            try:
                f[c] = str(int(round(float(f[c]))))
            except ValueError:
                pass
        if f[4] == '0':
            f[4] = '60'
        for c in range(6, 35):
            if c in _INT_COLUMNS:
                continue
            try:
                v = float(f[c])
            except ValueError:
                continue
            if v == 0:
                f[c] = '0.0'
            elif c in _RADIATION_COLUMNS and v < 0:
                f[c] = '0.0'
        out.append(','.join(f))
    return '\n'.join(out) + '\n'


def read_text(text):
    """Read EPW text that may not be in pyepw's strict form."""
    fd, tmp = tempfile.mkstemp(suffix='.epw')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(normalize_text(text))
        return _read_strict(tmp)
    finally:
        os.remove(tmp)


def slug(text):
    text = re.sub(r'[^A-Za-z0-9]+', '_', text or '').strip('_')
    return text or 'weather'
