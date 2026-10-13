"""Run the model in EnergyPlus alone -- no FMU, no gateway -- and store what the FMU would carry.

The FMU exposes two things to the BMS: outputs (ExternalInterface ... From:Variable, what the
building sends) and inputs (To:Schedule, To:Actuator, To:Variable, what the controller sends).
Without an FMU nobody sends the inputs: the building follows its own logic (thermostats and
schedules, and the model's own EMS). This module runs that case and records, for every FMU
point, the value EnergyPlus itself computed:

    outputs   the very Output:Variable the From:Variable reads (EMS chain included)
    inputs    To:Schedule  -> 'Schedule Value' of that schedule (exact)
              To:Actuator / To:Variable -> what the actuated component natively does:
                  1. the model's own EMS:Actuator on the same component/type/control, read
                     through an EMS output variable;
                  2. otherwise a native report variable, only the ones in NATIVE_INPUTS
                     (each verified against EnergyPlus 9.6 before being listed);
                  3. otherwise the point is reported as "not observable", never invented.

The run IDF is the export's baseline model (platform inputs removed, model_converter
._make_baseline_idf) with the shared period, Output:SQLite and the requested
variables at Timestep. Results are read from eplusout.sql and written to InfluxDB.
"""

import datetime
import glob
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time

import ems_chain
import run_period

DIRECT_DATABASE = 'direct_building'
MEASUREMENT = 'points'
RUN_TAG = 'direct'
WORK_DIR = os.path.join('simulation_outputs', 'direct')
ENERGYPLUS_BIN = '/EnergyPlus-9.6.0-4b123cf80f-Linux-Ubuntu20.04-x86_64/energyplus-9.6.0'
BATCH = 5000

# Actuated (component type, control type) -> native report variable, keyed by the component name.
# Only what was checked: "Zone Temperature Control" heating setpoint on test.idf and
# lab_optimal.idf, 7 days, 1008 rows per timestep each (tests/integrity/direct_run_check.py).
# Where the thermostat has no active setpoint EnergyPlus reports its own sentinel (-50 for heating
# was seen in a July week of lab_optimal); it is stored as reported.
NATIVE_INPUTS = {
    ('zone temperature control', 'heating setpoint'): 'Zone Thermostat Heating Setpoint Temperature',
    ('zone temperature control', 'cooling setpoint'): 'Zone Thermostat Cooling Setpoint Temperature',
}

_lock = threading.RLock()
_thread = None
_proc = None
_stop = threading.Event()
_state = {'state': 'idle', 'message': '', 'progress': 0, 'sim_date': None, 'period': None,
          'points': [], 'not_observable': [], 'rows': 0, 'rows_total': 0, 'severe': 0,
          'started': None, 'finished': None, 'database': DIRECT_DATABASE}


# ------------------------------------------------------------------------ state
def snapshot():
    with _lock:
        return dict(_state, points=list(_state['points']), not_observable=list(_state['not_observable']))


def is_active():
    return snapshot()['state'] in ('building', 'running', 'writing')


def _set(**kw):
    with _lock:
        _state.update(kw)


# ---------------------------------------------------------------------- planning
def _norm(text):
    return str(text or '').strip().upper()


def _program_text(idf):
    chunks = []
    for cls in ('EnergyManagementSystem:Program', 'EnergyManagementSystem:Subroutine'):
        for obj in idf.idfobjects[cls]:
            chunks += [str(v) for v in obj.obj[2:] if v]
    return '\n'.join(chunks)


def _apply_target(idf, to_variable_name):
    """(component, type, control) the platform's apply-program drives for a To:Variable, or None."""
    name = str(to_variable_name)
    actuator_name = '{}{}'.format(name, ems_chain.ACTUATOR_SUFFIX)
    program = ems_chain._apply_program_name(name)
    if not any(str(p.Name) == program for p in idf.idfobjects['EnergyManagementSystem:Program']):
        return None
    for act in idf.idfobjects['EnergyManagementSystem:Actuator']:
        if str(act.Name) == actuator_name:
            return (str(act.Actuated_Component_Unique_Name), str(act.Actuated_Component_Type),
                    str(act.Actuated_Component_Control_Type))
    return None


