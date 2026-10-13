"""Any EnergyPlus schedule, read into one shape, with who uses it and who overrides it.

From the Input Output Reference 9.6, Group - Schedules, checked against Energy+.idd:

    A schedule that other objects can name (\\reference ScheduleNames) is one of
        Schedule:Constant    one value for the whole year
        Schedule:Compact     Through: date / For: day types / Until: time, value
        Schedule:Year        up to 53 (week, start, end) -> Schedule:Week:Daily
                             (12 day fields) or Schedule:Week:Compact (day-type
                             list, day pairs) -> Schedule:Day:Hourly (24 values),
                             Schedule:Day:Interval (Until/value pairs) or
                             Schedule:Day:List (minutes per item, values)
        Schedule:File        a column of 8760-8784 hourly (or sub-hourly) values
        ExternalInterface:[FunctionalMockupUnit...:To:]Schedule
                             a value written by an external program at run time

    Every period must cover all 12 day types (Sunday ... Saturday, Holiday,
    SummerDesignDay, WinterDesignDay, CustomDay1, CustomDay2) and every day must
    reach 24:00. "Until" includes the time entered. A Schedule:Year that misses
    part of the year is a fatal error.

All of these say the same thing: for each period of the year, for each set of
day types, a value until each time of day. That is the shape returned here:

    {name, type, limits, editable,
     periods: [{start: [m, d], end: [m, d], week: <Schedule:Week name | None>,
                groups: [{days: [...12-day-type subset...],
                          day: <Schedule:Day name | None>,
                          interpolate: 'No' | 'Average' | 'Linear',
                          slots: [[until_minute, value], ...]}]}],
     problems: [...],   rules EnergyPlus would reject; the editor will not write
     notes: [...]}      text E+ accepts but ignores (zero-length slots, blocks
                        after 31/12), dropped from the shape

A schedule is used through any field whose IDD object-list is ScheduleNames
(800 fields in 9.6), so `users` is derived from the IDD, not listed by hand. It
can be overridden at run time by an EMS actuator on the schedule, or by an FMU
writing to that actuator; `overrides` finds both, and says whether an EMS
program that is actually called writes to the actuator, and whether it ever
releases it (SET x = NULL), in which case the schedule applies the rest of the time.
"""

import re

DAY_TYPES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
             'Holiday', 'SummerDesignDay', 'WinterDesignDay', 'CustomDay1', 'CustomDay2']
_WEEKDAYS = DAY_TYPES[1:6]

YEAR_TYPES = ('SCHEDULE:CONSTANT', 'SCHEDULE:COMPACT', 'SCHEDULE:YEAR', 'SCHEDULE:FILE',
              'EXTERNALINTERFACE:SCHEDULE',
              'EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITIMPORT:TO:SCHEDULE',
              'EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:TO:SCHEDULE')
WEEK_TYPES = ('SCHEDULE:WEEK:DAILY', 'SCHEDULE:WEEK:COMPACT')
DAY_SCHEDULE_TYPES = ('SCHEDULE:DAY:HOURLY', 'SCHEDULE:DAY:INTERVAL', 'SCHEDULE:DAY:LIST')

_MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
_DAYS_IN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

WHOLE_YEAR = ([1, 1], [12, 31])


# ---- raw access (eppy getattr is slow at model scale) -----------------------

def _fields(obj):
    """Every field after the class name, as stripped strings."""
    return [str(v).strip() for v in obj.obj[1:]]


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


class _Index:
    """Schedule-related objects by upper-cased name, per role."""

    def __init__(self, idf):
        self.idf = idf
        self.year, self.week, self.day = {}, {}, {}
        for role, types in ((self.year, YEAR_TYPES), (self.week, WEEK_TYPES),
                            (self.day, DAY_SCHEDULE_TYPES)):
            for cls in types:
                for obj in idf.idfobjects.get(cls, []):
                    role[str(obj.obj[1]).strip().upper()] = obj


# ---- parsing helpers --------------------------------------------------------

