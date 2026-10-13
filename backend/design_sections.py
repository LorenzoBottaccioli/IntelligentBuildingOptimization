"""How the design panel divides the model: by the decision being made.

Five sections, each a question a designer actually asks, and each filled from
whatever classes this model contains -- a model with real plant grows a sixth.
There is no "everything else" section. What belongs to none of them (location,
simulation parameters, output requests...) is not a design decision, and stays
reachable through the search, which names its EnergyPlus group.

    envelope   Involucro               -- external walls, roof, windows; envelope.py
    control    Regolazione             -- thermostats by regime, see thermostats.py
    loads      Occupazione e carichi   -- people, lights, equipment, hot water
    airflow    Ventilazione            -- ventilation and infiltration
    systems    Impianti                -- only when the model has plant or units

The section of a class is its IDD group, mapped once below over all 59 groups
EnergyPlus 9.6 declares. Groups left out are, on purpose, not design sections.
"""

import idf_session

SECTIONS = [
    ('envelope', 'Envelope', 'External walls, roof and windows: a layer of a build-up or the whole construction.'),
    ('control', 'Control', 'Thermostat setpoints and other controls, read from the schedules that hold them.'),
    ('loads', 'Occupancy and internal loads', 'People, lighting, equipment and hot water: densities and profiles.'),
    ('airflow', 'Ventilation and infiltration', 'Air flow rates, calculation methods and profiles.'),
    ('systems', 'HVAC systems', 'Units, coils, pumps and plant the model contains.'),
]

# IDD group -> section. Envelope groups are reached through the elements, not
# listed as classes; the envelope section shows elements only.
GROUP_SECTION = {
    'Internal Gains': 'loads',
    'Exterior Equipment': 'loads',
    'Water Systems': 'loads',
    'Zone Airflow': 'airflow',
    'AirflowNetwork': 'airflow',
    'Zone HVAC Controls and Thermostats': 'control',
    'Daylighting': 'control',
    'Setpoint Managers': 'control',
    'System Availability Managers': 'control',
    'Controllers': 'control',
    'Demand Limiting Controls': 'control',
    'Plant-Condenser Control': 'control',
    **{g: 'systems' for g in (
        'HVAC Templates', 'HVAC Design Objects', 'Zone HVAC Forced Air Units',
        'Zone HVAC Radiative/Convective Units', 'Zone HVAC Air Loop Terminal Units',
        'Zone HVAC Equipment Connections', 'Fans', 'Coils', 'Evaporative Coolers',
        'Humidifiers and Dehumidifiers', 'Heat Recovery', 'Unitary Equipment',
        'Variable Refrigerant Flow Equipment', 'Air Distribution', 'Pumps',
        'Plant-Condenser Flow Control', 'Non-Zone Equipment', 'Solar Collectors',
        'Plant Heating and Cooling Equipment', 'Condenser Equipment and Heat Exchangers',
        'Water Heaters and Thermal Storage', 'Plant-Condenser Loops', 'Refrigeration',
        'Electric Load Center-Generator Specifications',
        'User Defined HVAC and Plant Component Models', 'Performance Curves',
        'Performance Tables', 'Node-Branch Management')},
}

_SCHEDULE_CLASSES = ('SCHEDULE:COMPACT', 'SCHEDULE:CONSTANT', 'SCHEDULE:YEAR',
                     'SCHEDULE:FILE')