def _own_ems_actuator(idf, target, skip_names):
    """The model's own EMS:Actuator on `target`, ignoring the ones the platform built."""
    component, ctype, control = (_norm(x) for x in target)
    for act in idf.idfobjects['EnergyManagementSystem:Actuator']:
        if str(act.Name) in skip_names:
            continue
        if (_norm(act.Actuated_Component_Unique_Name), _norm(act.Actuated_Component_Type),
                _norm(act.Actuated_Component_Control_Type)) == (component, ctype, control):
            return str(act.Name)
    return None


def plan_points(idf, model_name):
    """Every point of the FMU interface of `idf` (the working model, FMU objects in place).

    Each entry: id, fmu, type (measurement|command), role, unit, plus `source`:
      {'key', 'variable'}          an Output:Variable that exists in the model;
      {'ems_actuator': <Erl name>} to expose through an EMS output variable;
      None                         not observable, with `reason`.
    """
    import model_converter
    points = model_converter._build_points(idf, model_name)[1]
    by_fmu = {p['fmu']: p for p in points}

    for obj in idf.idfobjects[ems_chain.FROM_VARIABLE]:
        by_fmu[str(obj.FMU_Variable_Name)]['source'] = {
            'key': str(obj.OutputVariable_Index_Key_Name), 'variable': str(obj.OutputVariable_Name)}

    platform_actuators = {'{}{}'.format(o.Name, ems_chain.ACTUATOR_SUFFIX)
                          for o in idf.idfobjects[ems_chain.TO_VARIABLE]}

    def resolve(target):
        own = _own_ems_actuator(idf, target, platform_actuators)
        if own:
            return {'ems_actuator': own}, None
        variable = NATIVE_INPUTS.get((target[1].strip().lower(), target[2].strip().lower()))
        if variable:
            return {'key': target[0], 'variable': variable}, None
        return None, 'no native report variable for {} / {}'.format(target[1], target[2])

    for obj in idf.idfobjects[ems_chain.TO_SCHEDULE]:
        by_fmu[str(obj.FMU_Variable_Name)]['source'] = {
            'key': str(obj.Schedule_Name), 'variable': 'Schedule Value'}
    for obj in idf.idfobjects[ems_chain.TO_ACTUATOR]:
        target = (str(obj.Actuated_Component_Unique_Name), str(obj.Actuated_Component_Type),
                  str(obj.Actuated_Component_Control_Type))
        p = by_fmu[str(obj.FMU_Variable_Name)]
        p['source'], p['reason'] = resolve(target)
    for obj in idf.idfobjects[ems_chain.TO_VARIABLE]:
        p = by_fmu[str(obj.FMU_Variable_Name)]
        target = _apply_target(idf, obj.Name)
        if target:
            p['source'], p['reason'] = resolve(target)
        else:
            p['source'], p['reason'] = None, 'a variable of the EMS programs: nothing writes it without the FMU'
    for p in points:
        p.setdefault('source', None)
    return points


def _ensure_timestep_output(idf, key, variable):
    for obj in idf.idfobjects['Output:Variable']:
        if (_norm(obj.Key_Value), _norm(obj.Variable_Name)) == (_norm(key), _norm(variable)) \
                and _norm(obj.Reporting_Frequency) == 'TIMESTEP':
            return
    obj = idf.newidfobject('Output:Variable')
    obj.Key_Value = key
    obj.Variable_Name = variable
    obj.Reporting_Frequency = 'Timestep'


