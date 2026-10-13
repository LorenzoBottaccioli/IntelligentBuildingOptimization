"""EMS programs: programs, the calling managers that run them, and the variables they use.

A program is Erl code; a calling manager says at which point of the EnergyPlus
timestep it runs and in which order. They are edited together and kept
consistent: a program a manager calls cannot be removed without leaving that
manager, and a manager is never left with nothing to run.

What is whose is read from the model itself: whatever the uploaded file already
had is the model's, whatever was added since is the student's. The platform's own
objects (SBEP_Apply_* programs, the keepalive and its manager) are read-only: other
code maintains them.

Sources: EMS Application Guide pp. 8-14 (statements, variables), pp. 52-59 (calling
points); Input Output Reference pp. 2223-2230 (calling points, object fields).
"""

import re

import ems_chain

PROGRAM = 'EnergyManagementSystem:Program'
MANAGER = 'EnergyManagementSystem:ProgramCallingManager'
SUBROUTINE = 'EnergyManagementSystem:Subroutine'
SENSOR = 'EnergyManagementSystem:Sensor'
ACTUATOR = 'EnergyManagementSystem:Actuator'
GLOBAL = 'EnergyManagementSystem:GlobalVariable'
TREND = 'EnergyManagementSystem:TrendVariable'

RUN_PREFIX = 'SBEP_Run_'
KEEPALIVE_PROGRAM = 'donothing'
KEEPALIVE_MANAGER = 'SBEP EMS Runtime'

MAX_LINE = 100  # an Erl line is cut at 100 characters (guide p.10)
KEYWORDS = ('RUN', 'RETURN', 'SET', 'IF', 'ELSEIF', 'ELSE', 'ENDIF', 'WHILE', 'ENDWHILE')

# Built-in variables, guide pp.12-13, plus the actuator release value.
BUILT_INS = (
    'Year', 'Month', 'DayOfMonth', 'DayOfWeek', 'DayOfYear', 'Holiday', 'DaylightSavings',
    'CurrentTime', 'Hour', 'Minute', 'TimeStepsPerHour', 'TimeStepNum', 'True', 'False', 'On',
    'Off', 'PI', 'SunIsUp', 'IsRaining', 'ZoneTimeStep', 'SystemTimeStep', 'CurrentEnvironment',
    'Null', 'ActualDateAndTime', 'ActualTime', 'WarmupFlag',
)

# The 15 calling points of the IOR (pp.2223-2225). `control` marks the ones a
# controller can act from; the rest are for set-up, reporting and sizing.
CALLING_POINTS = [
    ('BeginNewEnvironment', False, 'Once per environment period. Initialise variables here; not for control.'),
    ('BeginZoneTimestepBeforeSetCurrentWeather', True, 'Start of the step, before the weather is set. The only point where Weather Data actuators work.'),
    ('AfterNewEnvironmentWarmUpIsComplete', False, 'Once, after warm-up. Reset counters here; not for control.'),
    ('BeginZoneTimestepBeforeInitHeatBalance', True, 'Before solar shading and daylighting are computed: shades, constructions, shading surfaces.'),
    ('BeginZoneTimestepAfterInitHeatBalance', True, 'After solar shading and daylighting, before the surface heat balance: shades, constructions, weather.'),
    ('BeginTimestepBeforePredictor', True, 'Before the zone loads are predicted: setpoints, schedules, lights and equipment, people. Measured: a zone heating setpoint written here acts in the same step.'),
    ('AfterPredictorBeforeHVACManagers', True, 'After the load prediction, before SetpointManagers and AvailabilityManagers: those can overwrite what you set here.'),
    ('AfterPredictorAfterHVACManagers', True, 'After the managers: your values win over them. Measured: a zone setpoint written here acts one step late, because the predictor has already used it.'),
    ('InsideHVACSystemIterationLoop', True, 'Every HVAC iteration: plant and system overrides. Most accurate, slowest.'),
    ('EndOfZoneTimestepBeforeZoneReporting', False, 'End of the zone step, before reporting: custom output variables at zone frequency.'),
    ('EndOfZoneTimestepAfterZoneReporting', True, 'End of the zone step, after reporting: decide the next step from the final values of this one.'),
    ('EndOfSystemTimestepBeforeHVACReporting', False, 'End of the system step, before reporting: custom output variables at system frequency.'),
    ('EndOfSystemTimestepAfterHVACReporting', True, 'End of the system step, after reporting.'),
    ('EndOfZoneSizing', False, 'Once, after zone sizing: change the sizing results.'),
    ('EndOfSystemSizing', False, 'Once, after system sizing: change the sizing results.'),
]
DEFAULT_CALLING_POINT = 'BeginTimestepBeforePredictor'

