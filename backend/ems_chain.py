"""Build and tear down the EMS chain that exposes a quantity to the FMU.

Every observable quantity reaches the co-simulation the same way, because
ExternalInterface:...From:Variable cannot reference a meter or an actuator
directly -- only an Output:Variable:

    source (RDD variable | MDD meter | EMS actuator)
      -> EnergyManagementSystem:Sensor          (skipped for actuators)
      -> EnergyManagementSystem:OutputVariable
      -> Output:Variable, EMS, <name>
      -> ExternalInterface:...From:Variable, key "EMS"

Defaults for Type of Data / Update Frequency follow the reference lab models:
meters are Summed/SystemTimestep, everything else Averaged/ZoneTimestep.
"""

import re

SOURCE_VARIABLE = 'variable'
SOURCE_METER = 'meter'
SOURCE_ACTUATOR = 'actuator'

EMS_KEY = 'EMS'
DEFAULT_REPORTING_FREQUENCY = 'Timestep'


def sanitize_name(raw):
    """Reduce a free-form label to something safe as an Erl / FMU identifier."""
    cleaned = re.sub(r'[^0-9a-zA-Z_]', '_', (raw or '').strip())
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    if not cleaned:
        raise ValueError('Name is empty after sanitization.')
    if cleaned[0].isdigit():
        cleaned = 'v_' + cleaned
    return cleaned


def meter_index_key(meter_name):
    """Index key for a meter sensor.

    The reference models read DistrictHeating:Facility with the index key
    "Facility", i.e. the scope suffix of the meter name. Meters without a scope
    suffix are read with a blank key.
    """
    return meter_name.rsplit(':', 1)[1] if ':' in meter_name else ''


def _first(objects, predicate):
    return next((o for o in objects if predicate(o)), None)


def _ensure_output_variable(idf, key_value, variable_name):
    existing = _first(
        idf.idfobjects['Output:Variable'],
        lambda o: o.Key_Value == key_value and o.Variable_Name == variable_name
    )
    if existing:
        return existing
    obj = idf.newidfobject('Output:Variable')
    obj.Key_Value = key_value
    obj.Variable_Name = variable_name
    obj.Reporting_Frequency = DEFAULT_REPORTING_FREQUENCY
    return obj


def _ensure_output_meter(idf, meter_name):
    existing = _first(idf.idfobjects['Output:Meter'], lambda o: o.Key_Name == meter_name)
    if existing:
        return existing
    obj = idf.newidfobject('Output:Meter')
    obj.Key_Name = meter_name
    obj.Reporting_Frequency = DEFAULT_REPORTING_FREQUENCY
    return obj


def add_monitored_quantity(idf, source_type, source_name, name,
                           index_key='', fmu_variable_name=None):
    """Wire one quantity all the way through to an FMU output.

    source_name is the RDD variable name, the MDD meter name, or the name of an
    existing EnergyManagementSystem:Actuator.
    """
    name = sanitize_name(name)
    fmu_variable_name = sanitize_name(fmu_variable_name or name)

    if source_type == SOURCE_METER:
        _ensure_output_meter(idf, source_name)
        sensor_key = index_key or meter_index_key(source_name)
        ems_variable = name
        type_of_data, update_frequency = 'Summed', 'SystemTimestep'
    elif source_type == SOURCE_VARIABLE:
        _ensure_output_variable(idf, index_key, source_name)
        sensor_key = index_key
        ems_variable = name
        type_of_data, update_frequency = 'Averaged', 'ZoneTimestep'
    elif source_type == SOURCE_ACTUATOR:
        # An actuator is already an Erl variable, so it needs no sensor.
        sensor_key = None
        ems_variable = source_name
        type_of_data, update_frequency = 'Averaged', 'ZoneTimestep'
    else:
        raise ValueError('Unknown source type: {}'.format(source_type))

    if sensor_key is not None:
        if not _first(idf.idfobjects['EnergyManagementSystem:Sensor'], lambda o: o.Name == name):
            sensor = idf.newidfobject('EnergyManagementSystem:Sensor')
            sensor.Name = name
            sensor.OutputVariable_or_OutputMeter_Index_Key_Name = sensor_key
            sensor.OutputVariable_or_OutputMeter_Name = source_name

    if not _first(idf.idfobjects['EnergyManagementSystem:OutputVariable'], lambda o: o.Name == name):
        ems_output = idf.newidfobject('EnergyManagementSystem:OutputVariable')
        ems_output.Name = name
        ems_output.EMS_Variable_Name = ems_variable
        ems_output.Type_of_Data_in_Variable = type_of_data
        ems_output.Update_Frequency = update_frequency

    _ensure_output_variable(idf, EMS_KEY, name)

    if not _first(
        idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable'],
        lambda o: o.FMU_Variable_Name == fmu_variable_name
    ):
        export = idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:From:Variable')
        export.OutputVariable_Index_Key_Name = EMS_KEY
        export.OutputVariable_Name = name
        export.FMU_Variable_Name = fmu_variable_name

    return {'name': name, 'fmuVariableName': fmu_variable_name}