def build_run_idf(working_idf, target_idf, period, model_name, prune=True):
    """Write the IDF the direct run executes; returns the planned points (with `query` keys).

    Raises ValueError when the model cannot run without the FMU.
    """
    import model_converter
    from eppy.modeleditor import IDF
    IDF.setiddname(model_converter.IDD_PATH)

    plan = plan_points(IDF(working_idf), model_name)
    model_converter._make_baseline_idf(working_idf, target_idf)
    idf = IDF(target_idf)

    # A To:Variable left by hand is an Erl global of the model's own programs; without the
    # FMU that global would not exist, and the programs would fail to compile.
    text = _program_text(idf)
    for obj in idf.idfobjects[ems_chain.TO_VARIABLE]:
        if re.search(r'\b{}\b'.format(re.escape(str(obj.Name))), text, re.IGNORECASE):
            raise ValueError(
                'The EMS programs read "{}", an FMU input declared by hand: without the FMU nothing '
                'gives it a value. Run through the FMU, or rewrite that program.'.format(obj.Name))

    # An EMS output the baseline model no longer has: the chain of an FMU input (its '<name>_status'),
    # removed together with that input. What it reports is the input itself, stored under its own name.
    ems_outputs = {str(o.Name) for o in idf.idfobjects['EnergyManagementSystem:OutputVariable']}
    for p in plan:
        src = p['source']
        if p['type'] == 'measurement' and src and _norm(src['key']) == _norm(ems_chain.EMS_KEY) \
                and src['variable'] not in ems_outputs:
            p['source'], p['reason'] = None, 'reports an FMU input: stored as that input'

    keep = set()
    for p in plan:
        src = p['source']
        if src is None:
            continue
        if 'ems_actuator' in src:
            name = ems_chain.sanitize_name('{}_native'.format(p['fmu']))
            ems_chain.add_monitored_quantity(idf, ems_chain.SOURCE_ACTUATOR, src['ems_actuator'], name)
            src = {'key': ems_chain.EMS_KEY, 'variable': name}
        _ensure_timestep_output(idf, src['key'], src['variable'])
        keep.add((_norm(src['key']), _norm(src['variable'])))
        p['query'] = {'key': src['key'], 'variable': src['variable']}

    for cls in [c for c in idf.idfobjects.keys() if c.upper().startswith('EXTERNALINTERFACE')]:
        for obj in list(idf.idfobjects[cls]):
            idf.removeidfobject(obj)

    if prune:
        # Only our variables: the model's own hourly/daily '*' requests would fill the database
        # with thousands of series nobody asked for.
        for obj in list(idf.idfobjects['Output:Variable']):
            if (_norm(obj.Key_Value), _norm(obj.Variable_Name)) not in keep \
                    or _norm(obj.Reporting_Frequency) != 'TIMESTEP':
                idf.removeidfobject(obj)

    runs = idf.idfobjects['RunPeriod']
    for extra in list(runs)[1:]:
        idf.removeidfobject(extra)
    run = runs[0] if runs else idf.newidfobject('RunPeriod')
    run.Begin_Month, run.Begin_Day_of_Month = run_period.day_date(period['startDay'])
    run.End_Month, run.End_Day_of_Month = run_period.day_date(period['endDay'] - 1)
    run.Begin_Year = ''
    run.End_Year = ''
    steps = idf.idfobjects['Timestep']
    (steps[0] if steps else idf.newidfobject('Timestep')).Number_of_Timesteps_per_Hour = period['timestep']
    for sim in idf.idfobjects['SimulationControl']:
        sim.Run_Simulation_for_Weather_File_Run_Periods = 'Yes'
    for sql in list(idf.idfobjects['Output:SQLite']):
        idf.removeidfobject(sql)
    idf.newidfobject('Output:SQLite', Option_Type='Simple')
    idf.saveas(target_idf)
    return plan


# ------------------------------------------------------------------- the results
def _site_year(field_dir):
    try:
        with open(os.path.join(field_dir, 'points.yaml'), encoding='utf-8') as handle:
            match = re.search(r'^site:.*\byear:\s*(\d{4})', handle.read(), re.MULTILINE)
        if match:
            return int(match.group(1))
    except OSError:
        pass
    return datetime.date.today().year


def stamp_year(field_dir, upload_folder='uploads', epw=None):
    """(year, where it comes from): the dates stored in InfluxDB carry the year of the weather file when it is one
    real year (an Open-Meteo year, a station year), else site.year of Field/points.yaml (a typical year has no single year).
    `epw` is the file the run used; without it, the file of the session."""
    import weather_info
    info = weather_info.describe(epw) if epw else weather_info.info(upload_folder)
    if info.get('kind') == 'real' and info.get('years'):
        return info['years'][0], 'weather'
    return _site_year(field_dir), 'site'