_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


# ---------------------------------------------------------------- reading ---

def _lines(obj, start):
    return [str(v) for v in obj.obj[start:] if v not in (None, '')]


_ORIGINAL = {'key': None, 'names': None}

WSC = 'WindowShadingControl'


def original_names(original_path):
    """What the uploaded file already had, parsed once per file.

    Programs and managers (with their definitions, so a manager that was switched
    off can be put back), the shading type of each WindowShadingControl, and
    whether the file had an EMS at all.
    """
    empty = {'programs': set(), 'managers': {}, 'wsc': {}, 'hasEms': False}
    if not original_path:
        return empty
    import os
    key = (original_path, os.path.getmtime(original_path))
    if _ORIGINAL['key'] != key:
        from eppy.modeleditor import IDF
        old = IDF(original_path)
        _ORIGINAL['names'] = {
            'programs': {o.Name for cls in (PROGRAM, SUBROUTINE) for o in old.idfobjects[cls]},
            'managers': {o.Name: {'callingPoint': o.EnergyPlus_Model_Calling_Point, 'programs': _lines(o, 3)}
                         for o in old.idfobjects[MANAGER]},
            'wsc': {str(o.Name).upper(): str(o.Shading_Control_Type) for o in old.idfobjects[WSC]},
            'hasEms': any(old.idfobjects[c] for c in (PROGRAM, SUBROUTINE, SENSOR, ACTUATOR, MANAGER)),
        }
        _ORIGINAL['key'] = key
    return _ORIGINAL['names']


def _is_platform_program(idf, name):
    if name.startswith(ems_chain.APPLY_PROGRAM_PREFIX):
        return True
    if name == KEEPALIVE_PROGRAM:
        ours = 'SET{}=0'.format('SBEP_Keepalive'.upper())
        return any(o.Name == name and o.Program_Line_1.replace(' ', '').upper() == ours
                   for o in idf.idfobjects[PROGRAM])
    return False


def _origin(idf, kind, name, original):
    if kind == 'manager':
        if name == KEEPALIVE_MANAGER:
            return 'platform'
        return 'model' if name in original['managers'] else 'student'
    if _is_platform_program(idf, name):
        return 'platform'
    return 'model' if name in original['programs'] else 'student'


def _called_at(idf):
    """program name (upper) -> [(manager, calling point)]."""
    out = {}
    for manager in idf.idfobjects[MANAGER]:
        for name in _lines(manager, 3):
            out.setdefault(name.upper(), []).append((manager.Name, manager.EnergyPlus_Model_Calling_Point))
    return out


def list_programs(idf, original):
    called = _called_at(idf)
    programs = []
    for cls, kind in ((PROGRAM, 'program'), (SUBROUTINE, 'subroutine')):
        for obj in idf.idfobjects[cls]:
            name = str(obj.Name)
            runs = called.get(name.upper(), [])
            origin = _origin(idf, 'program', name, original)
            programs.append({
                'name': name,
                'kind': kind,
                'origin': origin,
                'editable': origin != 'platform',
                'lines': _lines(obj, 2),
                'callingPoint': runs[0][1] if runs else None,
                'managers': [m for m, _ in runs],
            })
    return programs