def parse_date(text):
    """A "Through:" date as EnergyPlus reads it (General::ProcessDateString, 9.6) -> [m, d] or None.

    '/', ':' and '-' separate; two tokens are month day (numbers), month-name day
    or day month-name (first three letters); one number is the day of a
    non-leap year ('Through: 10:31' is 31 Oct, '365' is 31 Dec).
    """
    t = re.sub(r'[/:\-]', ' ', text.strip().lower()).split()
    if len(t) == 1 and t[0].isdigit() and 1 <= int(t[0]) <= 365:
        n = int(t[0])
        for month, days in enumerate([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], 1):
            if n <= days:
                return [month, n]
            n -= days
    if len(t) == 3 and t[2].isdigit() and len(t[2]) == 4:
        t = t[:2]                                   # a trailing year
    if len(t) != 2:
        return None
    a, b = t
    month = day = None
    if a.isdigit() and b.isdigit():
        month, day = int(a), int(b)
    elif b.isdigit():
        month, day = next((i + 1 for i, n in enumerate(_MONTHS) if a[:3] == n), None), int(b)
    elif a.isdigit():
        day, month = int(a), next((i + 1 for i, n in enumerate(_MONTHS) if b[:3] == n), None)
    if not month or not (1 <= month <= 12 and 1 <= day <= _DAYS_IN[month - 1]):
        return None
    return [month, day]


def parse_time(text):
    """An "Until:" time as EnergyPlus reads it (DecodeHHMMField) -> minutes, or None.

    Needs a colon; hours 0-24, minutes 0-60; 24:xx is cut to 24:00 (E+ warns).
    """
    m = re.fullmatch(r'(\d*):(\d+)(?::\d+)?', text.strip())
    if not m:
        return None
    hh, mm = int(m.group(1) or 0), int(m.group(2))
    if hh > 24 or mm > 60:
        return None
    minutes = 1440 if hh == 24 else hh * 60 + mm
    return minutes if 0 < minutes <= 1440 else None


# ScheduleManager::ProcessForDayTypes (9.6): each keyword is searched as a
# substring of the upper-cased field, in this order, so 'Weekday', 'Saturdays'
# and 'For Weekdaysy' all work. Assigning a day type twice is a severe error.
_FOR_KEYS = [('WEEKDAY', _WEEKDAYS), ('MONDAY', ['Monday']), ('TUESDAY', ['Tuesday']),
             ('WEDNESDAY', ['Wednesday']), ('THURSDAY', ['Thursday']), ('FRIDAY', ['Friday']),
             ('WEEKEND', ['Sunday', 'Saturday']), ('SATURDAY', ['Saturday']), ('SUNDAY', ['Sunday']),
             ('CUSTOMDAY1', ['CustomDay1']), ('CUSTOMDAY2', ['CustomDay2']), ('ALLDAY', DAY_TYPES),
             ('HOLIDAY', ['Holiday']), ('SUMMER', ['SummerDesignDay']), ('WINTER', ['WinterDesignDay'])]


def _day_types(text, taken):
    """(days, error) for a For/DayType field, given the day types already assigned."""
    up = text.upper()
    days, dup, valid = [], False, False
    already = list(taken)
    for key, members in _FOR_KEYS:
        if key in up:
            valid = True
            for d in members:
                if d in already:
                    dup = True
                else:
                    already.append(d)
                if d not in days:
                    days.append(d)
    if 'ALLOTHERDAY' in up:
        valid = True
        days += [d for d in DAY_TYPES if d not in already and d not in days]
    if not valid:
        return [], f'nessun tipo di giorno riconosciuto in "{text}"'
    if dup:
        return [d for d in days if d not in taken], f'"{text}": un giorno è assegnato due volte (EnergyPlus lo rifiuta)'
    return days, None


def _after(token, word):
    """'Through: 12/31' -> '12/31'; the keyword and colon are optional prefixes."""
    return re.sub(r'^\s*' + word + r'\s*:?\s*', '', token, flags=re.I)


def _target(obj, k):
    """The IDF field behind f[k] (f = _fields(obj)), in the form problem.json uses."""
    return {'className': obj.key, 'object': str(obj.obj[1]).strip(), 'field': obj.fieldnames[k + 1]}


def _merge(slots, src):
    """Join consecutive slots with the same value; the shape a person reads.

    A joined slot keeps every value field it came from (a Day:Hourly box that
    covers 08-12 writes Hour 9..12), and has no single time field.
    """
    out, out_src = [], []
    for (until, value), sr in zip(slots, src):
        if out and out[-1][1] == value:
            out[-1][0] = until
            out_src[-1] = {'time': [], 'value': out_src[-1]['value'] + sr['value']}
        else:
            out.append([until, value])
            out_src.append({'time': list(sr['time']), 'value': list(sr['value'])})
    return out, out_src


# ---- day and week schedules ------------------------------------------------