def read_series(sql_path, plan):
    """({point id: [(Month, Day, Hour, Minute, value)]} for the points the run produced,
    the ids it did not (the model reports no such variable), {point id: unit EnergyPlus reports})."""
    con = sqlite3.connect('file:{}?mode=ro'.format(sql_path.replace('\\', '/')), uri=True)
    try:
        dictionary, sql_units = {}, {}
        for idx, key, name, units in con.execute(
                "select ReportDataDictionaryIndex, KeyValue, Name, Units from ReportDataDictionary "
                "where ReportingFrequency = 'Zone Timestep' order by ReportDataDictionaryIndex"):
            dictionary.setdefault((_norm(key), _norm(name)), idx)
            sql_units.setdefault(idx, units or '')
        series, missing, units = {}, [], {}
        for p in plan:
            q = p.get('query')
            idx = dictionary.get((_norm(q['key']), _norm(q['variable']))) if q else None
            if idx is None:
                if q:
                    missing.append(p['id'])
                continue
            units[p['id']] = {'C': 'degC'}.get(sql_units[idx], sql_units[idx])
            series[p['id']] = con.execute(
                "select t.Month, t.Day, t.Hour, t.Minute, r.Value from ReportData r "
                "join Time t on t.TimeIndex = r.TimeIndex "
                "where r.ReportDataDictionaryIndex = ? and t.WarmupFlag = 0 and t.EnvironmentPeriodIndex in "
                "(select EnvironmentPeriodIndex from EnvironmentPeriods where EnvironmentType = 3) "
                "order by r.TimeIndex", (idx,)).fetchall()
        return series, missing, units
    finally:
        con.close()


def timestamp(year, month, day, hour, minute):
    """Epoch seconds of the end of an interval; EnergyPlus labels the last one 24:00."""
    when = datetime.datetime(year, month, day) + datetime.timedelta(hours=hour, minutes=minute)
    return int(when.replace(tzinfo=datetime.timezone.utc).timestamp())


def _influx_client():
    from urllib.parse import urlparse
    from influxdb import InfluxDBClient
    url = urlparse(os.environ.get('INFLUX_URL', 'http://influxdb:8086'))
    return InfluxDBClient(host=url.hostname or 'influxdb', port=url.port or 8086,
                          username=os.environ.get('INFLUX_USERNAME') or None,
                          password=os.environ.get('INFLUX_PASSWORD') or None, timeout=60)


def write_influx(series, plan, year, progress=None, keep=False):
    """Write `series` to DIRECT_DATABASE, replacing what it held, or beside it when `keep`. Returns the rows written.

    With `keep`, a run of another year adds to the database (the dates differ), so a dataset of several years is built
    by running one year after the other; a run of the same year writes over its own points.
    """
    meta = {p['id']: p for p in plan}
    client = _influx_client()
    if not keep:
        client.drop_database(DIRECT_DATABASE)
    client.create_database(DIRECT_DATABASE)
    written, batch = 0, []
    for pid, rows in series.items():
        p = meta[pid]
        tags = {'run': RUN_TAG, 'point': pid, 'type': p['type']}
        if p.get('unit') and p['unit'] != '-':
            tags['unit'] = p['unit']
        if p['type'] == 'measurement' and p.get('role'):
            tags['role'] = p['role']
        for month, day, hour, minute, value in rows:
            if value is None or value != value:
                continue
            try:
                when = timestamp(year, month, day, hour, minute)
            except ValueError:
                raise ValueError('The weather file has {:02d}/{:02d}, which does not exist in {}: '
                                 'set site.year in Field/points.yaml to a leap year.'.format(month, day, year))
            batch.append({'measurement': MEASUREMENT, 'tags': tags, 'time': when, 'fields': {'value': float(value)}})
            if len(batch) >= BATCH:
                client.write_points(batch, time_precision='s', database=DIRECT_DATABASE)
                written += len(batch)
                batch = []
                if progress:
                    progress(written)
    if batch:
        client.write_points(batch, time_precision='s', database=DIRECT_DATABASE)
        written += len(batch)
        if progress:
            progress(written)
    return written


