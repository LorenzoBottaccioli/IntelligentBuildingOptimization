"""Zone thermostats as a designer reads them: regimes of zones, and what to vary.

How EnergyPlus controls a zone's temperature (Input Output Reference, Group -
Zone Controls - Thermostats, and Group - Schedules):

    ZoneControl:Thermostat           one per zone
      Control Type Schedule          0 none, 1 single heating, 2 single cooling,
                                     3 single heating/cooling, 4 dual setpoint
      Control Object Type / Name     the ThermostatSetpoint:* object for each type
    ThermostatSetpoint:DualSetpoint  names a heating and a cooling schedule
    ThermostatSetpoint:Single*       names one schedule
    schedule                         the setpoint in C at each timestep: a year
                                     of periods ("Through:"), day types ("For:")
                                     and hours ("Until:")

A designer does not think in those objects. They think of a zone's regime --
heating to 20 C on weekdays from 5 to 19, 16 C otherwise, from October to
April; cooling to 26 C in summer -- and of the few numbers that define it: the
comfort and setback temperatures, the hours, the season dates. So:

  regime     zones whose heating and cooling profiles are the same, whether
             they share one schedule (Office) or each has an identical copy
             (E1_RES1). One card per regime, heating and cooling together.
  levels     each temperature the profile holds, named by its role: the
             highest heating value is comfort, lower ones setback; for cooling
             the lowest is comfort. Written to every field holding it.
  hours      each time of day at which the temperature changes. When heating
             and cooling change at the same time on the same days -- they
             follow the same occupancy -- it is one variable over both.
  seasons    each date at which heating or cooling switches on or off. When
             heating ends the day cooling starts, it is one variable over both,
             so no sample can open a gap or an overlap between the seasons.

Values that switch the plant off (heating below HEATING_OFF_BELOW, cooling
above COOLING_OFF_ABOVE: the course models use -50 C and 100 C) are never a
variable: moving them turns a system on, it does not tune it.

Dates and hours are offered as a choice among nearby times, each strictly
between its neighbours, so no combination of choices can put a schedule's
times out of order -- which EnergyPlus rejects.

Only Schedule:Compact and Schedule:Constant are read for writing. A regime on a
Schedule:Year or Schedule:File is shown, and said to be read-only here.
"""

import json

import idf_session

HEATING_OFF_BELOW = 0.0
COOLING_OFF_ABOVE = 40.0

# (class, field, what it sets), field names from Energy+.idd 9.6.
_SETPOINT_FIELDS = {
    'THERMOSTATSETPOINT:DUALSETPOINT': [('Heating_Setpoint_Temperature_Schedule_Name', 'heating'),
                                        ('Cooling_Setpoint_Temperature_Schedule_Name', 'cooling')],
    'THERMOSTATSETPOINT:SINGLEHEATING': [('Setpoint_Temperature_Schedule_Name', 'heating')],
    'THERMOSTATSETPOINT:SINGLECOOLING': [('Setpoint_Temperature_Schedule_Name', 'cooling')],
    'THERMOSTATSETPOINT:SINGLEHEATINGORCOOLING': [('Setpoint_Temperature_Schedule_Name', 'both')],
}
_SCHEDULES = ('SCHEDULE:COMPACT', 'SCHEDULE:CONSTANT', 'SCHEDULE:YEAR', 'SCHEDULE:FILE')

_DAY_NAMES = {
    'weekdays': 'feriali', 'weekends': 'weekend', 'holidays': 'festivi',
    'alldays': 'tutti i giorni', 'allotherdays': 'altri giorni',
    'monday': 'lun', 'tuesday': 'mar', 'wednesday': 'mer', 'thursday': 'gio',
    'friday': 'ven', 'saturday': 'sab', 'sunday': 'dom',
    'customday1': 'giorno speciale 1', 'customday2': 'giorno speciale 2',
}
_DESIGN_DAYS = {'summerdesignday', 'winterdesignday'}
_MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_MONTHS_IT = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
_DAYS_IN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


# ---- small readers --------------------------------------------------------

def _raw(obj, field):
    try:
        return obj.obj[obj.fieldnames.index(field)]
    except (ValueError, IndexError):
        return ''