def _num(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# Read through the raw list eppy keeps on every object (obj.obj, aligned with
# obj.fieldnames) rather than getattr: getattr resolves the field name on each
# call, and walking every field of every object that way took 211 s on E1_RES1
# in the backend image. getobject scans its class on each call, so schedules
# are looked up through one index instead.

def _index(idf):
    return {o.Name.upper(): o for cls in _SCHEDULE_CLASSES for o in idf.idfobjects[cls]}


def _raw(obj, field):
    try:
        return obj.obj[obj.fieldnames.index(field)]
    except (ValueError, IndexError):
        return ''


def values(obj):
    """The numeric values a schedule holds, each with the field it sits in.

    Schedule:Compact is one irregular list -- "Through:", "For:", "Until:" and
    numbers -- so a value is any field that parses as a number and is not a
    time. Schedule:Constant has one. Anything else (Year -> Week -> Day, File)
    is not editable from here and yields nothing.
    """
    key = obj.key.upper()
    if key == 'SCHEDULE:CONSTANT':
        v = _num(_raw(obj, 'Hourly_Value'))
        return [('Hourly_Value', v, '')] if v is not None else []
    if key != 'SCHEDULE:COMPACT':
        return []
    out, period = [], ''
    names, raws = obj.fieldnames, obj.obj
    for i in range(3, min(len(names), len(raws))):
        f, raw = names[i], str(raws[i]).strip()
        if not raw:
            continue
        if raw.lower().startswith('through:'):
            period = raw[8:].strip()
        v = _num(raw)
        if v is not None:
            out.append((f, v, period))
    return out


# ---- reading a schedule the way EnergyPlus does --------------------------
#
# From the Input Output Reference, Group - Schedules: a schedule is a year made
# of weeks made of days. Schedule:Compact writes all three in one list --
# "Through:" a date ends a period of the year, "For:" names the day types that
# follow, each "Until:" a time closes a block of the day, and the number after
# it is the value for that block. Schedule:Constant is one value for the whole
# year. Schedule:Year names a Schedule:Week:Daily per period, which names a
# Schedule:Day per day type. A thermostat's setpoint schedule is read the same
# way: the value is the setpoint at that time of that day.

_DAYS = {
    'weekdays': 'weekdays', 'weekends': 'weekends', 'holidays': 'holidays',
    'alldays': 'every day', 'allotherdays': 'other days',
    'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday',
    'thursday': 'Thursday', 'friday': 'Friday', 'saturday': 'Saturday',
    'sunday': 'Sunday', 'customday1': 'custom day 1',
    'customday2': 'custom day 2',
}
# Design days only size the plant; they are not part of the year a student
# optimises over, so they are left out of the description.
_DESIGN_DAYS = {'summerdesignday', 'winterdesignday'}
_MONTHS_EN = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
_MONTHS_IT = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
_DAYS_IN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
ALL_YEAR = "tutto l'anno"


def _date(text):
    """A Through: date as (month, day), in any of the forms EnergyPlus accepts."""
    t = text.strip().lower().replace(',', ' ')
    if '/' in t:
        m, d = t.split('/')[:2]
        return int(m), int(d)
    parts = t.split()
    for i, part in enumerate(parts):
        for n, name in enumerate(_MONTHS_EN):
            if part.startswith(name):
                other = parts[1 - i] if len(parts) > 1 else '1'
                return n + 1, int(''.join(c for c in other if c.isdigit()) or 1)
    return None


def _next_day(md):
    m, d = md
    if d < _DAYS_IN[m - 1]:
        return m, d + 1
    return (m % 12) + 1, 1


def _fmt(md):
    return f'{md[1]} {_MONTHS_EN[md[0] - 1].title()}'


def _hour(text):
    t = str(text).strip()
    if ':' in t:
        h, m = t.split(':')[:2]
        return int(h) + int(m) / 60
    return _num(t)


def _hhmm(h):
    if h == int(h):
        return f'{int(h):02d}'
    return f'{int(h):02d}:{int(round((h % 1) * 60)):02d}'


def _days_label(tokens):
    kept = [t for t in tokens if t.lower() not in _DESIGN_DAYS]
    return ', '.join(_DAYS.get(t.lower(), t) for t in kept)


def _compact(obj):
    """Schedule:Compact as rows: period, day types, blocks (from, to, value, field)."""
    rows, start, period, days, clock = [], (1, 1), None, None, 0.0
    names, raws = obj.fieldnames, obj.obj
    for i in range(3, min(len(names), len(raws))):
        raw = str(raws[i]).strip()
        if not raw:
            continue
        low = raw.lower()
        if low.startswith('through'):
            end = _date(raw.split(':', 1)[-1] if ':' in raw else raw[7:])
            period = (start, end or (12, 31))
            start = _next_day(end) if end else start
            days = None
        elif low.startswith('for'):
            tokens = (raw.split(':', 1)[-1] if ':' in raw else raw[3:]).split()
            days = {'tokens': tokens, 'blocks': []}
            clock = 0.0
            if period is not None:
                rows.append({'period': period, 'days': days})
        elif low.startswith('interpolate'):
            continue
        elif low.startswith('until'):
            if days is not None:
                days['pending'] = _hour(raw.split(':', 1)[-1])
        else:
            v = _num(raw)
            if v is None or days is None:
                continue
            until = days.pop('pending', 24.0)
            days['blocks'].append((clock, until, v, names[i]))
            clock = until
    return rows


def _day(idf, name):
    hourly = idf.getobject('SCHEDULE:DAY:HOURLY', name)
    if hourly is not None:
        vals = [_num(v) for v in hourly.obj[3:27]]
        blocks, first = [], 0
        for h in range(1, 25):
            if h == 24 or vals[h] != vals[first]:
                blocks.append((float(first), float(h), vals[first], None))
                first = h
        return blocks
    interval = idf.getobject('SCHEDULE:DAY:INTERVAL', name)
    if interval is not None:
        blocks, clock, raws = [], 0.0, interval.obj[4:]
        for t, v in zip(raws[0::2], raws[1::2]):
            t = str(t)
            until = _hour(t.split(':', 1)[-1] if t.lower().startswith('until') else t)
            blocks.append((clock, until, _num(v), None))
            clock = until
        return blocks
    return None


def _year(idf, obj):
    """Schedule:Year -> Schedule:Week:Daily -> Schedule:Day:*, as rows."""
    rows, raws = [], obj.obj
    week_days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                 'Saturday', 'Holidays']
    for i in range(3, len(raws) - 4, 5):
        try:
            period = ((int(raws[i + 1]), int(raws[i + 2])), (int(raws[i + 3]), int(raws[i + 4])))
        except (TypeError, ValueError):
            continue
        week = idf.getobject('SCHEDULE:WEEK:DAILY', raws[i])
        if week is None:
            return None
        by_day = {}
        for n, day in enumerate(week_days):
            by_day.setdefault(str(week.obj[2 + n]), []).append(day)
        for day_name, day_types in by_day.items():
            blocks = _day(idf, day_name)
            if blocks is None:
                return None
            tokens = ['AllDays'] if len(day_types) == len(week_days) else day_types
            rows.append({'period': period, 'days': {'tokens': tokens, 'blocks': blocks}})
    return rows