# ---------------------------------------------------------------------- the run
def _err_summary(err_path):
    """(severe count, first severe/fatal lines) from eplusout.err."""
    lines = []
    severe = 0
    try:
        with open(err_path, encoding='latin-1') as handle:
            for line in handle:
                if '** Severe' in line or '**  Fatal' in line or '** Fatal' in line:
                    severe += 1
                    if len(lines) < 4:
                        lines.append(line.strip())
                elif lines and len(lines) < 4 and line.strip().startswith('**   ~~~   **') and severe:
                    lines[-1] += ' ' + line.strip().replace('**   ~~~   **', '').strip()
    except OSError:
        pass
    return severe, lines


def _stop_energyplus():
    proc = _proc
    if proc and proc.poll() is None:
        proc.terminate()
    try:
        from methods import ENERGYPLUS_CONTAINER
        subprocess.run(['docker', 'exec', '-u', 'root', ENERGYPLUS_CONTAINER, 'pkill', '-f',
                        '/workspace/simulation_outputs/direct/'], timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _worker(period, field_dir, prune, keep=False, epw_path=None, final=True):
    global _proc
    try:
        import idf_session
        from methods import ENERGYPLUS_CONTAINER
        working = idf_session.working_path()
        epw = epw_path or (sorted(glob.glob(os.path.join('uploads', '*.epw'))) or [None])[0]
        used_epw = epw
        if epw and not os.path.abspath(epw).startswith(os.path.abspath('uploads') + os.sep):
            # The EnergyPlus container sees uploads/ and simulation_outputs/ only: a file of the library is lent to it there,
            # for this run, and the weather of the session stays what it was.
            lent = os.path.join('simulation_outputs', 'direct_weather')
            shutil.rmtree(lent, ignore_errors=True)
            os.makedirs(lent, exist_ok=True)
            shutil.copyfile(epw, os.path.join(lent, os.path.basename(epw)))
            epw = os.path.join(lent, os.path.basename(epw))
        if not working or not epw:
            raise ValueError('Upload an IDF and an EPW file first.')
        idf_session.save()
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        os.makedirs(WORK_DIR, exist_ok=True)
        model_name = os.path.splitext(os.path.basename(working))[0]
        target = os.path.join(WORK_DIR, 'model.idf')

        _set(state='building', message='Preparing the model: no FMU, native logic, the FMU points as outputs…')
        plan = build_run_idf(working, target, period, model_name, prune=prune)
        observable = [p for p in plan if p.get('query')]
        _set(points=[{'id': p['id'], 'type': p['type'], 'unit': p.get('unit') or '', 'fmu': p['fmu']}
                     for p in observable],
             not_observable=[{'id': p['id'], 'fmu': p['fmu'], 'reason': p.get('reason', '')}
                             for p in plan if not p.get('query')])
        if not observable:
            raise ValueError('None of the FMU points can be read from EnergyPlus alone.')
        if _stop.is_set():
            raise InterruptedError

        first, last = period['startDay'], period['endDay']
        _set(state='running', progress=0, message='EnergyPlus is simulating {} to {}…'.format(
            run_period.day_label(first), run_period.day_label(last - 1)))
        cmd = ['docker', 'exec', '-u', 'root', ENERGYPLUS_CONTAINER, ENERGYPLUS_BIN,
               '-d', '/workspace/simulation_outputs/direct',
               '-w', '/workspace/{}'.format(epw.replace(os.sep, '/')),
               '/workspace/simulation_outputs/direct/model.idf']
        _proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 encoding='utf-8', errors='replace', bufsize=1)
        date_re = re.compile(r'(?:Starting|Continuing) Simulation at (\d\d)/(\d\d)/(\d{4})')
        for line in _proc.stdout:
            m = date_re.search(line)
            if m:
                month, day = int(m.group(1)), int(m.group(2))
                doy = (datetime.date(run_period._NON_LEAP_YEAR, month, day) -
                       datetime.date(run_period._NON_LEAP_YEAR, 1, 1)).days
                _set(sim_date='{} {}'.format(day, datetime.date(2021, month, 1).strftime('%b')),
                     progress=max(0, min(99, int(100 * (doy - first) / max(1, last - first)))))
        code = _proc.wait()
        if _stop.is_set():
            raise InterruptedError
        severe, lines = _err_summary(os.path.join(WORK_DIR, 'eplusout.err'))
        _set(severe=severe)
        if code != 0 or not os.path.exists(os.path.join(WORK_DIR, 'eplusout.sql')):
            raise RuntimeError('EnergyPlus failed ({}): {}'.format(code, ' | '.join(lines) or 'see eplusout.err'))

        _set(state='writing', progress=100, message='Reading the EnergyPlus results…')
        series, missing, sql_units = read_series(os.path.join(WORK_DIR, 'eplusout.sql'), observable)
        for p in observable:
            # The export deduces units from the model and leaves some empty: EnergyPlus knows them all.
            if p['id'] in sql_units and (not p.get('unit') or p['unit'] == '-'):
                p['unit'] = sql_units[p['id']]
        _set(points=[{'id': p['id'], 'type': p['type'], 'unit': p.get('unit') or '', 'fmu': p['fmu']}
                     for p in observable if p['id'] in series])
        if not series:
            raise RuntimeError('EnergyPlus reported none of the requested variables. {}'.format(' | '.join(lines)))
        expected = (period['endDay'] - period['startDay']) * 24 * period['timestep']
        short = {pid: len(r) for pid, r in series.items() if len(r) != expected}
        if short:
            raise RuntimeError('EnergyPlus stopped early: expected {} steps, got {} for {}. {}'.format(
                expected, next(iter(short.values())), next(iter(short)), ' | '.join(lines)))
        total = sum(len(r) for r in series.values())
        _set(rows_total=total, rows=0, message='Writing {:,} rows to InfluxDB ({})…'.format(total, DIRECT_DATABASE))
        year, _from = stamp_year(field_dir, epw=used_epw)
        _set(year=year, year_from=_from)
        written = write_influx(series, observable, year, progress=lambda n: _set(rows=n), keep=keep)
        note = '' if not missing else ' Not reported by the model: {}.'.format(', '.join(missing))
        warn = '' if not severe else ' EnergyPlus logged {} severe message(s): {}'.format(severe, ' | '.join(lines))
        summary = '{:,} rows ({} points × {} steps) written to {}, dated {}.{}{}'.format(
            written, len(series), expected, DIRECT_DATABASE, year, note, warn)
        if final:
            _set(state='done', rows=written, finished=time.time(), message=summary)
        else:   # a year of a queue: the next one follows, the run is not over
            _set(state='building', rows=written, message=summary + ' Next year…')
        return True
    except InterruptedError:
        _set(state='stopped', finished=time.time(), message='Stopped.')
    except Exception as exc:  # shown in the Control room
        _set(state='error', finished=time.time(), message=str(exc))
    finally:
        _proc = None
    return False