def _day(obj, problems):
    """A Schedule:Day:* object -> (interpolate, slots, src); src[i] = fields of slot i."""
    cls = obj.key.upper()
    f = _fields(obj)
    name = f[0]
    if cls == 'SCHEDULE:DAY:HOURLY':
        values = [_num(v) for v in f[2:26]]
        if len(values) < 24 or None in values:
            problems.append(f'{name}: servono 24 valori orari')
            values = [v if v is not None else 0.0 for v in values] + [0.0] * (24 - len(values))
        slots, src = _merge([[60 * (h + 1), v] for h, v in enumerate(values)],
                            [{'time': [], 'value': [_target(obj, 2 + h)]} for h in range(24)])
        return 'No', slots, src
    if cls == 'SCHEDULE:DAY:INTERVAL':
        interpolate = f[2] or 'No'
        slots, src = [], []
        rest = f[3:]
        for i in range(0, len(rest) - 1, 2):
            if not rest[i]:
                break
            until, value = parse_time(_after(rest[i], 'until')), _num(rest[i + 1])
            if until is None or value is None:
                problems.append(f'{name}: fascia illeggibile "{rest[i]}"')
                continue
            slots.append([until, value])
            src.append({'time': [_target(obj, 3 + i)], 'value': [_target(obj, 4 + i)]})
        return interpolate, slots, src
    # SCHEDULE:DAY:LIST
    interpolate = f[2] or 'No'
    step = int(_num(f[3]) or 60)
    values = [_num(v) for v in f[4:] if v != '']
    slots, src = _merge([[step * (i + 1), v] for i, v in enumerate(values)],
                        [{'time': [], 'value': [_target(obj, 4 + i)]} for i in range(len(values))])
    return interpolate, slots, src


def _week(obj, idx, problems):
    """A Schedule:Week:* object -> groups, one per distinct Schedule:Day."""
    cls = obj.key.upper()
    f = _fields(obj)
    by_day = {}
    if cls == 'SCHEDULE:WEEK:DAILY':
        for day_type, day_name in zip(DAY_TYPES, f[1:13]):
            by_day.setdefault(day_name, []).append(day_type)
    else:
        taken = []
        rest = f[1:]
        for i in range(0, len(rest) - 1, 2):
            if not rest[i]:
                break
            days, err = _day_types(rest[i], taken)
            if err:
                problems.append(f'{f[0]}: {err}')
            taken += days
            by_day.setdefault(rest[i + 1], []).extend(days)
    groups = []
    for day_name, days in by_day.items():
        day_obj = idx.day.get(day_name.upper())
        if day_obj is None:
            problems.append(f'{f[0]}: manca Schedule:Day "{day_name}"')
            continue
        interpolate, slots, src = _day(day_obj, problems)
        groups.append({'days': days, 'day': str(day_obj.obj[1]).strip(),
                       'dayType': day_obj.key, 'interpolate': interpolate, 'slots': slots,
                       'src': src})
    return groups


# ---- year schedules ---------------------------------------------------------

def _compact(obj, problems, notes):
    f = _fields(obj)
    periods, start = [], [1, 1]
    period = group = None
    taken = []
    pending_until = None
    pending_field = None
    for k, token in enumerate(f[2:], 2):
        if token == '':
            continue
        low = token.lower()
        if low.startswith('through'):
            end = parse_date(_after(token, 'through'))
            if end is None:
                problems.append(f'data illeggibile "{token}"')
                end = [12, 31]
            period = {'start': start, 'end': end, 'week': None, 'groups': [],
                      'srcEnd': [_target(obj, k)]}
            if periods and periods[-1]['end'] == [12, 31]:
                # E+ fills no day with a block after the full year; it is dead text.
                notes.append(f'"{token}" dopo il 31/12 non copre nessun giorno: EnergyPlus lo ignora')
            else:
                periods.append(period)
            start = _next_day(end)
            taken, group = [], None
        elif low.startswith('for'):
            days, err = _day_types(token, taken)
            if err or period is None:
                problems.append(err or f'"{token}" prima di un "Through:"')
            taken += days
            group = {'days': days, 'day': None, 'interpolate': 'No', 'slots': [], 'src': []}
            if period is not None:
                period['groups'].append(group)
        elif low.startswith('interpolate') or (group is not None and not group['slots']
                                               and pending_until is None and _num(token) is None
                                               and not low.startswith('until')):
            word = next((w for w in ('Average', 'Linear', 'No') if w.upper() in token.upper()), None)
            if word is None:
                problems.append(f'interpolazione illeggibile "{token}"')
            elif group is not None:
                group['interpolate'] = word
        elif low.startswith('until'):
            pending_until = parse_time(_after(token, 'until'))
            pending_field = k
            if pending_until is None:
                problems.append(f'ora illeggibile "{token}"')
        else:
            value = _num(token)
            if value is None or pending_until is None or group is None:
                problems.append(f'valore fuori posto "{token}"')
                continue
            group['slots'].append([pending_until, value])
            group['src'].append({'time': [_target(obj, pending_field)], 'value': [_target(obj, k)]})
            pending_until = None
    return periods