def describe(idf, obj):
    """A schedule as a person reads it: when, on which days, what value.

    Rows {period, days, blocks:[{from, to, value}]}, identical rows merged -- a
    heating schedule equal from January to April and from October to December
    reads as one row -- or None for kinds not read here (Schedule:File,
    Schedule:Day:List).
    """
    key = obj.key.upper()
    if key == 'SCHEDULE:CONSTANT':
        v = _num(_raw(obj, 'Hourly_Value'))
        return [{'period': ALL_YEAR, 'days': 'every day', 'spans': [],
                 'blocks': [{'from': 0, 'to': 24, 'value': v}]}]
    if key == 'SCHEDULE:COMPACT':
        raw_rows = _compact(obj)
    elif key == 'SCHEDULE:YEAR' and idf is not None:
        raw_rows = _year(idf, obj)
    else:
        return None
    if raw_rows is None:
        return None

    merged = []
    for r in raw_rows:
        label = _days_label(r['days']['tokens'])
        if not label:
            continue  # design days only
        blocks = tuple((b[0], b[1], b[2]) for b in r['days']['blocks'])
        same = next((m for m in merged if m['label'] == label and m['blocks'] == blocks), None)
        if same:
            same['periods'].append(r['period'])
        else:
            merged.append({'label': label, 'blocks': blocks, 'periods': [r['period']]})

    # Periods that follow one another are one period: a control type schedule
    # written as Jan-Mar, Apr-Sep, Oct-Dec with the same content is all year.
    for m in merged:
        joined = []
        for a, b in sorted(m['periods']):
            if joined and _next_day(joined[-1][1]) == a:
                joined[-1] = (joined[-1][0], b)
            else:
                joined.append((a, b))
        m['periods'] = joined

    def when(periods):
        if len(periods) == 1 and periods[0] == ((1, 1), (12, 31)):
            return ALL_YEAR
        return ' e '.join(f'dal {_fmt(a)} al {_fmt(b)}' for a, b in periods)

    # Day types with the same hours in the same period are one row.
    out = []
    for m in merged:
        period = when(m['periods'])
        same = next((o for o in out if o['period'] == period and o['_blocks'] == m['blocks']), None)
        if same:
            same['days'] += ', ' + m['label']
            continue
        out.append({'period': period, 'days': m['label'], '_blocks': m['blocks'],
                    # The same periods as data, so the panel can make each end
                    # date a handle; an all-year row has none.
                    'spans': [] if period == ALL_YEAR else
                             [{'from': _fmt(a), 'to': _fmt(b)} for a, b in m['periods']],
                    'blocks': [{'from': a, 'to': b, 'value': v} for a, b, v in m['blocks']]})
    for o in out:
        del o['_blocks']
        if o['days'] == 'weekdays, weekends, holidays' or o['days'].startswith('weekdays, weekends, holidays, other'):
            o['days'] = 'every day'
    return out