def _queue(period, field_dir, prune, keep, files):
    """Several weather files one after the other: the first replaces what is stored unless `keep`, the others add to it."""
    for i, (path, name, year) in enumerate(files):
        last = i == len(files) - 1
        _set(step=i + 1, of=len(files), weather=name, message='Weather {} of {}: {}…'.format(i + 1, len(files), name))
        if not _worker(period, field_dir, prune, keep or i > 0, epw_path=path, final=last):
            return      # the worker has said why: error or stopped


def start(period, field_dir, prune=True, keep=False, files=None):
    """Start a run in the background. ValueError: bad period; RuntimeError: one is already running.

    `files` is a list of (path, name, year) of weather files, run one after the other; without it, the weather of the session.
    """
    global _thread
    period = run_period.validate(period)
    with _lock:
        if is_active():
            raise RuntimeError('A direct run is already in progress.')
        _stop.clear()
        _set(state='building', message='Starting…', progress=0, sim_date=None, period=period, points=[],
             not_observable=[], rows=0, rows_total=0, severe=0, started=time.time(), finished=None,
             step=1, of=len(files) if files else 1, weather=None, year=None, year_from=None)
        if files:
            _thread = threading.Thread(target=_queue, args=(period, field_dir, prune, keep, files), daemon=True)
        else:
            _thread = threading.Thread(target=_worker, args=(period, field_dir, prune, keep), daemon=True)
        _thread.start()


def stop():
    _stop.set()
    _stop_energyplus()