def list_managers(idf, original):
    names = {o.Name.upper() for o in idf.idfobjects[PROGRAM]}
    out = []
    for obj in idf.idfobjects[MANAGER]:
        origin = _origin(idf, 'manager', obj.Name, original)
        programs = _lines(obj, 3)
        out.append({
            'name': obj.Name,
            'origin': origin,
            'editable': origin != 'platform',
            'callingPoint': obj.EnergyPlus_Model_Calling_Point,
            'programs': programs,
            'missing': [p for p in programs if p.upper() not in names],
        })
    return out


def list_variables(idf):
    """Everything a program can name, by kind. Names are what goes into the Erl code."""
    return {
        'builtIns': list(BUILT_INS),
        'sensors': [{'name': o.Name,
                     'source': '{} @ {}'.format(o.OutputVariable_or_OutputMeter_Name,
                                                o.OutputVariable_or_OutputMeter_Index_Key_Name or 'meter')}
                    for o in idf.idfobjects[SENSOR]],
        'actuators': [{'name': o.Name,
                       'source': '{} of {}'.format(o.Actuated_Component_Control_Type,
                                                   o.Actuated_Component_Unique_Name)}
                      for o in idf.idfobjects[ACTUATOR]],
        'fmuInputs': [{'name': o.Name, 'source': 'FMU input {} (initial {})'.format(
            o.FMU_Variable_Name, o.Initial_Value)} for o in idf.idfobjects[ems_chain.TO_VARIABLE]],
        'globals': [{'name': v, 'source': 'global'}
                    for o in idf.idfobjects[GLOBAL] for v in _lines(o, 1)
                    if v != 'SBEP_Keepalive'],      # the platform's own, not for programs
        'trends': [{'name': o.Name, 'source': 'trend of {} over {} steps'.format(
            o.EMS_Variable_Name, o.Number_of_Timesteps_to_be_Logged)} for o in idf.idfobjects[TREND]],
    }


# ------------------------------------------------------------- validation ---

def _strip(line):
    return line.split('!', 1)[0].strip().rstrip(',;').strip()


def validate(lines, known=()):
    """(errors, warnings) for a program. Errors block saving; warnings do not.

    Mirrors the rules of guide pp.8-14: one statement per line starting with a
    keyword, IF nested up to 5 deep, WHILE not nested, lines up to 100 characters.
    A variable the program reads but nobody declared or SET is only a warning:
    EnergyPlus stops on it (guide p.11) but the check here is by name.
    """
    errors, warnings = [], []
    depth = 0
    in_while = False
    assigned = set()
    used = []
    known = {k.upper() for k in known} | {b.upper() for b in BUILT_INS}
    for number, raw in enumerate(lines, start=1):
        if len(raw) > MAX_LINE:
            errors.append('Line {}: {} characters; EnergyPlus cuts a line at {}.'.format(number, len(raw), MAX_LINE))
        text = _strip(raw)
        if not text:
            continue
        keyword = text.split(None, 1)[0].upper().rstrip(',')
        if keyword not in KEYWORDS:
            errors.append('Line {}: must start with one of {}.'.format(number, ', '.join(KEYWORDS)))
            continue
        rest = text[len(keyword):].strip()
        if keyword == 'IF':
            depth += 1
            if depth > 5:
                errors.append('Line {}: IF blocks nest at most 5 deep.'.format(number))
        elif keyword == 'ENDIF':
            depth -= 1
            if depth < 0:
                errors.append('Line {}: ENDIF without IF.'.format(number))
                depth = 0
        elif keyword in ('ELSEIF', 'ELSE') and depth == 0:
            errors.append('Line {}: {} outside an IF block.'.format(number, keyword))
        elif keyword == 'WHILE':
            if in_while:
                errors.append('Line {}: WHILE blocks cannot be nested.'.format(number))
            in_while = True
        elif keyword == 'ENDWHILE':
            if not in_while:
                errors.append('Line {}: ENDWHILE without WHILE.'.format(number))
            in_while = False
        if keyword == 'SET':
            target, _, expression = rest.partition('=')
            target = target.strip()
            if not _IDENT.match(target):
                errors.append('Line {}: "{}" is not a valid variable name.'.format(number, target))
                continue
            used.extend((number, t) for t in _identifiers(expression))
            assigned.add(target.upper())
        elif keyword in ('IF', 'ELSEIF', 'WHILE'):
            used.extend((number, t) for t in _identifiers(rest))
    if depth > 0:
        errors.append('{} IF block(s) never closed with ENDIF.'.format(depth))
    if in_while:
        errors.append('A WHILE block is never closed with ENDWHILE.')
    seen = set()
    for number, token in used:
        up = token.upper()
        if up not in known and up not in assigned and up not in seen:
            seen.add(up)
            warnings.append('Line {}: "{}" is not declared anywhere; EnergyPlus stops on a variable it has never seen.'.format(number, token))
    return errors, warnings