def _num(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _doy(month, day):
    return sum(_DAYS_IN[:month - 1]) + day


def _date(doy):
    m = 0
    while doy > _DAYS_IN[m]:
        doy -= _DAYS_IN[m]
        m += 1
    return m + 1, doy


def date_label(doy):
    m, d = _date(doy)
    return f'{d} {_MONTHS_IT[m - 1]}'


def _parse_date(text):
    t = text.strip().lower().replace(',', ' ')
    if '/' in t:
        m, d = t.split('/')[:2]
        return _doy(int(m), int(d))
    parts = t.split()
    for i, part in enumerate(parts):
        for n, name in enumerate(_MONTHS_EN):
            if part.startswith(name.lower()):
                other = parts[1 - i] if len(parts) > 1 else '1'
                return _doy(n + 1, int(''.join(c for c in other if c.isdigit()) or 1))
    return None


def _parse_hour(text):
    t = str(text).strip()
    if ':' in t:
        h, m = t.split(':')[:2]
        return int(h) + int(m) / 60
    return _num(t)


def hour_label(h):
    return f'{int(h):02d}:{int(round((h % 1) * 60)):02d}'


def _days(tokens):
    kept = [t for t in tokens if t.lower() not in _DESIGN_DAYS]
    return [_DAY_NAMES.get(t.lower(), t) for t in kept]


# ---- a setpoint schedule, read with the field behind every number --------

def read(obj):
    """A schedule as periods -> day groups -> blocks, each number with its field.

        {'writable': bool,
         'periods': [{'start': doy, 'end': doy, 'endField': str|None,
                      'groups': [{'days': [..], 'blocks': [
                          {'from': h, 'to': h, 'toField': str|None,
                           'value': v, 'valueField': str}]}]}]}
    """
    key = obj.key.upper()
    if key == 'SCHEDULE:CONSTANT':
        v = _num(_raw(obj, 'Hourly_Value'))
        return {'writable': True, 'periods': [{
            'start': 1, 'end': 365, 'endField': None, 'groups': [{
                'days': ['tutti i giorni'], 'blocks': [{
                    'from': 0.0, 'to': 24.0, 'toField': None,
                    'value': v, 'valueField': 'Hourly_Value'}]}]}]}
    if key != 'SCHEDULE:COMPACT':
        return {'writable': False, 'periods': []}

    periods, start, group, clock, pending = [], 1, None, 0.0, None
    names, raws = obj.fieldnames, obj.obj
    for i in range(3, min(len(names), len(raws))):
        raw = str(raws[i]).strip()
        if not raw:
            continue
        low = raw.lower()
        if low.startswith('through'):
            end = _parse_date(raw.split(':', 1)[-1] if ':' in raw else raw[7:]) or 365
            periods.append({'start': start, 'end': end, 'endField': names[i], 'groups': []})
            start, group = end + 1, None
        elif low.startswith('for'):
            tokens = (raw.split(':', 1)[-1] if ':' in raw else raw[3:]).split()
            group = {'days': _days(tokens), 'blocks': []}
            clock, pending = 0.0, None
            if periods and group['days']:
                periods[-1]['groups'].append(group)
        elif low.startswith('interpolate'):
            continue
        elif low.startswith('until'):
            pending = (_parse_hour(raw.split(':', 1)[-1]), names[i])
        else:
            v = _num(raw)
            if v is None or group is None:
                continue
            until, field = pending or (24.0, None)
            group['blocks'].append({'from': clock, 'to': until, 'toField': field,
                                    'value': v, 'valueField': names[i]})
            clock, pending = until, None
    for p in periods:
        if p['end'] >= 365:
            p['endField'] = None  # the year's end is not a choice
    return {'writable': True, 'periods': periods}


def _content(profile):
    """What a profile says, without where it says it: two zones with identical
    content are one regime even when each has its own schedule object."""
    return json.dumps([[p['start'], p['end'], [[g['days'], [[b['from'], b['to'], b['value']]
                                                          for b in g['blocks']]]
                                               for g in p['groups']]]
                       for p in profile['periods']])


def _off(kind, v):
    return v is None or (v < HEATING_OFF_BELOW if kind == 'heating' else v > COOLING_OFF_ABOVE)


# ---- regimes ----------------------------------------------------------------

def _index(idf):
    return {o.Name.upper(): o for c in _SCHEDULES for o in idf.idfobjects[c]}


def _zone_setup(idf):
    """Per zone: its thermostat, and the schedule for heating and for cooling."""
    index = _index(idf)
    setpoint_objects = {o.Name.upper(): (cls, o) for cls in _SETPOINT_FIELDS
                        for o in idf.idfobjects[cls]}
    zones = []
    for t in idf.idfobjects['ZONECONTROL:THERMOSTAT']:
        zone = {'zone': str(_raw(t, 'Zone_or_ZoneList_Name') or t.Name),
                'thermostat': t.Name, 'heating': None, 'cooling': None, 'pointers': []}
        for n in range(1, 5):
            name = str(_raw(t, f'Control_{n}_Name') or '').upper()
            if name not in setpoint_objects:
                continue
            cls, sp = setpoint_objects[name]
            for field, kind in _SETPOINT_FIELDS[cls]:
                sched = index.get(str(_raw(sp, field) or '').upper())
                if sched is None:
                    continue
                for k in (('heating', 'cooling') if kind == 'both' else (kind,)):
                    zone[k] = sched
                zone['pointers'].append({'className': sp.key, 'object': sp.Name,
                                         'field': field, 'kind': kind})
        zones.append(zone)
    return zones


def regimes(idf=None):
    """Zones grouped by what their thermostats do, with the variables of each."""
    idf = idf or idf_session.get()
    zones = _zone_setup(idf)

    # A zone can be varied alone only through schedules no other zone reads.
    readers = {}
    for z in zones:
        for k in ('heating', 'cooling'):
            if z[k] is not None:
                readers.setdefault(z[k].Name, set()).add(z['zone'])

    groups = {}
    for z in zones:
        profiles = {k: read(z[k]) if z[k] is not None else None for k in ('heating', 'cooling')}
        key = tuple(_content(p) if p else '' for p in profiles.values())
        g = groups.setdefault(key, {'zones': [], 'profiles': profiles, 'members': []})
        g['zones'].append(z['zone'])
        g['members'].append(z)

    out = []
    for g in groups.values():
        out.append(_regime(g, readers))
    out.sort(key=lambda r: -len(r['zones']))
    return {'regimes': out, 'offBelow': HEATING_OFF_BELOW, 'offAbove': COOLING_OFF_ABOVE}


def _targets(members, kind, pick):
    """Every (schedule, field) across the regime's zones for one number."""
    out, seen = [], set()
    for z in members:
        sched = z[kind]
        if sched is None or sched.Name in seen:
            continue
        seen.add(sched.Name)
        for field in pick(read(sched)):
            out.append({'object': sched.Name, 'field': field, 'className': sched.key})
    return out


def _regime(g, readers):
    members, profiles = g['members'], g['profiles']
    writable = all(p is None or p['writable'] for p in profiles.values())
    regime = {
        'zones': g['zones'],
        'writable': writable,
        'schedules': {k: sorted({z[k].Name for z in members if z[k] is not None})
                      for k in ('heating', 'cooling')},
        'own': {z['zone']: all(readers.get(z[k].Name, set()) == {z['zone']}
                               for k in ('heating', 'cooling') if z[k] is not None)
                for z in members},
        'pointers': [p for z in members for p in z['pointers']],
        'zoneSchedules': {z['zone']: {k: z[k].Name for k in ('heating', 'cooling')
                                      if z[k] is not None} for z in members},
        'year': _year(profiles),
        'days': _day_rows(profiles),
        'levels': [], 'hours': [], 'seasons': [],
    }
    if not writable:
        return regime

    # Levels: each value a profile holds, named by its role.
    for kind in ('heating', 'cooling'):
        p = profiles[kind]
        if not p:
            continue
        vals = sorted({b['value'] for per in p['periods'] for gr in per['groups']
                       for b in gr['blocks'] if not _off(kind, b['value'])})
        comfort = (max(vals) if kind == 'heating' else min(vals)) if vals else None
        for v in vals:
            role = 'setpoint' if len(vals) == 1 else ('comfort' if v == comfort else 'attenuazione')
            pick = lambda prof, v=v: [b['valueField'] for per in prof['periods']
                                      for gr in per['groups'] for b in gr['blocks']
                                      if b['value'] == v]
            per_zone = {}
            for z in members:
                if regime['own'][z['zone']] and z[kind] is not None:
                    per_zone[z['zone']] = _targets([z], kind, pick)
            regime['levels'].append({
                'id': f'{kind}_{role}_{v:g}', 'kind': kind, 'role': role, 'value': v,
                'when': _when(p, v), 'targets': _targets(members, kind, pick),
                'perZone': per_zone})

    # Hours: where the temperature changes during a day, coupled across kinds.
    hours = {}
    for kind in ('heating', 'cooling'):
        p = profiles[kind]
        if not p:
            continue
        for per in p['periods']:
            if all(all(_off(kind, b['value']) for b in gr['blocks']) for gr in per['groups']):
                continue
            for gr in per['groups']:
                blocks = gr['blocks']
                for j in range(len(blocks) - 1):
                    a, b = blocks[j], blocks[j + 1]
                    if a['toField'] is None:
                        continue
                    key = (a['to'], tuple(gr['days']))
                    h = hours.setdefault(key, {'hour': a['to'], 'days': gr['days'],
                                               'kinds': set(), 'lo': 0.0, 'hi': 24.0,
                                               'fields': {}, 'rising': {}})
                    h['kinds'].add(kind)
                    h['lo'] = max(h['lo'], a['from'])
                    h['hi'] = min(h['hi'], b['to'])
                    h['fields'].setdefault(kind, set()).add(a['toField'])
                    warmer = b['value'] > a['value']
                    h['rising'][kind] = warmer if kind == 'heating' else not warmer
    for (hour, _), h in sorted(hours.items()):
        options = [hour + d for d in (-3, -2, -1, 0, 1, 2, 3)
                   if (h['lo'] + hour) / 2 < hour + d < (hour + h['hi']) / 2 or d == 0]
        if len(options) < 2:
            continue
        targets = []
        for kind in sorted(h['kinds']):
            fields = h['fields'][kind]
            targets += _targets(members, kind, lambda prof, fields=fields: sorted(fields))
        into_comfort = any(h['rising'].values())
        regime['hours'].append({
            'id': f'hour_{hour_label(hour)}_{"_".join(h["days"])}',
            'hour': hour, 'label': hour_label(hour), 'days': ', '.join(h['days']),
            'kinds': sorted(h['kinds']),
            'meaning': 'inizio comfort' if into_comfort else 'fine comfort',
            'options': [f'Until: {hour_label(o)}' for o in options],
            'labels': {f'Until: {hour_label(o)}': hour_label(o) for o in options},
            'current': f'Until: {hour_label(hour)}', 'targets': targets,
            # The range a student may pick from, whole hours strictly between the
            # midpoints to the neighbouring changes: any choice keeps the order.
            'min': int(-(-((h['lo'] + hour) / 2 + 1e-9) // 1)),
            'max': int(((hour + h['hi']) / 2 - 1e-9) // 1)})

    # Seasons: dates at which a kind switches on or off, coupled across kinds.
    dates = {}
    for kind in ('heating', 'cooling'):
        p = profiles[kind]
        if not p:
            continue
        active = [not all(all(_off(kind, b['value']) for b in gr['blocks']) for gr in per['groups'])
                  for per in p['periods']]
        for n, per in enumerate(p['periods'][:-1]):
            # A switch on or off, or a change between two periods that are
            # both on -- the date a student split the year at, for instance.
            if per['endField'] is None or (not active[n] and not active[n + 1]):
                continue
            lo = p['periods'][n]['start']
            hi = p['periods'][n + 1]['end']
            d = dates.setdefault(per['end'], {'end': per['end'], 'events': [], 'lo': 0, 'hi': 366,
                                             'fields': {}})
            d['events'].append((kind, 'cambio' if active[n] and active[n + 1]
                                else 'fine' if active[n] else 'inizio'))
            d['lo'] = max(d['lo'], lo)
            d['hi'] = min(d['hi'], hi)
            d['fields'].setdefault(kind, set()).add(per['endField'])
    for end, d in sorted(dates.items()):
        options = [end + k for k in (-30, -15, 0, 15, 30)
                   if ((d['lo'] + end) / 2 < end + k < (end + d['hi']) / 2 or k == 0)
                   and 1 <= end + k <= 364]
        if len(options) < 2:
            continue
        targets = []
        for kind, fields in sorted(d['fields'].items()):
            targets += _targets(members, kind, lambda prof, fields=fields: sorted(fields))
        what = {'heating': 'riscaldamento', 'cooling': 'raffrescamento'}
        events = [f'{role} {"periodo " if role == "cambio" else ""}{what[k]}'
                  for k, role in d['events']]
        regime['seasons'].append({
            'id': f'season_{end}', 'end': end, 'label': date_label(end),
            'next': date_label(end + 1), 'events': events,
            'options': [f'Through: {_date(o)[1]} {_MONTHS_EN[_date(o)[0] - 1]}' for o in options],
            'labels': {f'Through: {_date(o)[1]} {_MONTHS_EN[_date(o)[0] - 1]}':
                       f'{date_label(o)} / {date_label(o + 1)}' for o in options},
            'current': f'Through: {_date(end)[1]} {_MONTHS_EN[_date(end)[0] - 1]}',
            'targets': targets,
            # Day-of-year range allowed, strictly between the midpoints to the
            # neighbouring dates; the panel turns a chosen range into options.
            'min': max(1, int((d['lo'] + end) / 2) + 1), 'max': min(364, int((end + d['hi']) / 2) - 1)})
    regime['view'] = _view(members, profiles, regime)
    return regime


# ---- the schedule as a timetable, every number with its fields --------------

def _view(members, profiles, regime):
    """Each kind's seasons, day types and time slots, as the panel lays them out.

    Every slot carries the fields that hold its temperature -- in every period
    that says the same thing and in every zone schedule of the regime -- so a
    box in the timetable writes exactly where that number lives. The hours
    between slots and the season dates point at the regime's hour and season
    entries, which already couple heating and cooling where they coincide.
    """
    parsed = {k: [(z, read(z[k])) for z in members if z[k] is not None]
              for k in ('heating', 'cooling')}
    out = []
    for kind in ('heating', 'cooling'):
        p = profiles[kind]
        if not p:
            continue
        active = [not all(all(_off(kind, b['value']) for b in gr['blocks']) for gr in per['groups'])
                  for per in p['periods']]
        if not any(active):
            out.append({'kind': kind, 'never': True})
            continue

        # Active periods with the same content are one season (both winters).
        seasons = []
        for n, per in enumerate(p['periods']):
            if not active[n]:
                continue
            sig = json.dumps([[g['days'], [[b['from'], b['to'], b['value']] for b in g['blocks']]]
                              for g in per['groups']])
            # Identical periods are one season only when something else lies
            # between them (the two winters); side by side they stay two, so a
            # date the student put between them can be seen and moved.
            same = next((x for x in seasons if x['sig'] == sig
                         and x['periods'][-1] != n - 1), None)
            if same:
                same['periods'].append(n)
            else:
                seasons.append({'sig': sig, 'periods': [n]})

        for season in seasons:
            pers = [p['periods'][n] for n in season['periods']]
            spans = [[x['start'], x['end']] for x in pers]
            # A season across the new year reads as one span: 15 ott - 15 apr.
            if len(spans) > 1 and spans[0][0] == 1 and spans[-1][1] >= 365:
                last = spans.pop()
                spans[0] = [last[0], spans[0][1]]
            span_out = []
            for a, b in spans:
                start = next((x['id'] for x in regime['seasons'] if x['end'] == a - 1), None)
                end = next((x['id'] for x in regime['seasons'] if x['end'] == b), None)
                span_out.append({'start': a, 'end': b, 'startSeason': start, 'endSeason': end})

            groups = []
            first = pers[0]
            for gi, gr in enumerate(first['groups']):
                days = ', '.join(gr['days'])
                blocks = []
                for j, bl in enumerate(gr['blocks']):
                    targets = []
                    for z, prof in parsed[kind]:
                        for n in season['periods']:
                            try:
                                field = prof['periods'][n]['groups'][gi]['blocks'][j]['valueField']
                            except (IndexError, KeyError):
                                continue
                            t = {'object': z[kind].Name, 'field': field, 'className': z[kind].key}
                            if t not in targets:
                                targets.append(t)
                    hour_id = lambda h: next((x['id'] for x in regime['hours']
                                              if x['hour'] == h and x['days'] == days), None)
                    blocks.append({'from': bl['from'], 'to': bl['to'], 'value': bl['value'],
                                   'off': _off(kind, bl['value']), 'targets': targets,
                                   'fromHour': hour_id(bl['from']) if j > 0 else None,
                                   'toHour': hour_id(bl['to']) if j < len(gr['blocks']) - 1 else None})
                # Day types with identical slots are one line (weekend, holidays).
                same = next((g for g in groups
                             if [(b['from'], b['to'], b['value']) for b in g['blocks']] ==
                             [(b['from'], b['to'], b['value']) for b in blocks]), None)
                if same:
                    same['days'] += ', ' + days
                    for b_same, b_new in zip(same['blocks'], blocks):
                        b_same['targets'] += [t for t in b_new['targets'] if t not in b_same['targets']]
                else:
                    groups.append({'days': days, 'blocks': blocks})
            if all(all(b['off'] for b in g['blocks']) for g in groups):
                continue
            out.append({'kind': kind, 'allYear': spans == [[1, 365]] or spans == [[1, 366]],
                        'spans': span_out, 'groups': groups})
    return out


def edit(idf, changes):
    """Write new values into setpoint schedules, refusing any that break order.

    Each change is {targets: [{object, className, field}], value: str}. A value
    goes where a value is, an "Until: HH:MM" where an hour is, a "Through: D
    Mon" where a date is. After writing, every touched schedule is read again:
    dates must still increase through the year and hours through each day, or
    everything is put back and the edit refused -- EnergyPlus would reject it.
    """
    index = _index(idf)
    old, touched = [], {}
    try:
        for ch in changes:
            value = str(ch.get('value', '')).strip()
            for t in ch.get('targets') or []:
                obj = index.get(str(t.get('object', '')).upper())
                field = t.get('field')
                if obj is None or field not in obj.fieldnames:
                    raise ValueError(f'{t.get("object")}.{field} non esiste nel modello.')
                now = str(getattr(obj, field) or '').strip()
                kind_now = now.lower().split(':')[0] if now.lower().startswith(('until', 'through')) else 'value'
                kind_new = value.lower().split(':')[0] if value.lower().startswith(('until', 'through')) else 'value'
                if kind_now != kind_new or (kind_new == 'value' and _num(value) is None):
                    raise ValueError(f'{obj.Name}.{field}: {value!r} non va in un campo che contiene {now!r}.')
                old.append((obj, field, getattr(obj, field)))
                setattr(obj, field, float(value) if kind_new == 'value' else value)
                touched[obj.Name] = obj
        for obj in touched.values():
            prof = read(obj)
            ends = [per['end'] for per in prof['periods']]
            if ends != sorted(ends) or len(set(ends)) != len(ends):
                raise ValueError(f'{obj.Name}: le date non sarebbero piu in ordine.')
            for per in prof['periods']:
                for gr in per['groups']:
                    hours = [b['to'] for b in gr['blocks']]
                    if hours != sorted(hours) or len(set(hours)) != len(hours):
                        raise ValueError(f'{obj.Name}: gli orari non sarebbero piu in ordine.')
    except ValueError:
        for obj, field, value in reversed(old):
            setattr(obj, field, value)
        raise
    return len(old)


def _when(profile, v):
    """Where a value applies, in words: days and hours, then the periods."""
    spans = {}
    for per in profile['periods']:
        for gr in per['groups']:
            blocks = [b for b in gr['blocks'] if b['value'] == v]
            if not blocks:
                continue
            hours = 'tutto il giorno' if len(blocks) == 1 and blocks[0]['from'] == 0                 and blocks[0]['to'] == 24 else                 'ore ' + ', '.join(f'{hour_label(b["from"])}-{hour_label(b["to"])}' for b in blocks)
            key = f'{", ".join(gr["days"])} {hours}'
            period = None if per['start'] == 1 and per['end'] >= 365 else                 f'{date_label(per["start"])} - {date_label(per["end"])}'
            spans.setdefault(key, [])
            if period and period not in spans[key]:
                spans[key].append(period)
    return '; '.join(f'{k} ({", ".join(p)})' if p else k for k, p in spans.items())


def _year(profiles):
    """The year as segments: which of heating and cooling are on, day by day."""
    marks = {1, 366}
    for p in profiles.values():
        if p:
            for per in p['periods']:
                marks.add(per['start'])
                marks.add(min(per['end'], 365) + 1)
    marks = sorted(m for m in marks if 1 <= m <= 366)
    out = []
    for a, b in zip(marks, marks[1:]):
        on = {}
        for kind, p in profiles.items():
            per = next((x for x in (p or {}).get('periods', []) if x['start'] <= a <= x['end']), None)
            on[kind] = bool(per) and not all(all(_off(kind, bl['value']) for bl in gr['blocks'])
                                            for gr in per['groups'])
        if out and out[-1]['heating'] == on['heating'] and out[-1]['cooling'] == on['cooling']:
            out[-1]['to'] = b - 1
        else:
            out.append({'from': a, 'to': b - 1, **on,
                        'label': f'{date_label(a)} - {date_label(b - 1)}'})
    return out


def _day_rows(profiles):
    """For each period in which something is on, the day groups with both kinds' blocks."""
    rows = []
    heat, cool = profiles.get('heating'), profiles.get('cooling')
    marks = sorted({per['start'] for p in (heat, cool) if p for per in p['periods']})
    for start in marks:
        row = {'start': start, 'groups': {}}
        for kind, p in (('heating', heat), ('cooling', cool)):
            per = next((x for x in (p or {}).get('periods', []) if x['start'] <= start <= x['end']), None)
            if not per:
                continue
            row['end'] = min(row.get('end', 365), per['end'])
            for gr in per['groups']:
                if all(_off(kind, b['value']) for b in gr['blocks']):
                    continue
                days = ', '.join(gr['days'])
                row['groups'].setdefault(days, {})[kind] = [
                    {'from': b['from'], 'to': b['to'], 'value': b['value'],
                     'off': _off(kind, b['value'])} for b in gr['blocks']]
        if row['groups']:
            # Day types with the same hours are one line: weekend and holidays
            # at 16 C all day read once.
            joined = {}
            for days, content in row['groups'].items():
                same = next((k for k, c in joined.items() if c == content), None)
                if same:
                    joined[f'{same}, {days}'] = joined.pop(same)
                else:
                    joined[days] = content
            row['groups'] = joined
            row['label'] = f'{date_label(start)} - {date_label(row.get("end", 365))}'
            rows.append(row)
    # Identical rows (the same days in two periods, e.g. both winters) read once.
    merged = []
    for r in rows:
        same = next((m for m in merged if m['groups'] == r['groups']), None)
        if same:
            same['label'] += f' e {r["label"]}'
        else:
            merged.append(r)
    for r in merged:
        if r['label'] == f'{date_label(1)} - {date_label(365)}':
            r['label'] = "tutto l'anno"
    return merged


# ---- giving a profile more structure ---------------------------------------
#
# A Schedule:Constant has no hours and no seasons, so there is nothing in it to
# move. To vary when something happens, the profile first needs the moment in
# it: a change of hour in a day, or a change of period in the year. These add
# one, with the same temperature on both sides, so the model behaves exactly as
# before until a value changes. A Schedule:Constant becomes the equivalent
# Schedule:Compact under the same name -- every reference to it still holds.

def _structure(obj):
    """A Constant or Compact schedule as periods -> day groups -> blocks, raw."""
    key = obj.key.upper()
    limits = str(_raw(obj, 'Schedule_Type_Limits_Name') or '')
    if key == 'SCHEDULE:CONSTANT':
        v = _raw(obj, 'Hourly_Value')
        return {'limits': limits, 'periods': [{'end': 365, 'groups': [
            {'tokens': ['AllDays'], 'blocks': [[24.0, v]]}]}]}
    if key != 'SCHEDULE:COMPACT':
        raise ValueError(f'{obj.Name}: uno schedule {obj.key} qui non si ristruttura.')
    periods, group, pending = [], None, None
    for raw in obj.obj[3:]:
        raw = str(raw).strip()
        if not raw:
            continue
        low = raw.lower()
        if low.startswith('through'):
            end = _parse_date(raw.split(':', 1)[-1] if ':' in raw else raw[7:]) or 365
            periods.append({'end': end, 'groups': []})
            group = None
        elif low.startswith('for'):
            group = {'tokens': (raw.split(':', 1)[-1] if ':' in raw else raw[3:]).split(),
                     'blocks': []}
            periods[-1]['groups'].append(group)
        elif low.startswith('interpolate'):
            continue
        elif low.startswith('until'):
            pending = _parse_hour(raw.split(':', 1)[-1])
        elif group is not None:
            group['blocks'].append([pending if pending is not None else 24.0, raw])
            pending = None
    return {'limits': limits, 'periods': periods}


def _write_structure(idf, obj, st):
    """Replace a schedule by a Schedule:Compact saying `st`, under the same name."""
    fields = []
    for per in st['periods']:
        m, d = _date(per['end'])
        fields.append(f'Through: {d} {_MONTHS_EN[m - 1]}')
        for g in per['groups']:
            fields.append('For: ' + ' '.join(g['tokens']))
            for until, value in g['blocks']:
                fields.append(f'Until: {hour_label(until)}')
                fields.append(str(value))
    name = obj.Name
    idf.removeidfobject(obj)
    new = idf.newidfobject('SCHEDULE:COMPACT')
    new.Name = name
    new.Schedule_Type_Limits_Name = st['limits']
    for i, value in enumerate(fields):
        setattr(new, f'Field_{i + 1}', value)
    return new


def _label_of(tokens):
    return ', '.join(_days(tokens))


def add_hour(idf, schedules, days, hour):
    """Split, at `hour`, the block containing it in the day groups labelled `days`."""
    if not 0 < hour < 24:
        raise ValueError('L ora deve essere fra 00:00 e 24:00.')
    index = _index(idf)
    wanted = set(d.strip() for d in days.split(','))
    done = 0
    for name in schedules:
        obj = index.get(name.upper())
        if obj is None:
            raise ValueError(f'Lo schedule {name!r} non esiste.')
        st = _structure(obj)
        for per in st['periods']:
            for g in per['groups']:
                label = set(d.strip() for d in _label_of(g['tokens']).split(','))
                if not label or not label <= wanted:
                    continue
                start = 0.0
                for i, (until, value) in enumerate(g['blocks']):
                    if start < hour < until:
                        g['blocks'].insert(i, [hour, value])
                        done += 1
                        break
                    start = until
        _write_structure(idf, obj, st)
    return done


def add_season(idf, schedules, at):
    """Split, after day-of-year `at`, the period containing it into two equal ones."""
    if not 1 <= at < 365:
        raise ValueError('La data deve essere fra il 1 gen e il 30 dic.')
    index = _index(idf)
    for name in schedules:
        obj = index.get(name.upper())
        if obj is None:
            raise ValueError(f'Lo schedule {name!r} non esiste.')
        st = _structure(obj)
        start = 1
        for i, per in enumerate(st['periods']):
            if start <= at < per['end']:
                copy = json.loads(json.dumps(per))
                copy['end'] = at
                st['periods'].insert(i, copy)
                break
            start = per['end'] + 1
        _write_structure(idf, obj, st)
    return len(schedules)


# ---- making one zone independent -------------------------------------------

def make_independent(idf, zone):
    """Give one zone its own copy of every setpoint schedule it shares.

    The zone's setpoint object is copied too when other thermostats use it,
    and its thermostat pointed at the copy. Nothing else changes: the copies
    say what the originals said, so the model behaves as before until a design
    point varies one zone.
    """
    setup = {z['zone']: z for z in _zone_setup(idf)}
    if zone not in setup:
        raise ValueError(f'La zona {zone!r} non ha un termostato.')
    z = setup[zone]
    thermostat = idf.getobject('ZONECONTROL:THERMOSTAT', z['thermostat'])
    readers = {}
    for other in setup.values():
        for k in ('heating', 'cooling'):
            if other[k] is not None:
                readers.setdefault(other[k].Name, set()).add(other['zone'])
    users = {}
    for t in idf.idfobjects['ZONECONTROL:THERMOSTAT']:
        for n in range(1, 5):
            users.setdefault(str(_raw(t, f'Control_{n}_Name') or '').upper(), set()).add(t.Name)

    made, copies = [], {}
    for p in z['pointers']:
        sp = idf.getobject(p['className'].upper(), p['object'])
        if len(users.get(sp.Name.upper(), set())) > 1:
            new = idf.copyidfobject(sp)
            new.Name = f'{sp.Name} - {zone}'
            for n in range(1, 5):
                if str(_raw(thermostat, f'Control_{n}_Name') or '').upper() == sp.Name.upper():
                    setattr(thermostat, f'Control_{n}_Name', new.Name)
            users[sp.Name.upper()].discard(thermostat.Name)
            sp = new
            made.append(new.Name)
        sched_name = str(getattr(sp, p['field']) or '')
        if readers.get(sched_name, set()) - {zone}:
            if sched_name not in copies:
                original = _index(idf)[sched_name.upper()]
                copy = idf.copyidfobject(original)
                copy.Name = f'{original.Name} - {zone}'
                copies[sched_name] = copy.Name
                made.append(copy.Name)
            setattr(sp, p['field'], copies[sched_name])
    return made