def remove_monitored_quantity(idf, name):
    """Remove the whole chain built for `name`, leaving the source object alone."""
    name = sanitize_name(name)

    for export in list(idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable']):
        if export.OutputVariable_Index_Key_Name == EMS_KEY and export.OutputVariable_Name == name:
            idf.removeidfobject(export)

    for variable in list(idf.idfobjects['Output:Variable']):
        if variable.Key_Value == EMS_KEY and variable.Variable_Name == name:
            idf.removeidfobject(variable)

    for ems_output in list(idf.idfobjects['EnergyManagementSystem:OutputVariable']):
        if ems_output.Name == name:
            idf.removeidfobject(ems_output)

    for sensor in list(idf.idfobjects['EnergyManagementSystem:Sensor']):
        if sensor.Name == name:
            idf.removeidfobject(sensor)


ACTUATOR_SUFFIX = '_act'
FMU_INPUT_SUFFIX = '_FMU'
APPLY_PROGRAM_PREFIX = 'SBEP_Apply_'


def _apply_program_name(name):
    return '{}{}'.format(APPLY_PROGRAM_PREFIX, name)


def add_controlled_actuator(idf, name, component_name, component_type, control_type,
                            fmu_variable_name=None, initial_value=0, monitor_status=True):
    """Let the FMU drive one actuator, following the reference control model.

    The obvious route -- ExternalInterface:...To:Actuator -- does NOT work here.
    EnergyPlus turns that object's name into an Erl variable, so declaring both it
    and an EnergyManagementSystem:Actuator for the same component collides:

        ** Severe ** Invalid Name=SHADE_CMD
           ~~~ Object name conflicts with a global variable name in EMS

    lab_building_external_control.idf instead keeps the two apart and joins them
    with a one-line program, which is what this reproduces:

        To:Variable  <name>          the FMU writes this Erl variable
        EMS:Actuator <name>_act      the handle on the component
        EMS:Program  SET <name>_act = <name>

    The FMU-facing name carries a suffix for the same reason the reference model
    writes `Bath1_shade` / `Bath1_shade_FMU`: To:Variable's Name becomes an Erl
    global, and reusing it as the FMU Variable Name is rejected outright:

        ** Severe ** Invalid FMU Variable Name=Shade_cmd
           ~~~ Name conflicts with an existing global variable name
    """
    name = sanitize_name(name)
    fmu_variable_name = sanitize_name(
        fmu_variable_name or '{}{}'.format(name, FMU_INPUT_SUFFIX))
    actuator_name = '{}{}'.format(name, ACTUATOR_SUFFIX)
    if fmu_variable_name == name:
        raise ValueError(
            'The FMU variable name must differ from the Erl variable name "{}".'.format(name))

    if not _first(idf.idfobjects['EnergyManagementSystem:Actuator'],
                  lambda o: o.Name == actuator_name):
        actuator = idf.newidfobject('EnergyManagementSystem:Actuator')
        actuator.Name = actuator_name
        actuator.Actuated_Component_Unique_Name = component_name
        actuator.Actuated_Component_Type = component_type
        actuator.Actuated_Component_Control_Type = control_type

    if not _first(
        idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Variable'],
        lambda o: o.Name == name
    ):
        export = idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:To:Variable')
        export.Name = name
        export.FMU_Variable_Name = fmu_variable_name
        export.Initial_Value = initial_value

    program_name = _apply_program_name(name)
    if not _first(idf.idfobjects['EnergyManagementSystem:Program'],
                  lambda o: o.Name == program_name):
        program = idf.newidfobject('EnergyManagementSystem:Program')
        program.Name = program_name
        program.Program_Line_1 = 'SET {} = {}'.format(actuator_name, name)

    status = None
    if monitor_status:
        # Report what was actually applied to the component, not the raw input.
        status = add_monitored_quantity(
            idf,
            source_type=SOURCE_ACTUATOR,
            source_name=actuator_name,
            name='{}_status'.format(name)
        )

    return {
        'name': name,
        'actuatorName': actuator_name,
        'programName': program_name,
        'fmuVariableName': fmu_variable_name,
        'status': status,
    }


def controlled_actuator_programs(idf):
    """Names of the apply-programs, so the calling manager can invoke them."""
    return [o.Name for o in idf.idfobjects['EnergyManagementSystem:Program']
            if o.Name.startswith(APPLY_PROGRAM_PREFIX)]


def remove_controlled_actuator(idf, name):
    name = sanitize_name(name)
    actuator_name = '{}{}'.format(name, ACTUATOR_SUFFIX)
    program_name = _apply_program_name(name)

    remove_monitored_quantity(idf, '{}_status'.format(name))

    for program in list(idf.idfobjects['EnergyManagementSystem:Program']):
        if program.Name == program_name:
            idf.removeidfobject(program)

    for export in list(idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Variable']):
        if export.Name == name:
            idf.removeidfobject(export)

    for actuator in list(idf.idfobjects['EnergyManagementSystem:Actuator']):
        if actuator.Name == actuator_name:
            idf.removeidfobject(actuator)


# --------------------------------------------------------------------------- #
# Direct mode: the FMU writes the component or the schedule itself.
#
# ExternalInterface:FunctionalMockupUnitExport:To:Actuator and :To:Schedule need
# no EMS program and no calling manager. Measured on EnergyPlus 9.6 with an FMU
# and a pyfmi master (model with zero EMS objects): the value the master sets
# before a step shows up in that same step, for the zone heating setpoint and
# for a schedule. The moment is chosen by EnergyPlus, not by us.
#
#   * the Initial Value stands in for the master in sizing and warm-up, but not
#     equally for every kind (lab model, dual-setpoint zone, FMU + pyfmi):
#       - To:Schedule honours it (cooling schedule 26: clean warm-up, 26 at step 0);
#       - To:Actuator and To:Variable do not: the first warm-up step ran with 0
#         (cooling setpoint 0 against heating 20: "Effective heating set-point
#         higher than effective cooling set-point", fatal), also when the master
#         set the input before initialize. This holds for the program route
#         add_controlled_actuator too. So thermostats are driven through their
#         schedule, not through the setpoint actuator;
#     with a To:Schedule the value must still be sensible: a heating setpoint
#     above the cooling one ended the sizing of a small model with a fatal error;
#   * run on its own, without a master, a To:Schedule stays at its Initial Value
#     and a To:Actuator is not applied at all.
# --------------------------------------------------------------------------- #

TO_ACTUATOR = 'ExternalInterface:FunctionalMockupUnitExport:To:Actuator'
TO_SCHEDULE = 'ExternalInterface:FunctionalMockupUnitExport:To:Schedule'
TO_VARIABLE = 'ExternalInterface:FunctionalMockupUnitExport:To:Variable'
FROM_VARIABLE = 'ExternalInterface:FunctionalMockupUnitExport:From:Variable'

# Top-level schedules: the kinds a To:Schedule can stand in for (its Name joins the
# ScheduleNames list; Day and Week schedules are referenced from other lists).
REPLACEABLE_SCHEDULES = ('Schedule:Constant', 'Schedule:Compact', 'Schedule:Year', 'Schedule:File')


def _fmu_names_taken(idf):
    taken = set()
    for cls in (TO_ACTUATOR, TO_SCHEDULE, TO_VARIABLE, FROM_VARIABLE):
        taken.update(str(o.FMU_Variable_Name).upper() for o in idf.idfobjects[cls])
    return taken


def _erl_names_taken(idf):
    names = set()
    for cls in ('EnergyManagementSystem:Actuator', 'EnergyManagementSystem:Sensor',
                TO_ACTUATOR, TO_VARIABLE):
        names.update(str(o.Name).upper() for o in idf.idfobjects[cls])
    for o in idf.idfobjects['EnergyManagementSystem:GlobalVariable']:
        names.update(str(v).upper() for v in o.obj[1:] if v)
    return names


def add_direct_actuator(idf, name, component_name, component_type, control_type,
                        fmu_variable_name=None, initial_value=0):
    """Let the FMU write one actuator directly (no EMS program, no calling manager)."""
    name = sanitize_name(name)
    fmu_variable_name = sanitize_name(fmu_variable_name or '{}{}'.format(name, FMU_INPUT_SUFFIX))
    if fmu_variable_name.upper() == name.upper():
        raise ValueError(
            'The FMU variable name must differ from the Erl variable name "{}".'.format(name))

    for existing in idf.idfobjects[TO_ACTUATOR]:
        if existing.Name == name:
            return {'name': name, 'fmuVariableName': existing.FMU_Variable_Name, 'mode': 'direct'}
        if (existing.Actuated_Component_Unique_Name.upper(), existing.Actuated_Component_Type.upper(),
                existing.Actuated_Component_Control_Type.upper()) == (
                component_name.upper(), component_type.upper(), control_type.upper()):
            raise ValueError('"{}" already writes this component; remove it first.'.format(existing.Name))
    if name.upper() in _erl_names_taken(idf):
        raise ValueError('The name "{}" is already used by another EMS object.'.format(name))
    if fmu_variable_name.upper() in _fmu_names_taken(idf):
        raise ValueError('The FMU variable name "{}" is already in use.'.format(fmu_variable_name))

    obj = idf.newidfobject(TO_ACTUATOR)
    obj.Name = name
    obj.Actuated_Component_Unique_Name = component_name
    obj.Actuated_Component_Type = component_type
    obj.Actuated_Component_Control_Type = control_type
    obj.FMU_Variable_Name = fmu_variable_name
    obj.Initial_Value = float(initial_value)
    return {'name': name, 'fmuVariableName': fmu_variable_name, 'mode': 'direct'}


def add_direct_variable(idf, key_value, variable_name, fmu_variable_name):
    """Export a report variable to the FMU as it is: Output:Variable + From:Variable.

    No sensor, no EMS output variable, no program: nothing of the EMS is needed
    to read a report variable (verified with an FMU on a model with no EMS
    objects). Meters cannot be read this way; they go through the EMS chain.
    """
    fmu_variable_name = sanitize_name(fmu_variable_name)
    for existing in idf.idfobjects[FROM_VARIABLE]:
        if existing.FMU_Variable_Name.upper() == fmu_variable_name.upper():
            if (existing.OutputVariable_Index_Key_Name, existing.OutputVariable_Name) == (key_value, variable_name):
                return {'fmuVariableName': fmu_variable_name, 'mode': 'direct'}
            raise ValueError('The FMU variable name "{}" is already in use.'.format(fmu_variable_name))
    if fmu_variable_name.upper() in _fmu_names_taken(idf):
        raise ValueError('The FMU variable name "{}" is already in use.'.format(fmu_variable_name))
    _ensure_output_variable(idf, key_value, variable_name)
    export = idf.newidfobject(FROM_VARIABLE)
    export.OutputVariable_Index_Key_Name = key_value
    export.OutputVariable_Name = variable_name
    export.FMU_Variable_Name = fmu_variable_name
    return {'fmuVariableName': fmu_variable_name, 'mode': 'direct'}


def remove_direct_variable(idf, fmu_variable_name):
    """Drop the export. The Output:Variable stays: the model may report it for itself."""
    for export in list(idf.idfobjects[FROM_VARIABLE]):
        if export.FMU_Variable_Name == fmu_variable_name and export.OutputVariable_Index_Key_Name != EMS_KEY:
            idf.removeidfobject(export)


def remove_direct_actuator(idf, name):
    for obj in list(idf.idfobjects[TO_ACTUATOR]):
        if obj.Name == name:
            idf.removeidfobject(obj)


def find_schedule(idf, name):
    for cls in REPLACEABLE_SCHEDULES:
        for obj in idf.idfobjects[cls]:
            if str(obj.Name).strip().upper() == name.strip().upper():
                return obj
    return None


def suggest_initial_value(idf, name):
    """A value that makes sense in sizing and warm-up: what the schedule says at
    noon of the first day type that has one. Heating and cooling setpoint
    schedules are read at the same instant, so the pair stays consistent."""
    import schedule_model
    shape = schedule_model.read(idf, name)
    if not shape or not shape.get('periods'):
        return None
    start = shape['periods'][0]['start']
    for day_type in schedule_model.DAY_TYPES:
        value = schedule_model.value_at(shape, start[0], start[1], day_type, 720)
        if value is not None:
            return value
    return None


def add_direct_schedule(idf, schedule_name, fmu_variable_name=None, initial_value=None):
    """Replace a top-level schedule by a To:Schedule of the same name.

    The To:Schedule *is* the schedule (its name must be unique among schedules),
    so the original definition goes. It can be restored from the pristine upload.
    """
    schedule = find_schedule(idf, schedule_name)
    if schedule is None:
        raise ValueError('"{}" is not a Schedule:Constant, Compact, Year or File in this model.'.format(
            schedule_name))
    name = str(schedule.Name).strip()
    # An EMS actuator on the schedule would lose its target: it is a Schedule:*
    # component, and the To:Schedule that replaces it is not.
    for actuator in idf.idfobjects['EnergyManagementSystem:Actuator']:
        if (str(actuator.Actuated_Component_Unique_Name).strip().upper() == name.upper()
                and str(actuator.Actuated_Component_Type).upper().startswith('SCHEDULE')):
            raise ValueError(
                'The EMS actuator "{}" overrides this schedule; remove it first, or keep the schedule '
                'and drive it through an actuator.'.format(actuator.Name))
    fmu_variable_name = sanitize_name(fmu_variable_name or '{}{}'.format(name, FMU_INPUT_SUFFIX))
    if fmu_variable_name.upper() in _fmu_names_taken(idf):
        raise ValueError('The FMU variable name "{}" is already in use.'.format(fmu_variable_name))
    if initial_value in (None, ''):
        initial_value = suggest_initial_value(idf, name)
    if initial_value is None:
        raise ValueError('Give an initial value: it is used in sizing and warm-up.')

    limits = getattr(schedule, 'Schedule_Type_Limits_Name', '') or ''
    idf.removeidfobject(schedule)
    obj = idf.newidfobject(TO_SCHEDULE)
    obj.Schedule_Name = name
    obj.Schedule_Type_Limits_Names = limits
    obj.FMU_Variable_Name = fmu_variable_name
    obj.Initial_Value = float(initial_value)
    return {'name': name, 'fmuVariableName': fmu_variable_name,
            'initialValue': float(initial_value), 'mode': 'direct'}


def remove_direct_schedule(idf, schedule_name, original_idf_path=None):
    """Take the To:Schedule out and put the original schedule back, if the
    pristine upload still has it."""
    removed = False
    for obj in list(idf.idfobjects[TO_SCHEDULE]):
        if str(obj.Schedule_Name).strip().upper() == schedule_name.strip().upper():
            idf.removeidfobject(obj)
            removed = True
    if not removed or not original_idf_path or find_schedule(idf, schedule_name) is not None:
        return {'restored': False}
    from eppy.modeleditor import IDF
    source = find_schedule(IDF(original_idf_path), schedule_name)
    if source is None:
        return {'restored': False}
    copy = idf.newidfobject(source.key)
    # Field by field would pad an extensible object (Schedule:Compact) with
    # thousands of empty fields; copy the raw values instead.
    copy.obj[1:] = list(source.obj[1:])
    return {'restored': True}