def summary(obj, idf=None):
    """A schedule in one line: day types and hours with their values."""
    rows = describe(idf, obj)
    if not rows:
        return obj.key
    parts = []
    for r in rows[:3]:
        if len(r['blocks']) == 1:
            blocks = f'{r["blocks"][0]["value"]:g} all day'
        else:
            blocks = ' · '.join(f'{_hhmm(b["from"])}-{_hhmm(b["to"])} {b["value"]:g}'
                                for b in r['blocks'])
        prefix = '' if r['period'] == ALL_YEAR else f'{r["period"]}, '
        parts.append(f'{prefix}{r["days"]}: {blocks}')
    more = f' (+{len(rows) - 3})' if len(rows) > 3 else ''
    return ' | '.join(parts) + more


def schedules(idf=None):
    """Every schedule, what it holds and what uses it.

    Used by the panel to describe a schedule by its content and to set the
    alternatives for a profile: those with the same use come first, the rest
    of the model's schedules apart.
    """
    idf = idf or idf_session.get()
    out = {}
    for cls in _SCHEDULE_CLASSES:
        for o in idf.idfobjects[cls]:
            out[o.Name] = {'summary': summary(o, idf), 'usedBy': [],
                           'typeLimits': _raw(o, 'Schedule_Type_Limits_Name') or ''}
    upper = {n.upper(): n for n in out}
    for cls, objects in idf.idfobjects.items():
        if not objects or cls.startswith('SCHEDULE') or cls.startswith('OUTPUT'):
            continue
        # Which positions hold a schedule name is a property of the class.
        slots = [(i, f) for i, f in enumerate(objects[0].fieldnames)
                 if f.endswith('Schedule_Name')]
        if not slots:
            continue
        for o in objects:
            raws = o.obj
            for i, f in slots:
                if i >= len(raws):
                    continue
                name = upper.get(str(raws[i] or '').upper())
                if name:
                    # Upper case, as eppy keys its classes: the file may
                    # spell a class "PEOPLE" or "People", and the panel
                    # compares on this string.
                    use = f'{cls}.{f}'
                    if use not in out[name]['usedBy']:
                        out[name]['usedBy'].append(use)
    return out