def _clean(line):
    """A line as the IDF stores it: no trailing separator, no trailing blanks."""
    return str(line).rstrip().rstrip(',;').rstrip()


def check(idf, lines):
    """validate() with the variables the model declares as known names."""
    variables = list_variables(idf)
    known = [v['name'] for kind in ('sensors', 'actuators', 'fmuInputs', 'globals', 'trends')
             for v in variables[kind]]
    return validate([_clean(ln) for ln in lines if str(ln).strip()], known)


def _identifiers(expression):
    expression = re.sub(r'@\w+', ' ', expression)           # built-in function names
    expression = re.sub(r'\b\d+(\.\d*)?([eE][-+]?\d+)?\b', ' ', expression)  # numbers
    return re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expression)


# ----------------------------------------------------------------- writing ---

def _manager_name(program_name):
    return '{}{}'.format(RUN_PREFIX, program_name)


def _all_names(idf):
    return {o.Name.upper() for cls in (PROGRAM, SUBROUTINE) for o in idf.idfobjects[cls]}


def _valid_point(calling_point):
    if calling_point not in [c[0] for c in CALLING_POINTS]:
        raise ValueError('Unknown calling point "{}".'.format(calling_point))


def _manager(idf, name):
    return next((o for o in idf.idfobjects[MANAGER] if o.Name == name), None)


def save_program(idf, original, name, lines, kind='program', manager=None, calling_point=None):
    """Create a program or subroutine, or rewrite one.

    For a new program, `manager` adds it to an existing calling manager and
    `calling_point` gives it a manager of its own; with neither it is saved
    uncalled and the warning says so. A program that already exists keeps the
    managers that call it: those are edited under Calling managers.
    """
    name = ems_chain.sanitize_name(name)
    if kind not in ('program', 'subroutine'):
        raise ValueError('Unknown kind "{}".'.format(kind))
    # The IDF supplies the separators: a comma the student typed would become an
    # empty field after the line.
    lines = [_clean(ln) for ln in lines if str(ln).strip()]
    if not lines:
        raise ValueError('A program needs at least one line.')
    errors, warnings = check(idf, lines)
    if errors:
        raise ValueError(' '.join(errors))

    cls = PROGRAM if kind == 'program' else SUBROUTINE
    existing = next((o for o in idf.idfobjects[cls] if o.Name == name), None)
    if existing is not None:
        if _origin(idf, 'program', name, original) == 'platform':
            raise ValueError('"{}" belongs to the platform: it cannot be edited.'.format(name))
        existing.obj[2:] = lines
        sync_shading(idf, original)
        return {'name': name, 'created': False, 'warnings': warnings}

    if name.upper() in _all_names(idf) or name.startswith(ems_chain.APPLY_PROGRAM_PREFIX) \
            or name.upper() == KEEPALIVE_PROGRAM.upper():
        raise ValueError('A program or subroutine called "{}" already exists or is reserved.'.format(name))
    obj = idf.newidfobject(cls)
    obj.Name = name
    obj.obj[2:] = lines            # raw values: field by field would pad the extensible object

    if kind == 'program':
        if manager:
            target = _manager(idf, manager)
            if target is None or _origin(idf, 'manager', manager, original) == 'platform':
                raise ValueError('"{}" is not a calling manager you can add to.'.format(manager))
            target.obj[3:] = _lines(target, 3) + [name]
        elif calling_point:
            _valid_point(calling_point)
            own = idf.newidfobject(MANAGER)
            own.Name = _unique_manager_name(idf, _manager_name(name))
            own.EnergyPlus_Model_Calling_Point = calling_point
            own.obj[3:] = [name]
        else:
            warnings.append('No calling manager runs this program yet: add it to one under Calling managers.')
    sync_shading(idf, original)
    return {'name': name, 'created': True, 'warnings': warnings}