def _year(obj, idx, problems):
    f = _fields(obj)
    periods = []
    rest = f[2:]
    for i in range(0, len(rest) - 4, 5):
        if not rest[i]:
            break
        nums = [int(_num(v) or 0) for v in rest[i + 1:i + 5]]
        week = idx.week.get(rest[i].upper())
        if week is None:
            problems.append(f'manca Schedule:Week "{rest[i]}"')
            continue
        periods.append({'start': nums[0:2], 'end': nums[2:4],
                        'week': str(week.obj[1]).strip(), 'weekType': week.key,
                        'groups': _week(week, idx, problems)})
    return periods


def _next_day(md):
    m, d = md
    if d < _DAYS_IN[m - 1] and not (m == 2 and d == 28):
        return [m, d + 1]
    return [1, 1] if m == 12 else [m + 1, 1]


def _check(periods, problems):
    """The coverage rules of the Schedules group."""
    expected = [1, 1]
    for p in periods:
        if p['start'] != expected and not (expected == [2, 29] and p['start'] == [3, 1]):
            problems.append(f'il periodo che inizia il {p["start"][1]}/{p["start"][0]} '
                            f'non segue il precedente')
        expected = _next_day(p['end'])
        missing = [d for d in DAY_TYPES if not any(d in g['days'] for g in p['groups'])]
        if missing:
            problems.append(f'periodo fino al {p["end"][1]}/{p["end"][0]}: '
                            f'mancano {", ".join(missing)}')
        for g in p['groups']:
            times = [s[0] for s in g['slots']]
            if not times or times[-1] != 1440:
                problems.append(f'{", ".join(g["days"]) or "un gruppo"}: il giorno non arriva a 24:00')
            if any(b < a for a, b in zip(times, times[1:])):
                problems.append(f'{", ".join(g["days"])}: orari non in ordine')
    if periods and periods[-1]['end'] != [12, 31]:
        problems.append("l'ultimo periodo non arriva al 31/12")


def read(idf, name, idx=None):
    """Any year schedule by name -> the common shape (see module docstring)."""
    idx = idx or _Index(idf)
    obj = idx.year.get(name.strip().upper())
    if obj is None:
        return None
    cls = obj.key.upper()
    f = _fields(obj)
    problems, notes = [], []
    out = {'name': f[0], 'type': obj.key, 'limits': f[1] if len(f) > 1 else '',
           'editable': cls in ('SCHEDULE:CONSTANT', 'SCHEDULE:COMPACT', 'SCHEDULE:YEAR'),
           'periods': [], 'problems': problems, 'notes': notes}
    if cls == 'SCHEDULE:CONSTANT':
        value = _num(f[2]) if len(f) > 2 else 0.0
        out['periods'] = [{'start': [1, 1], 'end': [12, 31], 'week': None,
                           'groups': [{'days': list(DAY_TYPES), 'day': None,
                                       'interpolate': 'No', 'slots': [[1440, value or 0.0]],
                                       'src': [{'time': [], 'value': [_target(obj, 2)]}]}]}]
    elif cls == 'SCHEDULE:COMPACT':
        out['periods'] = _compact(obj, problems, notes)
    elif cls == 'SCHEDULE:YEAR':
        out['periods'] = _year(obj, idx, problems)
    elif cls == 'SCHEDULE:FILE':
        out['file'] = {'path': f[2], 'column': f[3], 'rowsToSkip': f[4] if len(f) > 4 else ''}
        return out
    else:
        # ExternalInterface schedules: a name, limits and the initial value.
        out['external'] = True
        out['initialValue'] = _num(f[-1])
        return out
    _check(out['periods'], problems)
    for p in out['periods']:
        for g in p['groups']:
            keep = [k for k, sl in enumerate(g['slots']) if k == 0 or sl[0] != g['slots'][k - 1][0]]
            if len(keep) != len(g['slots']):
                notes.append('una fascia di durata zero (stesso "Until" della precedente) non conta: tolta')
                g['slots'] = [g['slots'][k] for k in keep]
                g['src'] = [g['src'][k] for k in keep]
    return out


