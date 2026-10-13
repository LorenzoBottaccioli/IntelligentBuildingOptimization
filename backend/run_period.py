"""The simulated period, shared by the FMU export and the Control room.

One source of truth: the four period lines of Field/parameters.py, the file the
FMU export writes and gateway/building.py reads.

    parameter['fmu_step_size']   = 3600 / timesteps per hour          (s)
    parameter['fmu_start_time']  = <start day> * 60 * 60 * 24
    parameter['fmu_warmup_time'] = None | <start + warm-up days> * 60 * 60 * 24
    parameter['fmu_final_time']  = <end day> * 60 * 60 * 24

Days are counted from 1 January 00:00 (day 0). The FMU starts and stops at midnight
only, so everything is whole days. write() replaces those four lines and nothing
else: the roles, names and ranges of the export stay as they are.
"""

import ast
import datetime
import os
import re

DAY = 86400
# IDD 9.6, Timestep: "Must be evenly divisible into 60".
TIMESTEPS = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
PARAMETERS = 'parameters.py'
DEFAULT_PERIOD = {'timestep': 6, 'startDay': 0, 'warmupDays': 0, 'endDay': 7}

_NON_LEAP_YEAR = 2021  # the same convention as the export page's dayLabel


def day_date(day):
    """(month, day of month) of day number `day` (0 = 1 January), in a non-leap year."""
    when = datetime.date(_NON_LEAP_YEAR, 1, 1) + datetime.timedelta(days=int(day))
    return when.month, when.day


def day_label(day):
    when = datetime.date(_NON_LEAP_YEAR, 1, 1) + datetime.timedelta(days=int(day))
    return '{} {}'.format(when.day, when.strftime('%b'))


def validate(period):
    """Normalised period dict, or a ValueError naming what is wrong."""
    try:
        timestep = int(period.get('timestep'))
        start = period.get('startDay')
        warm = period.get('warmupDays', 0)
        end = period.get('endDay')
        for name, value in (('start day', start), ('warm-up days', warm), ('end day', end)):
            if isinstance(value, bool) or int(value) != float(value) or int(value) < 0:
                raise ValueError('The {} must be a whole number of days (the FMU starts and stops at midnight).'.format(name))
        start, warm, end = int(start), int(warm), int(end)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith('The '):
            raise
        raise ValueError('timestep, startDay, warmupDays and endDay must be numbers.')
    if timestep not in TIMESTEPS:
        raise ValueError('Timesteps per hour must divide 60: one of {}.'.format(', '.join(map(str, TIMESTEPS))))
    if end > 365:
        raise ValueError('The end day must be at most 365.')
    if start + warm >= end:
        raise ValueError('The controller must get at least one day: start + warm-up must be before the end.')
    return {'timestep': timestep, 'startDay': start, 'warmupDays': warm, 'endDay': end}


# ---------------------------------------------------------------- parameters.py
def _eval(expr):
    """Value of a plain arithmetic expression ('7 * 60 * 60 * 24', '600', 'None')."""
    node = ast.parse(expr.strip(), mode='eval').body

    def walk(n):
        if isinstance(n, ast.Constant) and (n.value is None or isinstance(n.value, (int, float))):
            return n.value
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mult, ast.Add, ast.Sub, ast.Div)):
            a, b = walk(n.left), walk(n.right)
            return {ast.Mult: lambda: a * b, ast.Add: lambda: a + b,
                    ast.Sub: lambda: a - b, ast.Div: lambda: a / b}[type(n.op)]()
        raise ValueError('not plain arithmetic')
    return walk(node)


def _line_re(key):
    return re.compile(r"^(?P<head>\s*parameter\['{}'\]\s*=\s*)(?P<expr>[^#\n]*?)(?P<tail>\s*(#.*)?)$".format(key),
                      re.MULTILINE)


def read(field_dir, model_timestep=None):
    """The period as the export page shows it. `exists` is False before any export."""
    path = os.path.join(field_dir, PARAMETERS)
    result = dict(DEFAULT_PERIOD, exists=False)
    if model_timestep in TIMESTEPS:
        result['timestep'] = model_timestep
    try:
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
    except OSError:
        return result
    values = {}
    for key in ('fmu_step_size', 'fmu_start_time', 'fmu_warmup_time', 'fmu_final_time'):
        match = _line_re(key).search(text)
        if not match:
            return result
        try:
            values[key] = _eval(match.group('expr'))
        except (ValueError, SyntaxError, ZeroDivisionError):
            return result
    step = values['fmu_step_size']
    if not step or 3600 % step or int(3600 // step) not in TIMESTEPS:
        return result
    start = values['fmu_start_time'] / DAY
    end = values['fmu_final_time'] / DAY
    # fmu_warmup_time is the absolute moment the controller starts acting.
    control = start if values['fmu_warmup_time'] is None else values['fmu_warmup_time'] / DAY
    result.update(exists=True, timestep=int(3600 // step), startDay=int(start),
                  warmupDays=int(control - start), endDay=int(end))
    return result


def _lines(period):
    p = validate(period)
    control = p['startDay'] + p['warmupDays']
    if p['warmupDays'] > 0:
        warm = ('{c} * 60 * 60 * 24  # absolute: controller acts from day {c} ({l}); days {s}-{c} run with '
                'every action = 0').format(c=control, l=day_label(control), s=p['startDay'])
    else:
        warm = 'None  # no fmi_gym warm-up: the controller acts from the start'
    return {
        'fmu_step_size': '{}  # s, = 3600 / {} timesteps per hour of the model'.format(
            3600 // p['timestep'], p['timestep']),
        'fmu_start_time': '{} * 60 * 60 * 24  # day {}, {} 00:00'.format(
            p['startDay'], p['startDay'], day_label(p['startDay'])),
        'fmu_warmup_time': warm,
        'fmu_final_time': '{} * 60 * 60 * 24  # day {}, {} 00:00'.format(
            p['endDay'], p['endDay'], day_label(p['endDay'])),
    }


def write(field_dir, period):
    """Overwrite the four period lines of Field/parameters.py. Returns the new period.

    FileNotFoundError when nothing has been exported yet: the file belongs to the export.
    """
    p = validate(period)
    path = os.path.join(field_dir, PARAMETERS)
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    for key, value in _lines(p).items():
        pattern = _line_re(key)
        if not pattern.search(text):
            raise ValueError("parameters.py has no parameter['{}'] line to overwrite.".format(key))
        text = pattern.sub(lambda m: m.group('head') + value, text, count=1)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    return p


# ------------------------------------------------------------------ the model
def model_timestep(idf_path):
    """Timesteps per hour written in the IDF, or None. A text read: no IDF parse."""
    try:
        with open(idf_path, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except (OSError, TypeError):
        return None
    match = re.search(r'^\s*Timestep\s*,\s*(\d+)\s*[;,]', text, re.IGNORECASE | re.MULTILINE)
    return int(match.group(1)) if match else None


def exported_timestep(field_dir):
    """Timesteps per hour of the last exported FMU (export_info.json), or None if not recorded."""
    import json
    try:
        with open(os.path.join(field_dir, 'export_info.json'), encoding='utf-8') as handle:
            value = json.load(handle).get('timestep')
        return int(value) if value else None
    except (OSError, ValueError, TypeError):
        return None