def _unique_manager_name(idf, base):
    taken = {o.Name.upper() for o in idf.idfobjects[MANAGER]}
    name, n = base, 2
    while name.upper() in taken:
        name, n = '{}_{}'.format(base, n), n + 1
    return name


def remove_program(idf, original, name):
    """Remove a program or subroutine, and take it out of every manager that calls it.

    A manager left with nothing to run is removed too: EnergyPlus requires one.
    Programs that RUN a removed subroutine are left alone; the check on them will say so.
    """
    if _origin(idf, 'program', name, original) == 'platform':
        raise ValueError('"{}" belongs to the platform: it cannot be removed.'.format(name))
    dropped = []
    for obj in list(idf.idfobjects[MANAGER]):
        called = _lines(obj, 3)
        if name in called:
            rest = [p for p in called if p != name]
            if rest:
                obj.obj[3:] = rest
            else:
                dropped.append(obj.Name)
                idf.removeidfobject(obj)
    for cls in (PROGRAM, SUBROUTINE):
        for obj in list(idf.idfobjects[cls]):
            if obj.Name == name:
                idf.removeidfobject(obj)
    sync_shading(idf, original)
    return {'removedManagers': dropped}


def save_manager(idf, original, name, calling_point, programs, rename_from=None):
    """Create a calling manager, or rewrite one: calling point and ordered programs."""
    # A manager's name is an ordinary IDF object name, not an Erl identifier: spaces are fine.
    name = (name or '').strip()
    if not name or re.search(r'[,;!]', name):
        raise ValueError('Give the calling manager a name without commas, semicolons or "!".')
    _valid_point(calling_point)
    programs = [p for p in programs if p]
    if not programs:
        raise ValueError('A calling manager needs at least one program to run.')
    available = {o.Name for o in idf.idfobjects[PROGRAM]}
    for p in programs:
        if p not in available:
            raise ValueError('"{}" is not a program in this model.'.format(p))
        if _is_platform_program(idf, p):
            raise ValueError('"{}" is run by the platform: leave it out.'.format(p))
    if name.upper() == KEEPALIVE_MANAGER.upper() or _origin(idf, 'manager', name, original) == 'platform':
        raise ValueError('"{}" belongs to the platform.'.format(name))
    target = _manager(idf, name)
    created = target is None
    if created:
        target = idf.newidfobject(MANAGER)
        target.Name = name
    target.EnergyPlus_Model_Calling_Point = calling_point
    target.obj[3:] = programs
    sync_shading(idf, original)
    return {'name': name, 'created': created}


def remove_manager(idf, original, name):
    if _origin(idf, 'manager', name, original) == 'platform':
        raise ValueError('"{}" belongs to the platform: it cannot be removed.'.format(name))
    removed = False
    for obj in list(idf.idfobjects[MANAGER]):
        if obj.Name == name:
            idf.removeidfobject(obj)
            removed = True
    if not removed:
        raise ValueError('There is no calling manager called "{}".'.format(name))
    sync_shading(idf, original)


# ----------------------------------------------- the do-nothing EMS, the model's EMS ---

def _other_ems_objects(idf):
    """Any EMS object that is not the platform's keepalive."""
    others = [o for cls in (SENSOR, ACTUATOR, TREND, SUBROUTINE, 'EnergyManagementSystem:OutputVariable')
              for o in idf.idfobjects[cls]]
    others += [o for o in idf.idfobjects[PROGRAM] if not _is_platform_program(idf, o.Name)]
    others += [o for o in idf.idfobjects[GLOBAL] if 'SBEP_Keepalive' not in _lines(o, 1)]
    return others