def value_at(schedule, month, day, day_type, minute):
    """The value in force during the minute ending at `minute` (1..1440), no interpolation."""
    for p in schedule['periods']:
        if _in_period(p, month, day):
            for g in p['groups']:
                if day_type in g['days']:
                    for until, value in g['slots']:
                        if minute <= until:
                            return value
    return None


def _in_period(p, month, day):
    return tuple(p['start']) <= (month, day) <= tuple(p['end'])


# ---- writing back, keeping the object type ---------------------------------
#
# Schedule:Compact    rewritten as Compact.
# Schedule:Constant   keeps its type while the shape is one value all year;
#                     any structure makes it a Compact of the same name, which
#                     every ScheduleNames field accepts alike.
# Schedule:Year       stays a Year. Its weeks and days may be shared with other
#                     schedules, so by default (share='copy') a period whose
#                     content changed points to a new Schedule:Week:Daily and
#                     to days with the same content, existing or new.
#                     share='all' writes the changed days in place instead,
#                     changing every schedule that uses them (see day_users).
# Schedule:File, ExternalInterface:*   read-only here.

def _hhmm(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _fmt(value):
    return ('%.15g' % value) if value is not None else '0'


def _days_keywords(days, taken):
    """Shortest For: text for `days`, given the day types already assigned."""
    days = [d for d in DAY_TYPES if d in days]
    rest = [d for d in DAY_TYPES if d not in taken]
    if days == DAY_TYPES:
        return 'AllDays'
    if taken and days == rest:
        return 'AllOtherDays'
    words, left = [], list(days)
    if all(d in left for d in _WEEKDAYS):
        words.append('Weekdays')
        left = [d for d in left if d not in _WEEKDAYS]
    if 'Saturday' in left and 'Sunday' in left:
        words.append('Weekends')
        left = [d for d in left if d not in ('Saturday', 'Sunday')]
    return ' '.join(words + left)


def validate(shape):
    """The coverage rules, on a shape that came back from the editor."""
    problems = []
    _check(shape.get('periods', []), problems)
    for p in shape.get('periods', []):
        seen = []
        for g in p['groups']:
            dup = [d for d in g['days'] if d in seen]
            if dup:
                problems.append(f'{", ".join(dup)} compaiono in due gruppi')
            seen += g['days']
            times = [sl[0] for sl in g['slots']]
            if any(b == a for a, b in zip(times, times[1:])):
                problems.append(f'{", ".join(g["days"])}: due fasce finiscono alla stessa ora')
    return problems


def compact_fields(periods):
    """A shape's periods -> Schedule:Compact fields after the limits."""
    out = []
    for p in periods:
        out.append(f'Through: {p["end"][0]}/{p["end"][1]}')
        taken = []
        for g in p['groups']:
            out.append('For: ' + _days_keywords(g['days'], taken))
            taken += g['days']
            if (g.get('interpolate') or 'No').lower() != 'no':
                out.append('Interpolate: ' + g['interpolate'])
            for until, value in g['slots']:
                out += [f'Until: {_hhmm(until)}', _fmt(value)]
    return out


def _set(obj, values):
    # eppy writes at most the fields the IDD lists for a class (Schedule:Week:Compact
    # 5 day pairs, Schedule:Day:Interval 144 slots, Schedule:Year 53 weeks,
    # Schedule:Compact 10000 fields) and drops the rest on save without a word.
    if len(values) > len(obj.objidd) - 1:
        raise ValueError(f'{obj.key} "{values[0]}": {len(values)} campi, eppy ne salva al massimo '
                         f'{len(obj.objidd) - 1}; il resto andrebbe perso')
    obj.obj[:] = [obj.obj[0]] + list(values)


def _replace(idf, obj, new_class, values):
    """Swap an object for one of another class with the same name (references stay valid)."""
    new = idf.newidfobject(new_class)
    try:
        _set(new, values)
    except ValueError:
        idf.removeidfobject(new)
        raise
    idf.removeidfobject(obj)
    return new


def _day_values(day_obj, interpolate, slots):
    """Fields for day_obj's own class, or None when that class cannot hold these slots."""
    cls = day_obj.key.upper()
    f = _fields(day_obj)
    if cls == 'SCHEDULE:DAY:HOURLY':
        if interpolate.lower() != 'no' or any(u % 60 for u, _ in slots):
            return None
        return f[:2] + [_fmt(_slot_value(slots, 60 * (h + 1))) for h in range(24)]
    if cls == 'SCHEDULE:DAY:LIST':
        step = int(_num(f[3]) or 60)
        if any(u % step for u, _ in slots):
            return None
        return f[:2] + [interpolate, str(step)] + \
            [_fmt(_slot_value(slots, step * (i + 1))) for i in range(1440 // step)]
    pairs = [x for u, v in slots for x in (_hhmm(u), _fmt(v))]
    return f[:2] + [interpolate] + pairs


def _slot_value(slots, minute):
    return next(v for u, v in slots if minute <= u)


def _unique(idf, base, classes):
    taken = {str(o.obj[1]).strip().upper() for c in classes for o in idf.idfobjects.get(c, [])}
    name, i = base, 1
    while name.upper() in taken:
        i += 1
        name = f'{base} {i}'
    return name


def _content(interpolate, slots):
    return ((interpolate or 'No').lower(), tuple((u, round(v, 9)) for u, v in slots))


def day_users(idf):
    """Schedule:Day name (upper) -> [(year schedule, week)] that reach it."""
    idx = _Index(idf)
    week_days = {}
    for wname, w in idx.week.items():
        week_days[wname] = {g['day'].upper() for g in _week(w, idx, [])}
    out = {}
    for y in idf.idfobjects.get('SCHEDULE:YEAR', []):
        rest = _fields(y)[2:]
        for i in range(0, len(rest) - 4, 5):
            for d in week_days.get(rest[i].upper(), ()):
                out.setdefault(d, []).append((_fields(y)[0], rest[i]))
    return out


def _write_year(idf, obj, shape, share):
    idx = _Index(idf)
    before = read(idf, _fields(obj)[0], idx)
    name, limits = _fields(obj)[0], _fields(obj)[1]
    fields = [name, limits]
    for n, p in enumerate(shape['periods']):
        week = idx.week.get((p.get('week') or '').upper())
        old = next((q for q in before['periods'] if q.get('week') and p.get('week')
                    and q['week'].upper() == p['week'].upper()), None)
        same_partition = old is not None and \
            sorted(map(sorted, (g['days'] for g in old['groups']))) == \
            sorted(map(sorted, (g['days'] for g in p['groups'])))
        if week is not None and same_partition:
            changed = [(g, og) for g in p['groups'] for og in old['groups']
                       if sorted(g['days']) == sorted(og['days'])
                       and _content(g['interpolate'], g['slots']) != _content(og['interpolate'], og['slots'])]
            if not changed:
                fields += [str(week.obj[1]).strip(), *map(str, p['start'] + p['end'])]
                continue
            if share == 'all':
                for g, og in changed:
                    day = idx.day[og['day'].upper()]
                    values = _day_values(day, g['interpolate'], g['slots'])
                    if values is None:
                        _replace(idf, day, 'Schedule:Day:Interval',
                                 [og['day'], _fields(day)[1], g['interpolate']] +
                                 [x for u, v in g['slots'] for x in (_hhmm(u), _fmt(v))])
                    else:
                        _set(day, values)
                idx = _Index(idf)
                fields += [str(week.obj[1]).strip(), *map(str, p['start'] + p['end'])]
                continue
        fields += [_new_week(idf, name, n, p, limits), *map(str, p['start'] + p['end'])]
        idx = _Index(idf)
    _set(obj, fields)
    _drop_orphans(idf)


def _new_week(idf, schedule, n, period, limits):
    """A Schedule:Week:Daily (plus days) holding period's groups; reuse days with equal content.

    Week:Daily has a fixed field per day type, so any grouping fits; a
    Week:Compact would need one pair per group and eppy keeps only five.
    """
    idx = _Index(idf)
    by_content = {}
    for d in idx.day.values():
        interp, slots, _ = _day(d, [])
        by_content.setdefault(_content(interp, slots), str(d.obj[1]).strip())
    wname = _unique(idf, f'{schedule} settimana {n + 1}', WEEK_TYPES)
    day_of = {}
    for k, g in enumerate(period['groups']):
        key = _content(g['interpolate'], g['slots'])
        dname = by_content.get(key)
        if dname is None:
            dname = _unique(idf, f'{schedule} giorno {n + 1}.{k + 1}', DAY_SCHEDULE_TYPES)
            hourly = (g['interpolate'] or 'No').lower() == 'no' and not any(u % 60 for u, _ in g['slots'])
            if hourly:
                new = idf.newidfobject('Schedule:Day:Hourly')
                _set(new, [dname, limits] + [_fmt(_slot_value(g['slots'], 60 * (h + 1))) for h in range(24)])
            else:
                new = idf.newidfobject('Schedule:Day:Interval')
                _set(new, [dname, limits, g['interpolate'] or 'No'] +
                     [x for u, v in g['slots'] for x in (_hhmm(u), _fmt(v))])
            by_content[key] = dname
        for d in g['days']:
            day_of[d] = dname
    week = idf.newidfobject('Schedule:Week:Daily')
    _set(week, [wname] + [day_of[d] for d in DAY_TYPES])
    return wname


def _drop_orphans(idf):
    """Remove Schedule:Week/Day objects nothing references any more."""
    outside = set()
    for cls, objs in idf.idfobjects.items():
        if not objs or cls.upper().startswith('SCHEDULE:'):
            continue
        cols = [i for i, fd in enumerate(objs[0].objidd)
                if {'DayScheduleNames', 'WeekScheduleNames'} & set(fd.get('object-list') or [])]
        outside |= {str(o.obj[i]).strip().upper() for o in objs for i in cols if i < len(o.obj)}
    for _ in range(2):
        refs = set(outside)
        for cls in ('SCHEDULE:YEAR',) + WEEK_TYPES:
            for o in idf.idfobjects.get(cls, []):
                refs |= {str(v).strip().upper() for v in o.obj[2:]}
        for cls in WEEK_TYPES + DAY_SCHEDULE_TYPES:
            for o in list(idf.idfobjects.get(cls, [])):
                if str(o.obj[1]).strip().upper() not in refs:
                    idf.removeidfobject(o)


def write(idf, name, shape, share='copy'):
    """Write an edited shape back into the model; raises ValueError on an invalid shape."""
    idx = _Index(idf)
    obj = idx.year.get(name.strip().upper())
    if obj is None:
        raise ValueError(f'schedule "{name}" non trovato')
    problems = validate(shape)
    if problems:
        raise ValueError('; '.join(problems))
    cls = obj.key.upper()
    f = _fields(obj)
    periods = shape['periods']
    if cls == 'SCHEDULE:CONSTANT':
        g = periods[0]['groups'][0] if len(periods) == 1 and len(periods[0]['groups']) == 1 else None
        if g and len(g['slots']) == 1:
            _set(obj, [f[0], f[1], _fmt(g['slots'][0][1])])
            return 'Schedule:Constant'
        _replace(idf, obj, 'Schedule:Compact', [f[0], f[1]] + compact_fields(periods))
        return 'Schedule:Compact'
    if cls == 'SCHEDULE:COMPACT':
        _set(obj, [f[0], f[1]] + compact_fields(periods))
        return 'Schedule:Compact'
    if cls == 'SCHEDULE:YEAR':
        _write_year(idf, obj, shape, share)
        return 'Schedule:Year'
    raise ValueError(f'{obj.key} non si modifica da qui')


# ---- who uses a schedule, who overrides it ---------------------------------

def users(idf):
    """schedule name (upper) -> [{class, object, field}], from the IDD's ScheduleNames lists."""
    out = {}
    for cls, objs in idf.idfobjects.items():
        if not objs:
            continue
        idd = objs[0].objidd
        fields = [i for i, fd in enumerate(idd)
                  if 'ScheduleNames' in (fd.get('object-list') or [])]
        if not fields:
            continue
        group = (idd[0].get('group') or [''])[0] if isinstance(idd[0].get('group'), list) else idd[0].get('group', '')
        for obj in objs:
            for i in fields:
                if i >= len(obj.obj):
                    break
                value = str(obj.obj[i]).strip()
                if value:
                    out.setdefault(value.upper(), []).append(
                        {'class': obj.key, 'object': str(obj.obj[1]).strip(),
                         'field': idd[i].get('field', [''])[0], 'group': group})
    return out


def _called_programs(idf):
    """Upper-cased names of EMS programs a calling manager runs, directly or via RUN."""
    programs = {str(p.obj[1]).strip().upper(): [str(v) for v in p.obj[2:]]
                for cls in ('ENERGYMANAGEMENTSYSTEM:PROGRAM', 'ENERGYMANAGEMENTSYSTEM:SUBROUTINE')
                for p in idf.idfobjects.get(cls, [])}
    todo = [str(v).strip().upper()
            for m in idf.idfobjects.get('ENERGYMANAGEMENTSYSTEM:PROGRAMCALLINGMANAGER', [])
            for v in m.obj[3:] if str(v).strip()]
    called = set()
    while todo:
        name = todo.pop()
        if name in called or name not in programs:
            continue
        called.add(name)
        for line in programs[name]:
            m = re.match(r'\s*run\s+(\S+)', line, re.I)
            if m:
                todo.append(m.group(1).upper())
    return called, programs


def overrides(idf):
    """schedule name (upper) -> [{by, name, active, programs}] for run-time writers."""
    out = {}
    called, programs = _called_programs(idf)
    for a in idf.idfobjects.get('ENERGYMANAGEMENTSYSTEM:ACTUATOR', []):
        f = _fields(a)
        if len(f) < 3 or f[2].upper() not in YEAR_TYPES:
            continue
        var = f[0].upper()
        writers = [n for n, lines in programs.items()
                   if any(re.match(r'\s*set\s+' + re.escape(var) + r'\s*=', ln, re.I)
                          for ln in lines)]
        # SET x = NULL hands control back to the schedule: the override is partial.
        releases = any(re.match(r'\s*set\s+' + re.escape(var) + r'\s*=\s*null\s*$', ln, re.I)
                       for n in writers for ln in programs[n])
        out.setdefault(f[1].upper(), []).append({
            'by': 'EMS', 'name': f[0],
            'programs': writers,
            'active': any(w in called for w in writers),
            'releases': releases})
    for a in idf.idfobjects.get('EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:TO:ACTUATOR', []):
        f = _fields(a)
        if len(f) > 2 and f[2].upper() in YEAR_TYPES:
            out.setdefault(f[1].upper(), []).append(
                {'by': 'FMU', 'name': f[0], 'programs': [], 'active': True, 'releases': False})
    return out


# ---- thermostats: zone -> control -> setpoint -> schedule --------------------

_SETPOINT_SCHEDULES = {
    'THERMOSTATSETPOINT:SINGLEHEATING': [('heating', 2)],
    'THERMOSTATSETPOINT:SINGLECOOLING': [('cooling', 2)],
    'THERMOSTATSETPOINT:SINGLEHEATINGORCOOLING': [('heating or cooling', 2)],
    'THERMOSTATSETPOINT:DUALSETPOINT': [('heating', 2), ('cooling', 3)],
}
CONTROL_TYPES = {0: 'uncontrolled', 1: 'single heating', 2: 'single cooling',
                 3: 'single heating or cooling', 4: 'dual setpoint'}


def _zones_of(idf, name):
    lists = {str(z.obj[1]).strip().upper(): [str(v).strip() for v in z.obj[2:] if str(v).strip()]
             for z in idf.idfobjects.get('ZONELIST', [])}
    return lists.get(name.upper(), [name])


def thermostats(idf):
    """One entry per ZoneControl:Thermostat, with its zones and the schedule behind each role."""
    setpoints = {(cls, str(o.obj[1]).strip().upper()): o
                 for cls in _SETPOINT_SCHEDULES for o in idf.idfobjects.get(cls, [])}
    out = []
    for zc in idf.idfobjects.get('ZONECONTROL:THERMOSTAT', []):
        f = _fields(zc)
        controls = []
        for i in range(3, min(len(f), 11), 2):
            cls, name = f[i].upper(), f[i + 1] if i + 1 < len(f) else ''
            if not cls or not name:
                continue
            sp = setpoints.get((cls, name.upper()))
            schedules = {}
            if sp is not None:
                for role, pos in _SETPOINT_SCHEDULES[cls]:
                    schedules[role] = str(sp.obj[pos]).strip()
            controls.append({'type': f[i], 'name': name, 'found': sp is not None,
                             'schedules': schedules})
        out.append({'name': f[0], 'zoneOrList': f[1], 'zones': _zones_of(idf, f[1]),
                    'controlTypeSchedule': f[2], 'controls': controls})
    return out


def overview(idf):
    """Every year schedule in the model, read, with its users and overrides."""
    idx = _Index(idf)
    used, over = users(idf), overrides(idf)
    return [dict(read(idf, str(obj.obj[1]), idx),
                 users=used.get(key, []), overrides=over.get(key, []))
            for key, obj in idx.year.items()]