def runtime_reason(idf):
    """Why the platform's do-nothing EMS (program + manager) is needed, or None.

    EnergyPlus runs the EMS only when a program is called. An EMS output variable
    stays silent without one, and so would a model whose EMS objects have nothing
    calling them. A model without any EMS, read through plain report variables or
    written directly, needs none: nothing is added.
    """
    if idf.idfobjects['EnergyManagementSystem:OutputVariable']:
        return 'outputs'
    if ems_chain.controlled_actuator_programs(idf):
        return 'inputs'
    if _other_ems_objects(idf) and not [m for m in idf.idfobjects[MANAGER] if m.Name != KEEPALIVE_MANAGER]:
        return 'idle'
    return None


def runtime_info(idf):
    return {
        'present': any(m.Name == KEEPALIVE_MANAGER for m in idf.idfobjects[MANAGER]),
        'reason': runtime_reason(idf),
        'program': KEEPALIVE_PROGRAM,
        'manager': KEEPALIVE_MANAGER,
    }


def _active_actuators(idf):
    """Upper-case names of the actuator variables a *called* program sets."""
    import schedule_model
    called, programs = schedule_model._called_programs(idf)
    out = set()
    for name in called:
        for line in programs.get(name, []):
            m = re.match(r'\s*set\s+([^\s=]+)\s*=', line, re.I)   # an actuator name may hold ':'
            if m:
                out.add(m.group(1).upper())
    return out


def sync_shading(idf, original):
    """Keep the shading controls consistent with who drives them.

    EnergyPlus 9.6 mishandles a blind that an EMS deploys while its
    WindowShadingControl says off (methods.fix_ems_blind_override). So a control
    whose windows are all driven by an actuator that a called program sets runs
    AlwaysOn; when that EMS is switched off the control goes back to the type the
    uploaded file gave it. Controls with any window outside the EMS are left alone.
    """
    active = _active_actuators(idf)
    driven = {str(a.Actuated_Component_Unique_Name).upper() for a in idf.idfobjects[ACTUATOR]
              if str(a.Actuated_Component_Type).strip().lower() == 'window shading control'
              and str(a.Actuated_Component_Control_Type).strip().lower() == 'control status'
              and a.Name.upper() in active}
    changed = []
    for control in idf.idfobjects[WSC]:
        windows = [getattr(control, f) for f in control.fieldnames
                   if f.startswith('Fenestration_Surface_') and getattr(control, f, '')]
        current = str(control.Shading_Control_Type or '')
        if windows and all(w.upper() in driven for w in windows):
            if current.lower() != 'alwayson':
                control.Shading_Control_Type = 'AlwaysOn'
                changed.append(control.Name)
        elif current.lower() == 'alwayson':
            was = original['wsc'].get(str(control.Name).upper())
            if was and was.lower() != 'alwayson':
                control.Shading_Control_Type = was
                changed.append(control.Name)
    return changed


def switch_model_manager(idf, original, name, enabled):
    """Switch one of the model's calling managers off or on.

    Off removes it from the working model: nothing it calls runs. Its programs
    stay. On puts it back as the uploaded file defined it.
    """
    definition = original['managers'].get(name)
    if definition is None:
        raise ValueError('"{}" is not a calling manager of the uploaded model.'.format(name))
    present = _manager(idf, name)
    if not enabled:
        if present is not None:
            idf.removeidfobject(present)
        return
    if present is not None:
        return
    available = {o.Name for o in idf.idfobjects[PROGRAM]}
    programs = [p for p in definition['programs'] if p in available]
    if not programs:
        raise ValueError('"{}" cannot be switched on: the programs it called are gone.'.format(name))
    obj = idf.newidfobject(MANAGER)
    obj.Name = name
    obj.EnergyPlus_Model_Calling_Point = definition['callingPoint']
    obj.obj[3:] = programs


def set_model_ems(idf, original, enabled, name=None):
    """All of the model's EMS on or off, or one manager. Returns what changed."""
    names = [name] if name else list(original['managers'])
    for n in names:
        switch_model_manager(idf, original, n, enabled)
    return {'shading': sync_shading(idf, original)}


def model_ems_state(idf, original):
    """The model's own EMS: what it is, whether it is running, what is switched off."""
    managers = original['managers']
    running = [n for n in managers if _manager(idf, n) is not None]
    return {
        'present': original['hasEms'],
        'managers': len(managers),
        'running': len(running),
        'enabled': bool(managers) and len(running) == len(managers),
        'off': [{'name': n, 'callingPoint': d['callingPoint'], 'programs': d['programs']}
                for n, d in managers.items() if n not in running],
        'actuators': len(idf.idfobjects[ACTUATOR]),
    }


# --------------------------------------------------------------- variables ---

def _check_free(idf, name):
    if name.upper() in ems_chain._erl_names_taken(idf) or name.upper() in {
            n.upper() for n in BUILT_INS} or name.upper() in {
            t.Name.upper() for t in idf.idfobjects[TREND]}:
        raise ValueError('The name "{}" is already used by another EMS variable.'.format(name))


def add_variable(idf, kind, name, **opt):
    """Declare one variable a program can use. `kind`: sensor, actuator, fmuInput, global, trend."""
    name = ems_chain.sanitize_name(name)
    _check_free(idf, name)
    if kind == 'sensor':
        obj = idf.newidfobject(SENSOR)
        obj.Name = name
        obj.OutputVariable_or_OutputMeter_Index_Key_Name = opt.get('key', '')
        obj.OutputVariable_or_OutputMeter_Name = opt['variableName']
    elif kind == 'actuator':
        obj = idf.newidfobject(ACTUATOR)
        obj.Name = name
        obj.Actuated_Component_Unique_Name = opt['component']
        obj.Actuated_Component_Type = opt['componentType']
        obj.Actuated_Component_Control_Type = opt['controlType']
    elif kind == 'fmuInput':
        fmu = ems_chain.sanitize_name(opt.get('fmuVariableName') or name + ems_chain.FMU_INPUT_SUFFIX)
        if fmu.upper() == name.upper():
            raise ValueError('The FMU variable name must differ from the Erl variable name.')
        if fmu.upper() in ems_chain._fmu_names_taken(idf):
            raise ValueError('The FMU variable name "{}" is already in use.'.format(fmu))
        obj = idf.newidfobject(ems_chain.TO_VARIABLE)
        obj.Name = name
        obj.FMU_Variable_Name = fmu
        obj.Initial_Value = float(opt.get('initialValue', 0))
    elif kind == 'global':
        obj = idf.newidfobject(GLOBAL)
        obj.Erl_Variable_1_Name = name
    elif kind == 'trend':
        obj = idf.newidfobject(TREND)
        obj.Name = name
        obj.EMS_Variable_Name = opt['variable']
        obj.Number_of_Timesteps_to_be_Logged = int(opt.get('steps', 12))
    else:
        raise ValueError('Unknown kind "{}".'.format(kind))
    result = {'name': name, 'kind': kind}
    if kind == 'fmuInput':
        # The caller sets the input's range on this name.
        result['fmuVariableName'] = str(obj.FMU_Variable_Name)
    return result


def remove_variable(idf, kind, name):
    cls = {'sensor': SENSOR, 'actuator': ACTUATOR, 'fmuInput': ems_chain.TO_VARIABLE, 'trend': TREND}.get(kind)
    if kind == 'global':
        for obj in list(idf.idfobjects[GLOBAL]):
            if name in _lines(obj, 1):
                idf.removeidfobject(obj)
        return
    if cls is None:
        raise ValueError('Unknown kind "{}".'.format(kind))
    if kind == 'fmuInput' and any(p.Name == ems_chain._apply_program_name(name)
                                  for p in idf.idfobjects[PROGRAM]):
        raise ValueError('"{}" is a platform input; remove it from the Actuators tab.'.format(name))
    if kind == 'actuator' and name.endswith(ems_chain.ACTUATOR_SUFFIX):
        raise ValueError('"{}" belongs to a platform input; remove that input instead.'.format(name))
    for obj in list(idf.idfobjects[cls]):
        if obj.Name == name:
            idf.removeidfobject(obj)
