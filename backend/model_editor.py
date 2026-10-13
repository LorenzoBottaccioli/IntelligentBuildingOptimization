from flask import Blueprint, request, session, jsonify, current_app
from flask_cors import CORS
from methods import *
import os
from config import db
import ems_chain
import ems_programs
import fmu_roles
import idf_session
import idf_version
import idf_reader
import shutil
import glob
from werkzeug.utils import secure_filename
from eppy.modeleditor import IDF
from models import *
import re
from influxdb import InfluxDBClient as InfluxDBClientV1
from datetime import datetime
from traceback import format_exc
from nbformat import read, write

import inject_data
from engine import surrogate_engine


UPLOAD_FOLDER='uploads'
SIMULATION_OUTPUTS='simulation_outputs'
IDD_PATH = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')

model_editor_bp = Blueprint('model_editor', __name__)
CORS(model_editor_bp)

# Routes written before idf_session existed: each parses uploads/ afresh and saves
# it, so the live model idf_session holds is stale afterwards, and the next edit
# made through the session (the Model editor's, an EMS page's) would write the
# stale copy back over theirs. The disk is current when they return, so dropping
# the cached model makes the next read re-parse it.
_DISK_EDIT_ROUTES = {
    'add_output_variable', 'add_ems_sensor', 'add_ems_actuator', 'add_fmu_actuator',
    'add_fmu_from_variable', 'add_fmu_to_variable', 'add_fmu_schedule',
    'add_ems_program_calling_manager', 'add_ems_program',
    'remove_output_variables', 'remove_ems_sensors', 'remove_ems_actuators',
    'remove_ems_program_calling_managers', 'remove_ems_programs', 'remove_fmu_actuators',
    'remove_fmu_from_variables', 'remove_fmu_to_variables', 'remove_fmu_schedules',
}


@model_editor_bp.after_request
def _resync_after_disk_edit(response):
    endpoint = (request.endpoint or '').rsplit('.', 1)[-1]
    if endpoint in _DISK_EDIT_ROUTES and response.status_code < 400:
        idf_session.invalidate()
    return response

_PROBE_CACHE = {}


def _probe_catalogue(pattern, parse):
    """A catalogue parsed from the probe simulation, cached until the file changes."""
    files = glob.glob(os.path.join(SIMULATION_OUTPUTS, pattern))
    if not files or not idf_session.has_model():
        return []
    key = (files[0], os.path.getmtime(files[0]))
    if _PROBE_CACHE.get(pattern, (None,))[0] != key:
        try:
            _PROBE_CACHE[pattern] = (key, parse(files[0]))
        except (IndexError, OSError):
            _PROBE_CACHE[pattern] = (key, [])
    return _PROBE_CACHE[pattern][1]


_KEYS_CACHE = {'key': None, 'value': {}, 'tried': None}


def _variable_keys():
    """{variable: {units, keys}} from the key probe, built once if missing.

    Models uploaded before the probe existed get it on first request, from the
    probe copy already in simulation_outputs, without a new upload.
    """
    import json
    if not idf_session.has_model():
        return {}
    if not os.path.exists(VARIABLE_KEYS_FILE):
        probe = sorted(glob.glob(os.path.join(SIMULATION_OUTPUTS, 'ems_*.idf')))
        epws = sorted(glob.glob(os.path.join(UPLOAD_FOLDER, '*.epw')))
        attempt = (probe[0] if probe else None, idf_session.generation())
        if probe and epws and _KEYS_CACHE['tried'] != attempt:
            _KEYS_CACHE['tried'] = attempt
            probe_variable_keys(probe[0], epws[0])
        if not os.path.exists(VARIABLE_KEYS_FILE):
            return {}
    key = os.path.getmtime(VARIABLE_KEYS_FILE)
    if _KEYS_CACHE['key'] != key:
        with open(VARIABLE_KEYS_FILE, encoding='utf-8') as handle:
            _KEYS_CACHE['value'] = json.load(handle)
        _KEYS_CACHE['key'] = key
    return _KEYS_CACHE['value']


_FMU_CLASSES = {
    'from': 'ExternalInterface:FunctionalMockupUnitExport:From:Variable',
    'actuator': 'ExternalInterface:FunctionalMockupUnitExport:To:Actuator',
    'variable': 'ExternalInterface:FunctionalMockupUnitExport:To:Variable',
    'schedule': 'ExternalInterface:FunctionalMockupUnitExport:To:Schedule',
}


def _fmu_names(idf, kind, match):
    """FMU variable names of the `kind` objects for which match(obj) holds.

    Read before the object is removed: afterwards the name is gone with it.
    """
    return [str(o.FMU_Variable_Name) for o in idf.idfobjects[_FMU_CLASSES[kind]] if match(o)]


def _drop_roles(names):
    for name in names:
        fmu_roles.drop(name)


def _current_fmu_names(idf):
    names = set()
    for cls in _FMU_CLASSES.values():
        names.update(str(o.FMU_Variable_Name) for o in idf.idfobjects[cls])
    return names


@model_editor_bp.route('/get_objects', methods=['GET'])
def get_objects():
    """Current model state, read from the live IDF.

    Only the probe-simulation catalogues (.edd actuators, .rdd variables,
    .mdd meters) come from elsewhere: they describe what EnergyPlus *could*
    report for this model, not what the model currently contains.
    """
    # Read from the probe simulation's .edd and .rdd, like the meters below,
    # not from the SQL tables filled at upload: the database lives inside the
    # container, so every rebuild emptied it and the Model Editor reported a
    # model with 0 actuators until the next upload.
    keys = _variable_keys()
    payload = {
        'edd_actuators': [
            {'id': i, 'componentUniqueName': a['Component_Unique_Name'],
             'componentType': a['Component_Type'], 'controlType': a['Control_Type'],
             'units': a.get('Units', '')}
            for i, a in enumerate(_probe_catalogue('*.edd', parse_edd_file), 1)],
        'rdd_variables': [
            {'id': i, 'varType': v['Var_Type'], 'variableName': v['Variable_Name'],
             'units': keys.get(v['Variable_Name'], {}).get('units'),
             'keys': keys.get(v['Variable_Name'], {}).get('keys')}
            for i, v in enumerate(_probe_catalogue('*.rdd', parse_rdd_file), 1)],
        'variableKeysKnown': bool(keys),
    }

    # Meters live in the .mdd, which every probe simulation regenerates.
    mdd_files = glob.glob(os.path.join(SIMULATION_OUTPUTS, '*.mdd'))
    payload['mdd_meters'] = [
        {'varType': m['Var_Type'], 'meterName': m['Meter_Name'], 'units': m.get('Units')}
        for m in (parse_mdd_file(mdd_files[0]) if mdd_files else [])
    ]

    if idf_session.has_model():
        idf = idf_session.get()
        payload.update(idf_reader.snapshot(idf))
        # An entry whose variable is no longer in the model is stale (an edit
        # that bypassed the remove routes, e.g. of the file itself).
        live = _current_fmu_names(idf)
        payload['fmu_roles'] = {name: entry for name, entry in fmu_roles.load().items()
                                if name in live}
        # The export writes its timestep into the model, so it starts from the
        # model's own instead of overwriting it with a default.
        # A blank field or a missing object means the IDD default, 6.
        ts = idf.idfobjects['TIMESTEP']
        raw = str(ts[0].Number_of_Timesteps_per_Hour).strip() if ts else ''
        payload['timesteps_per_hour'] = int(float(raw)) if raw else 6
    else:
        payload.update(idf_reader.empty_snapshot())
        payload['fmu_roles'] = {}
        payload['timesteps_per_hour'] = None

    return jsonify(payload), 200


@model_editor_bp.route('/set_fmu_role', methods=['POST'])
def set_fmu_role():
    """Record what an FMU variable is for: a role for an output, limits for an action."""
    data = request.get_json(silent=True) or {}
    name = data.get('fmuVariableName')
    if not name or not isinstance(name, str):
        return jsonify({'error': 'fmuVariableName is required.'}), 400
    role = data.get('role')
    low = data.get('min')
    high = data.get('max')
    if role is not None and role not in ('observation', 'reward'):
        return jsonify({'error': 'role must be "observation" or "reward".'}), 400
    if low is not None or high is not None:
        def is_number(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if not (is_number(low) and is_number(high)):
            return jsonify({'error': 'min and max must both be numbers.'}), 400
        if low > high:
            return jsonify({'error': 'min must not exceed max.'}), 400
    if role is None and low is None and high is None:
        return jsonify({'error': 'Give a role, or min and max.'}), 400
    if not idf_session.has_model():
        return jsonify({'error': 'No IDF has been uploaded yet.'}), 400
    return jsonify({'fmu_roles': fmu_roles.set_entry(name, role=role, min=low, max=high)}), 200

@model_editor_bp.route('/loaded_files', methods=['GET'])
def loaded_files():
    """The model and weather file the session holds, read from uploads/.

    The frontend asks this on start instead of trusting what the browser
    remembers: a first start shows no model, and a model stays loaded until
    Reset Session empties uploads/.
    """
    idf = idf_session.working_path()
    epws = sorted(glob.glob(os.path.join(idf_session.UPLOAD_FOLDER, '*.epw')))
    return jsonify({'idf': os.path.basename(idf) if idf else '',
                    'epw': os.path.basename(epws[0]) if idf and epws else ''}), 200

def populate_tables(original_idf_filepath):
    """Fill the SQL tables the edit routes read from the working IDF in uploads/.

    Shared by upload_files and by opening a saved session, which restores the
    files but not the database (it lives inside the container).
    """
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])

    zones=get_zone_names(idf_path[0])

    idf_runperiods = idf.idfobjects['Runperiod']
    idf_runperiod = idf_runperiods[0]

    new_current_runperiod = current_runperiod(
        Begin_Month=idf_runperiod.Begin_Month,
        Begin_Day_of_Month=idf_runperiod.Begin_Day_of_Month
    )
    db.session.add(new_current_runperiod)
    db.session.commit()
    
    idf_ems_sensors = idf.idfobjects['EnergyManagementSystem:Sensor']

    if idf_ems_sensors:
        for sensor in idf_ems_sensors:
            new_current_ems_sensor = current_ems_sensor(
                Name=sensor.Name,
                OutputVariable_or_OutputMeter_Index_Key_Name=sensor.OutputVariable_or_OutputMeter_Index_Key_Name,
                OutputVariable_or_OutputMeter_Name=sensor.OutputVariable_or_OutputMeter_Name
            )
            db.session.add(new_current_ems_sensor)
            db.session.commit()
    
    idf_ems_actuators = idf.idfobjects['EnergyManagementSystem:Actuator']

    if idf_ems_actuators:
        for actuator in idf_ems_actuators:
            new_current_ems_actuator = current_ems_actuator(
                Name=actuator.Name,
                Actuated_Component_Unique_Name=actuator.Actuated_Component_Unique_Name,
                Actuated_Component_Type=actuator.Actuated_Component_Type,
                Actuated_Component_Control_Type=actuator.Actuated_Component_Control_Type
            )
            db.session.add(new_current_ems_actuator)
            db.session.commit()

    idf_ems_programs = get_ems_programs(original_idf_filepath)

    if idf_ems_programs:
        for program in idf_ems_programs:
            new_ems_program = CurrentEMSProgram(name=program['Name'])

            # Add each program line to the program
            for line_text in program['ProgramLines']:
                new_ems_program.program_lines.append(ProgramLine(line_text=line_text))

            db.session.add(new_ems_program)
            db.session.commit()

    idf_ems_program_calling_managers = get_ems_program_calling_managers(original_idf_filepath)

    if idf_ems_program_calling_managers:
        for manager in idf_ems_program_calling_managers:
            new_manager = CurrentEMSProgramCallingManager(
                name=manager['Name'],
                energy_plus_model_calling_point=manager['EnergyPlus Model Calling Point']
            )

            # Add each program name to the calling manager
            for program_name in manager['Program Names']:
                new_manager.program_names.append(ProgramName(line_text=program_name))

            db.session.add(new_manager)
            db.session.commit()

    idf_fmu_actuators = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Actuator']

    if idf_fmu_actuators:
        for actuator in idf_fmu_actuators:
            new_current_fmu_actuator = current_fmu_actuator(
                Name=actuator.Name,
                Actuated_Component_Unique_Name=actuator.Actuated_Component_Unique_Name,
                Actuated_Component_Type=actuator.Actuated_Component_Type,
                Actuated_Component_Control_Type=actuator.Actuated_Component_Control_Type,
                FMU_Variable_Name=actuator.FMU_Variable_Name,
                Initial_Value=actuator.Initial_Value
            )
            db.session.add(new_current_fmu_actuator)
            db.session.commit()

    idf_fmu_from_variables = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable']

    if idf_fmu_from_variables:
        for variable in idf_fmu_from_variables:
            new_current_fmu_from_variable = current_fmu_from_variable(
                OutputVariable_Index_Key_Name=variable.OutputVariable_Index_Key_Name,
                OutputVariable_Name=variable.OutputVariable_Name,
                FMU_Variable_Name=variable.FMU_Variable_Name
            )
            db.session.add(new_current_fmu_from_variable)
            db.session.commit()

    idf_fmu_to_variables = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Variable']
    if idf_fmu_to_variables:
        for variable in idf_fmu_to_variables:
            new_current_fmu_to_variable = current_fmu_to_variable(
                Name=variable.Name,
                FMU_Variable_Name=variable.FMU_Variable_Name,
                Initial_Value=variable.Initial_Value
            )
            db.session.add(new_current_fmu_to_variable)
            db.session.commit()

    idf_fmu_schedules = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Schedule']

    if idf_fmu_schedules:
        for schedule in idf_fmu_schedules:
            new_current_fmu_schedule = current_fmu_schedule(
                Schedule_Name=schedule.Schedule_Name,
                Schedule_Type_Limits_Names=schedule.Schedule_Type_Limits_Names,
                FMU_Variable_Name=schedule.FMU_Variable_Name,
                Initial_Value=schedule.Initial_Value
            )
            db.session.add(new_current_fmu_schedule)
            db.session.commit()

    idf_schedule_type_limits = get_schedule_limits(original_idf_filepath)

    if idf_schedule_type_limits:
        for limit in idf_schedule_type_limits:
            new_existing_schedule_type_limit = existing_shedule_type_limit(
                Name=limit['Name'],
                Lower_Limit_Value=limit['Lower_Limit_Value'],
                Upper_Limit_Value=limit['Upper_Limit_Value']
            )
            db.session.add(new_existing_schedule_type_limit)
            db.session.commit()

    idf_schedule_names = get_schedule_names(original_idf_filepath)

    if idf_schedule_names:
        for name in idf_schedule_names:
            new_existing_schedule_name = existing_schedule_name(
                Schedule_Name=name
            )
            db.session.add(new_existing_schedule_name)
            db.session.commit()

    idf_output_variables = idf.idfobjects['Output:Variable']

    if idf_output_variables:
        for variable in idf_output_variables:
            new_current_output_variable = current_output_variable(
                Key_Value=variable.Key_Value,
                Variable_Name=variable.Variable_Name,
                Reporting_Frequency=variable.Reporting_Frequency,
                Schedule_Name=variable.Schedule_Name
            )
            db.session.add(new_current_output_variable)
            db.session.commit()
        
    session["progress"] = 100
    session.modified = True

    materials = parse_materials(idf)
    for m in materials:
        db.session.add(m)

    constructions = parse_constructions(idf)
    for c in constructions:
        db.session.add(c)

    fenestrations = parse_fenestration_surfaces(idf)
    for f in fenestrations:
        db.session.add(f)

    ventilations = parse_zone_ventilation(idf)
    for v in ventilations:
        db.session.add(v)

    lights = parse_lights(idf)
    for l in lights:
        db.session.add(l)

    shadings = parse_window_shading(idf)
    for s in shadings:
        db.session.add(s)

    db.session.commit()


@model_editor_bp.route('/upload_files', methods=['POST'])
def upload_files():
    try:
        idf_file = request.files.get('idf_file')
        epw_file = request.files.get('epw_file')

        if not idf_file:
            return jsonify({'error': 'No IDF file provided.'}), 400
        if not epw_file:
            return jsonify({'error': 'No EPW file provided.'}), 400
        
        if not idf_allowed_file(idf_file.filename):
            return jsonify({'error': 'Invalid IDF file type.'}), 400
        if not epw_allowed_file(epw_file.filename):
            return jsonify({'error': 'Invalid EPW file type.'}), 400
        
        original_idf_filename = secure_filename(idf_file.filename)
        epw_filename = secure_filename(epw_file.filename)

        original_idf_filepath = os.path.join(UPLOAD_FOLDER, original_idf_filename)
        epw_filepath = os.path.join(UPLOAD_FOLDER, epw_filename)

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        idf_file.save(original_idf_filepath)
        epw_file.save(epw_filepath)
        # A new model has a new FMU interface: the old roles do not carry over.
        fmu_roles.clear()

        # Before anything reads this file: an IDF written for an older EnergyPlus
        # is not rejected by eppy, it is parsed against the IDD we happen to have
        # and every field after one that a later version added is read one place
        # out. Nothing raises. The exercise models were 9.4 read as 9.6, and the
        # only symptom was that no surface seemed to face outdoors.
        version_check = idf_version.check(original_idf_filepath)

        copy_idf_filepath = os.path.join(SIMULATION_OUTPUTS, f"ems_{original_idf_filename}")
        shutil.copyfile(original_idf_filepath, copy_idf_filepath)

        # The upload stays pristine so it can be restored; edits go to the sandbox.
        idf_session.load(original_idf_filepath)
        idf_session.mutate(apply_verbose)
        idf_session.mutate(strip_external_interface)
        # EnergyPlus 9.6 defect with EMS-driven blinds: see fix_ems_blind_override.
        ems_blind_fixed = idf_session.mutate(fix_ems_blind_override)
        fix_ems_blind_override_file(copy_idf_filepath)

        modify_idf_for_one_day_simulation(copy_idf_filepath)
        add_verbose(copy_idf_filepath)
        add_surface_details(copy_idf_filepath)

        delete_external_interface(copy_idf_filepath)

        session["progress"] = 10
        session.modified = True

        simulation_success = run_energyplus_simulation(copy_idf_filepath, epw_filepath)

        session["progress"] = 25
        session.modified = True

        if not simulation_success:
            return jsonify({'error': 'Simulation failed. Please check the simulation inputs.'}), 500
        
        else:
            edd_files = glob.glob(os.path.join(SIMULATION_OUTPUTS, '*.edd'))
            rdd_files = glob.glob(os.path.join(SIMULATION_OUTPUTS, '*.rdd'))

            if edd_files:
                edd_Actuators = parse_edd_file(edd_files[0])
                for actuator in edd_Actuators:
                    new_edd_actuator = edd_Actuator(
                        Component_Unique_Name=actuator['Component_Unique_Name'],
                        Component_Type=actuator['Component_Type'],
                        Control_Type=actuator['Control_Type']
                    )
                    db.session.add(new_edd_actuator)
                    db.session.commit()

                session["progress"] = 50
                session.modified = True

            else:
                return jsonify({'error': 'No EDD file found after simulation.'}), 404
            
            if rdd_files:
                rdd_Variables = parse_rdd_file(rdd_files[0])
                for variable in rdd_Variables:
                    new_rdd_variable = rdd_Variable(
                        Var_Type=variable['Var_Type'],
                        Variable_Name=variable['Variable_Name']
                    )
                    db.session.add(new_rdd_variable)
                    db.session.commit()
                session["progress"] = 75
                session.modified = True
            else:
                return jsonify({'error': 'No RDD file found after simulation.'}), 404

            # The exact key of every report variable (zone, surface, node...),
            # so a sensor can only be built on a key that exists.
            probe_variable_keys(copy_idf_filepath, epw_filepath)
            
            populate_tables(original_idf_filepath)
            session['progress'] = 100

            # The two files saved above, by name: inject_data must not pick "the first
            # .idf in uploads/" itself. SURROGATE_ENGINE reaches it through the environment.
            subprocess.run(["python", "inject_data.py", original_idf_filename, epw_filename],
                           check=True)

            message = 'Files Processed and Simulation Completed Successfully.'
            if ems_blind_fixed:
                message += (f'\n\n{len(ems_blind_fixed)} WindowShadingControl set to AlwaysOn '
                            f'({", ".join(ems_blind_fixed)}): their blinds are driven by an EMS '
                            'program, and EnergyPlus 9.6 evaluates a blind the EMS deploys '
                            'with uninitialised optical data unless the control is on. '
                            'The EMS still decides when the blinds are down.')
            return jsonify({
                'message': message,
                'versionCheck': version_check,
                'emsBlindFixed': ems_blind_fixed,
            }), 200
    except Exception as e:
        print(f"ERROR en /upload_files: {e}", flush=1)
        print(format_exc(), flush=1)
        return {"error": str(e)}, 500

@model_editor_bp.route('/progress', methods=['GET'])
def get_progress():
    progress_1 = session.get("progress", 75)  # Usar get para manejar sesiones no inicializadas
    return jsonify({'progress': progress_1}), 200

@model_editor_bp.route('/add_output_variable', methods=['POST'])
def add_output_variable():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()
        new_output_variable_info=current_output_variable(
            Key_Value=data['keyValue'],
            Variable_Name=data['oVariableName'],
            Reporting_Frequency=data['reportingFrequency'],
            Schedule_Name=data['scheduleName']
        )
        db.session.add(new_output_variable_info)
        db.session.commit()
        # Add the Output:Variable object
        new_output_variable = idf.newidfobject('Output:Variable')
        new_output_variable.Key_Value = data['keyValue']
        new_output_variable.Variable_Name = data['oVariableName']
        new_output_variable.Reporting_Frequency = data['reportingFrequency']

        if data['scheduleName'] != '':
            new_output_variable.Schedule_Name=data['scheduleName']

        # Add additional objects based on addType
        if data.get('addType') == 'output_variable_with_ems_sensor' or data.get('addType') == 'output_variable_with_both':
            new_ems_sensor_info= current_ems_sensor(
                Name=data['name'],
                OutputVariable_or_OutputMeter_Index_Key_Name=data['keyValue'],
                OutputVariable_or_OutputMeter_Name=data['oVariableName']
            )
            db.session.add(new_ems_sensor_info)
            db.session.commit()

            new_ems_sensor = idf.newidfobject('EnergyManagementSystem:Sensor')
            new_ems_sensor.Name = data['name']
            new_ems_sensor.OutputVariable_or_OutputMeter_Index_Key_Name = data['keyValue']
            new_ems_sensor.OutputVariable_or_OutputMeter_Name = data['oVariableName']

        if data.get('addType') == 'output_variable_with_external_from_variable' or data.get('addType') == 'output_variable_with_both':
            new_fmu_from_variable_info= current_fmu_from_variable(
                OutputVariable_Index_Key_Name=data['keyValue'],
                OutputVariable_Name=data['oVariableName'],
                FMU_Variable_Name=data['fmuVariableName']
            )
            db.session.add(new_fmu_from_variable_info)
            db.session.commit()

            new_fmu_from_variable = idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:From:Variable')
            new_fmu_from_variable.OutputVariable_Index_Key_Name = data['keyValue']
            new_fmu_from_variable.OutputVariable_Name = data['oVariableName']
            new_fmu_from_variable.FMU_Variable_Name = data['fmuVariableName']

        idf.save()

        return jsonify({'message': 'Variable added successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500

@model_editor_bp.route('/add_ems_sensor', methods=['POST'])
def add_ems_sensor():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_ems_sensor_info= current_ems_sensor(
            Name=data['name'],
            OutputVariable_or_OutputMeter_Index_Key_Name=data['outputVariableOrOutputMeterIndexKeyName'],
            OutputVariable_or_OutputMeter_Name=data['outputVariableOrOutputMeterName']
        )
        db.session.add(new_ems_sensor_info)
        db.session.commit()

        # A meter source must NOT get a mirrored Output:Variable -- that request is
        # invalid and EnergyPlus rejects it. Meters are reported via Output:Meter.
        is_meter = data.get('sourceType') == 'meter'

        if not is_meter:
            new_output_variable_info=current_output_variable(
                Key_Value=data['outputVariableOrOutputMeterIndexKeyName'],
                Variable_Name=data['outputVariableOrOutputMeterName'],
                Reporting_Frequency='Timestep',
                Schedule_Name=''
            )
            db.session.add(new_output_variable_info)
            db.session.commit()

        new_ems_sensor=idf.newidfobject('EnergyManagementSystem:Sensor')
        new_ems_sensor.Name=data['name']
        new_ems_sensor.OutputVariable_or_OutputMeter_Index_Key_Name=data['outputVariableOrOutputMeterIndexKeyName']
        new_ems_sensor.OutputVariable_or_OutputMeter_Name=data['outputVariableOrOutputMeterName']

        if is_meter:
            new_output_meter=idf.newidfobject('Output:Meter')
            new_output_meter.Key_Name=data['outputVariableOrOutputMeterName']
            new_output_meter.Reporting_Frequency='Timestep'
        else:
            new_output_variable=idf.newidfobject('Output:Variable')
            new_output_variable.Key_Value=data['outputVariableOrOutputMeterIndexKeyName']
            new_output_variable.Variable_Name=data['outputVariableOrOutputMeterName']
            new_output_variable.Reporting_Frequency='Timestep'

        idf.save()

        return jsonify({'message': 'Sensor Added cuccesfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500

@model_editor_bp.route('/add_ems_actuator', methods=['POST'])
def add_ems_actuator():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_ems_actuator_info= current_ems_actuator(
            Name=data['name'],
            Actuated_Component_Unique_Name=data['actuatedComponentUniqueName'],
            Actuated_Component_Type=data['actuatedComponentType'],
            Actuated_Component_Control_Type=data['actuatedComponentControlType']
        )
        db.session.add(new_ems_actuator_info)
        db.session.commit()

        new_ems_actuator=idf.newidfobject('EnergyManagementSystem:Actuator')
        new_ems_actuator.Name=data['name']
        new_ems_actuator.Actuated_Component_Unique_Name=data['actuatedComponentUniqueName']
        new_ems_actuator.Actuated_Component_Type=data['actuatedComponentType']
        new_ems_actuator.Actuated_Component_Control_Type=data['actuatedComponentControlType']

        idf.save()

        return jsonify({'message': 'Actuator Added Successfully'}), 200
    
    except Exception as e:
         return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500

@model_editor_bp.route('/add_fmu_actuator', methods=['POST'])
def add_fmu_actuator():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_fmu_actuator_info= current_fmu_actuator(
            Name=data['name'],
            Actuated_Component_Unique_Name=data['actuatedComponentUniqueName'],
            Actuated_Component_Type=data['actuatedComponentType'],
            Actuated_Component_Control_Type=data['actuatedComponentControlType'],
            FMU_Variable_Name=data['fmuVariableName'],
            Initial_Value=data['initialValue']
        )
        db.session.add(new_fmu_actuator_info)
        db.session.commit()

        new_fmu_actuator=idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:To:Actuator')
        new_fmu_actuator.Name=data['name']
        new_fmu_actuator.Actuated_Component_Unique_Name=data['actuatedComponentUniqueName']
        new_fmu_actuator.Actuated_Component_Type=data['actuatedComponentType']
        new_fmu_actuator.Actuated_Component_Control_Type=data['actuatedComponentControlType']
        new_fmu_actuator.FMU_Variable_Name=data['fmuVariableName']
        new_fmu_actuator.Initial_Value=data['initialValue']

        idf.save()

        return jsonify({'message': 'FMU Actuator Added Successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500
    
@model_editor_bp.route('/add_fmu_from_variable', methods=['POST'])
def add_fmu_from_variable():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_fmu_from_variable_info= current_fmu_from_variable(
            OutputVariable_Index_Key_Name=data['outputVariableIndexKeyName'],
            OutputVariable_Name=data['outputVariableName'],
            FMU_Variable_Name=data['fmuVariableName']
        )
        db.session.add(new_fmu_from_variable_info)
        db.session.commit()

        new_output_variable_info = current_output_variable(
            Key_Value=data['outputVariableIndexKeyName'],
            Variable_Name=data['outputVariableName'],
            Reporting_Frequency='Timestep',
            Schedule_Name=''
        )
        db.session.add(new_output_variable_info)
        db.session.commit()

        new_fmu_from_variable=idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:From:Variable')
        new_fmu_from_variable.OutputVariable_Index_Key_Name=data['outputVariableIndexKeyName']
        new_fmu_from_variable.OutputVariable_Name=data['outputVariableName']
        new_fmu_from_variable.FMU_Variable_Name=data['fmuVariableName']

        new_output_variable=idf.newidfobject('Output:Variable')
        new_output_variable.Key_Value=data['outputVariableIndexKeyName']
        new_output_variable.Variable_Name=data['outputVariableName']
        new_output_variable.Reporting_Frequency='Timestep'

        idf.save()

        return jsonify({'message': 'FMU From Variable Added Succesfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500
    
@model_editor_bp.route('/add_fmu_to_variable', methods=['POST'])
def add_fmu_to_variable():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_fmu_to_variable_info= current_fmu_to_variable(
            Name=data['name'],
            FMU_Variable_Name=data['fmuVariableName'],
            Initial_Value=data['initialValue']
        )
        db.session.add(new_fmu_to_variable_info)
        db.session.commit()

        new_fmu_to_variable=idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:To:Variable')
        new_fmu_to_variable.Name=data['name']
        new_fmu_to_variable.FMU_Variable_Name=data['fmuVariableName']
        new_fmu_to_variable.Initial_Value=data['initialValue']

        idf.save()

        return jsonify({'message': 'FMU To Variable Added Successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500
    
@model_editor_bp.route('/add_fmu_schedule', methods=['POST'])
def add_fmu_schedule():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()
        schedule_name = data['scheduleName']

        # Check if the name type is existing_schedule and remove existing schedules with the same name
        if data.get('nameType') == 'existing_schedule':
            schedule_types = ['Schedule:Day:Hourly', 'Schedule:Day:Interval', 'Schedule:Day:List',
                              'Schedule:Week:Daily', 'Schedule:Week:Compact', 'Schedule:Year',
                              'Schedule:Compact', 'Schedule:Constant', 'Schedule:File:Shading', 'Schedule:File']

            for schedule_type in schedule_types:
                schedules = idf.idfobjects[schedule_type]
                for schedule in schedules:
                    if schedule.Name == schedule_name:
                        idf.removeidfobject(schedule)

        # Now, add the new schedule to the IDF
        new_fmu_schedule = idf.newidfobject('ExternalInterface:FunctionalMockupUnitExport:To:Schedule')
        new_fmu_schedule.Schedule_Name = schedule_name
        new_fmu_schedule.Schedule_Type_Limits_Names = data['scheduleTypeLimitsNames']
        new_fmu_schedule.FMU_Variable_Name = data['fmuVariableName']
        new_fmu_schedule.Initial_Value = data['initialValue']

        idf.save()

        # Add the new schedule information to the database
        new_fmu_schedule_info = current_fmu_schedule(
            Schedule_Name=schedule_name,
            Schedule_Type_Limits_Names=data['scheduleTypeLimitsNames'],
            FMU_Variable_Name=data['fmuVariableName'],
            Initial_Value=data['initialValue']
        )
        db.session.add(new_fmu_schedule_info)
        db.session.commit()

        return jsonify({'message': 'FMU Schedule Added Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Add Object.', 'details': str(e)}), 500
    
@model_editor_bp.route('/add_ems_program_calling_manager', methods=['POST'])
def add_ems_program_calling_manager():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try: 
        data = request.get_json()
        new_program_calling_manager_info = CurrentEMSProgramCallingManager (
            name=data['name'],
            energy_plus_model_calling_point=data['energyPlusModelCallingPoint']
        )
        for program_name in data['programNames']:
            new_program_calling_manager_info.program_names.append(ProgramName(line_text=program_name))
            
        db.session.add(new_program_calling_manager_info)
        db.session.commit()

        new_program_calling_manager=idf.newidfobject('EnergyManagementSystem:ProgramCallingManager')
        new_program_calling_manager.Name=data['name']
        new_program_calling_manager.EnergyPlus_Model_Calling_Point=data['energyPlusModelCallingPoint']

        for i, program in enumerate(data['programNames'], start=1):
            setattr(new_program_calling_manager, f'Program_Name_{i}', program)
            
        idf.save()

        return jsonify({'message': 'Program Calling Manager Added Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Add Object', 'details': str(e)}), 500
    
@model_editor_bp.route('/add_ems_program', methods=['POST'])
def add_ems_program():
    idf_path=glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf=IDF(idf_path[0])
    try:
        data = request.get_json()
        new_program_info = CurrentEMSProgram(
            name=data['name']
        )
        for program_line in data['programLines']:
            new_program_info.program_lines.append(ProgramLine(line_text=program_line))

        db.session.add(new_program_info)
        db.session.commit()
        
        new_program=idf.newidfobject('EnergyManagementSystem:Program')
        new_program.Name=data['name']

        for i, line in enumerate(data['programLines'], start=1):
            setattr(new_program, f'Program_Line_{i}', line)
            
        idf.save()

        return jsonify({'message': 'Program Added Successfylly'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to Add Object', 'details': str(e)}), 500

@model_editor_bp.route('/add_ems_output_variable', methods=['POST'])
def add_ems_output_variable():
    try:
        data = request.get_json()

        def build(idf):
            obj = idf.newidfobject('EnergyManagementSystem:OutputVariable')
            obj.Name = data['name']
            obj.EMS_Variable_Name = data['variableName']
            obj.Type_of_Data_in_Variable = data['typeOfData']
            obj.Update_Frequency = data['updateFrequency']
            if data.get('emsProgramOrSub'):
                obj.EMS_Program_or_Subroutine_Name = data['emsProgramOrSub']
            if data.get('units'):
                obj.Units = data['units']

        idf_session.mutate(build)
        return jsonify({'message': 'EMS Output Variable added'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Add Object', 'details': str(e)}), 500


@model_editor_bp.route('/add_monitored_quantity', methods=['POST'])
def add_monitored_quantity():
    """Expose one quantity to the FMU, building the whole EMS chain behind it."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_chain.add_monitored_quantity(
            idf,
            source_type=data['sourceType'],
            source_name=data['sourceName'],
            name=data['name'],
            index_key=data.get('indexKey', ''),
            fmu_variable_name=data.get('fmuVariableName')
        ))
        return jsonify({'message': 'Quantity is now exported to the FMU.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to monitor quantity.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_monitored_quantity', methods=['DELETE'])
def remove_monitored_quantity():
    try:
        data = request.get_json()
        def remove(idf):
            quantity = ems_chain.sanitize_name(data['name'])
            names = _fmu_names(idf, 'from', lambda o: o.OutputVariable_Index_Key_Name == ems_chain.EMS_KEY
                               and o.OutputVariable_Name == quantity)
            ems_chain.remove_monitored_quantity(idf, data['name'])
            return names
        _drop_roles(idf_session.mutate(remove))
        return jsonify({'message': 'Quantity removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove quantity.', 'details': str(e)}), 500


@model_editor_bp.route('/add_controlled_actuator', methods=['POST'])
def add_controlled_actuator():
    """Declare an actuator and wire it to the FMU in one step."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_chain.add_controlled_actuator(
            idf,
            name=data['name'],
            component_name=data['actuatedComponentUniqueName'],
            component_type=data['actuatedComponentType'],
            control_type=data['actuatedComponentControlType'],
            fmu_variable_name=data.get('fmuVariableName'),
            initial_value=data.get('initialValue', 0),
            monitor_status=data.get('monitorStatus', True)
        ))
        return jsonify({'message': 'Actuator is now controllable from the FMU.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to add actuator.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_controlled_actuator', methods=['DELETE'])
def remove_controlled_actuator():
    try:
        data = request.get_json()
        def remove(idf):
            # The input itself (To:Variable) and its '<name>_status' output.
            name = ems_chain.sanitize_name(data['name'])
            status = '{}_status'.format(name)
            names = _fmu_names(idf, 'variable', lambda o: o.Name == name)
            names += _fmu_names(idf, 'from', lambda o: o.OutputVariable_Index_Key_Name == ems_chain.EMS_KEY
                                and o.OutputVariable_Name == status)
            ems_chain.remove_controlled_actuator(idf, data['name'])
            return names
        _drop_roles(idf_session.mutate(remove))
        return jsonify({'message': 'Actuator removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove actuator.', 'details': str(e)}), 500


def _original_ems_names():
    """Which EMS objects the uploaded file already had: those are the model's."""
    return ems_programs.original_names(idf_session.original_path())


@model_editor_bp.route('/ems_programs', methods=['GET'])
def get_ems_programs_catalogue():
    """The programs of the model, the variables they can use, and the calling points."""
    try:
        if not idf_session.has_model():
            return jsonify({'programs': [], 'variables': {}, 'callingPoints': []}), 200
        idf = idf_session.get()
        return jsonify({
            'programs': ems_programs.list_programs(idf, _original_ems_names()),
            'managers': ems_programs.list_managers(idf, _original_ems_names()),
            'modelEms': ems_programs.model_ems_state(idf, _original_ems_names()),
            'runtime': ems_programs.runtime_info(idf),
            'variables': ems_programs.list_variables(idf),
            'callingPoints': [{'name': n, 'control': c, 'hint': h} for n, c, h in ems_programs.CALLING_POINTS],
            'defaultCallingPoint': ems_programs.DEFAULT_CALLING_POINT,
        }), 200

    except Exception as e:
        return jsonify({'error': 'Failed to read the EMS programs.', 'details': str(e)}), 500


@model_editor_bp.route('/check_ems_program', methods=['POST'])
def check_ems_program():
    try:
        errors, warnings = ems_programs.check(idf_session.get(), request.get_json().get('lines', []))
        return jsonify({'errors': errors, 'warnings': warnings}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to check the program.', 'details': str(e)}), 500


@model_editor_bp.route('/save_ems_program', methods=['POST'])
def save_ems_program():
    """Create or rewrite a program or subroutine; a new program can join a manager."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_programs.save_program(
            idf, _original_ems_names(), data['name'], data['lines'], data.get('kind', 'program'),
            manager=data.get('manager'), calling_point=data.get('callingPoint')))
        return jsonify({'message': 'Program saved.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to save the program.', 'details': str(e)}), 400


@model_editor_bp.route('/remove_ems_program', methods=['DELETE'])
def remove_ems_program():
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_programs.remove_program(
            idf, _original_ems_names(), data['name']))
        return jsonify({'message': 'Program removed.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove the program.', 'details': str(e)}), 400


@model_editor_bp.route('/save_ems_manager', methods=['POST'])
def save_ems_manager():
    """Create or rewrite a calling manager: its calling point and its programs, in order."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_programs.save_manager(
            idf, _original_ems_names(), data['name'], data['callingPoint'], data['programs']))
        return jsonify({'message': 'Calling manager saved.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to save the calling manager.', 'details': str(e)}), 400


@model_editor_bp.route('/set_model_ems', methods=['POST'])
def set_model_ems():
    """Switch the model's own EMS on or off, all of it or one calling manager."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_programs.set_model_ems(
            idf, _original_ems_names(), bool(data['enabled']), data.get('name')))
        return jsonify({'message': "The model's EMS is {}.".format('on' if data['enabled'] else 'off'), **result}), 200

    except Exception as e:
        return jsonify({'error': "Failed to switch the model's EMS.", 'details': str(e)}), 400


@model_editor_bp.route('/remove_ems_manager', methods=['DELETE'])
def remove_ems_manager():
    try:
        data = request.get_json()
        idf_session.mutate(lambda idf: ems_programs.remove_manager(idf, _original_ems_names(), data['name']))
        return jsonify({'message': 'Calling manager removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove the calling manager.', 'details': str(e)}), 400


@model_editor_bp.route('/add_ems_variable', methods=['POST'])
def add_ems_variable():
    """Declare a sensor, actuator, FMU input, global or trend variable for programs to use."""
    try:
        data = dict(request.get_json())
        kind, name = data.pop('kind'), data.pop('name')
        result = idf_session.mutate(lambda idf: ems_programs.add_variable(idf, kind, name, **data))
        return jsonify({'message': 'Variable added.', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to add the variable.', 'details': str(e)}), 400


@model_editor_bp.route('/remove_ems_variable', methods=['DELETE'])
def remove_ems_variable():
    try:
        data = request.get_json()
        def remove(idf):
            names = (_fmu_names(idf, 'variable', lambda o: o.Name == data['name'])
                     if data['kind'] == 'fmuInput' else [])
            ems_programs.remove_variable(idf, data['kind'], data['name'])
            return names
        _drop_roles(idf_session.mutate(remove))
        return jsonify({'message': 'Variable removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove the variable.', 'details': str(e)}), 400


@model_editor_bp.route('/add_direct_variable', methods=['POST'])
def add_direct_variable():
    """Export a report variable to the FMU with no EMS objects at all."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_chain.add_direct_variable(
            idf, data['indexKey'], data['variableName'], data['fmuVariableName']))
        return jsonify({'message': 'Variable is now exported to the FMU (direct).', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to export the variable.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_direct_variable', methods=['DELETE'])
def remove_direct_variable():
    try:
        data = request.get_json()
        idf_session.mutate(lambda idf: ems_chain.remove_direct_variable(idf, data['fmuVariableName']))
        fmu_roles.drop(data['fmuVariableName'])
        return jsonify({'message': 'Export removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove the export.', 'details': str(e)}), 500


@model_editor_bp.route('/add_direct_actuator', methods=['POST'])
def add_direct_actuator():
    """The FMU writes the actuator itself: To:Actuator alone, no EMS program."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_chain.add_direct_actuator(
            idf,
            name=data['name'],
            component_name=data['actuatedComponentUniqueName'],
            component_type=data['actuatedComponentType'],
            control_type=data['actuatedComponentControlType'],
            fmu_variable_name=data.get('fmuVariableName'),
            initial_value=data.get('initialValue', 0)
        ))
        return jsonify({'message': 'Actuator is now an FMU input (direct).', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to add actuator.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_direct_actuator', methods=['DELETE'])
def remove_direct_actuator():
    try:
        data = request.get_json()
        def remove(idf):
            names = _fmu_names(idf, 'actuator', lambda o: o.Name == data['name'])
            ems_chain.remove_direct_actuator(idf, data['name'])
            return names
        _drop_roles(idf_session.mutate(remove))
        return jsonify({'message': 'Actuator removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove actuator.', 'details': str(e)}), 500


_SCHEDULE_CACHE = {'generation': None, 'value': []}


def _schedule_candidates():
    """Every top-level schedule with who uses it and what a controller could do.

    Cached per model generation: reading a real model's schedules takes a moment.
    """
    import schedule_model
    generation = idf_session.generation()
    if _SCHEDULE_CACHE['generation'] != generation:
        idf = idf_session.get()
        rows = []
        for s in schedule_model.overview(idf):
            external = bool(s.get('external'))
            rows.append({
                'name': s['name'],
                'type': s['type'],
                'limits': s.get('limits', ''),
                'external': external,
                'initialValue': s.get('initialValue') if external else None,
                'suggestedInitial': None if external else ems_chain.suggest_initial_value(idf, s['name']),
                'replaceable': s['type'] in ems_chain.REPLACEABLE_SCHEDULES,
                'users': [{'class': u['class'], 'object': u['object'], 'field': u['field']}
                          for u in s.get('users', [])],
                'overrides': [{'by': o['by'], 'name': o['name'], 'programs': o['programs'],
                               'releases': o['releases']} for o in s.get('overrides', [])],
            })
        _SCHEDULE_CACHE.update(generation=generation, value=rows)
    return _SCHEDULE_CACHE['value']


@model_editor_bp.route('/schedule_candidates', methods=['GET'])
def schedule_candidates():
    try:
        if not idf_session.has_model():
            return jsonify({'schedules': []}), 200
        import schedule_model
        if _SCHEDULE_CACHE.get('thermostats_generation') != idf_session.generation():
            _SCHEDULE_CACHE['thermostats'] = schedule_model.thermostats(idf_session.get())
            _SCHEDULE_CACHE['thermostats_generation'] = idf_session.generation()
        return jsonify({'schedules': _schedule_candidates(),
                        'thermostats': _SCHEDULE_CACHE['thermostats']}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to read the schedules.', 'details': str(e)}), 500


@model_editor_bp.route('/add_direct_schedule', methods=['POST'])
def add_direct_schedule():
    """The FMU writes a whole schedule: To:Schedule replaces it, no EMS program."""
    try:
        data = request.get_json()
        result = idf_session.mutate(lambda idf: ems_chain.add_direct_schedule(
            idf,
            schedule_name=data['scheduleName'],
            fmu_variable_name=data.get('fmuVariableName'),
            initial_value=data.get('initialValue')
        ))
        return jsonify({'message': 'Schedule is now an FMU input (direct).', **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to add schedule.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_direct_schedule', methods=['DELETE'])
def remove_direct_schedule():
    try:
        data = request.get_json()
        def remove(idf):
            wanted = data['scheduleName'].strip().upper()
            names = _fmu_names(idf, 'schedule', lambda o: str(o.Schedule_Name).strip().upper() == wanted)
            return ems_chain.remove_direct_schedule(idf, data['scheduleName'], idf_session.original_path()), names
        result, names = idf_session.mutate(remove)
        _drop_roles(names)
        message = ('Schedule restored from the uploaded model.' if result['restored']
                   else 'Schedule removed from the FMU inputs; the uploaded model has no schedule of that name to restore.')
        return jsonify({'message': message, **result}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove schedule.', 'details': str(e)}), 500


@model_editor_bp.route('/add_output_meter', methods=['POST'])
def add_output_meter():
    try:
        data = request.get_json()

        def build(idf):
            obj = idf.newidfobject('Output:Meter')
            obj.Key_Name = data['keyName']
            obj.Reporting_Frequency = data.get('reportingFrequency', 'Timestep')

        idf_session.mutate(build)
        return jsonify({'message': 'Output Meter added.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Add Object', 'details': str(e)}), 500


@model_editor_bp.route('/remove_output_meters', methods=['DELETE'])
def remove_output_meters():
    try:
        data = request.get_json()

        def strip(idf):
            for meter in list(idf.idfobjects['Output:Meter']):
                if meter.Key_Name == data['keyName']:
                    idf.removeidfobject(meter)

        idf_session.mutate(strip)
        return jsonify({'message': 'Output Meter removed.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove Object', 'details': str(e)}), 500


@model_editor_bp.route('/revert_to_original', methods=['POST'])
def revert_to_original():
    """Discard every edit and restore the model the student uploaded."""
    try:
        idf_session.reset()
        fmu_roles.clear()
        return jsonify({'message': 'Model restored to the uploaded original.'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to restore model.', 'details': str(e)}), 500


@model_editor_bp.route('/remove_output_variables', methods=['DELETE'])
def remove_output_variables():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_output_variables = idf.idfobjects['Output:Variable']
        for variable in current_output_variables:
            if variable.Key_Value == data['keyValue'] and variable.Variable_Name == data['variableName'] and variable.Reporting_Frequency == data['reportingFrequency']:
                idf.removeidfobject(variable)
                break

            # Remove associated EMS Sensors
        current_ems_sensors = idf.idfobjects['EnergyManagementSystem:Sensor']
        sensors_to_remove = [sensor for sensor in current_ems_sensors if sensor.OutputVariable_or_OutputMeter_Index_Key_Name == data['keyValue'] and sensor.OutputVariable_or_OutputMeter_Name == data['variableName']]
        for sensor in sensors_to_remove:
            idf.removeidfobject(sensor)

            # Remove associated FMU From Variables
        current_fmu_from_variables = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable']
        from_vars_to_remove = [var for var in current_fmu_from_variables if var.OutputVariable_Index_Key_Name == data['keyValue'] and var.OutputVariable_Name == data['variableName']]
        for var in from_vars_to_remove:
            fmu_roles.drop(str(var.FMU_Variable_Name))
            idf.removeidfobject(var)

        idf.save()

            # Remove from database
        current_output_variable.query.filter_by(Key_Value=data['keyValue'], Variable_Name=data['variableName'], Reporting_Frequency=data['reportingFrequency']).delete()
        db.session.commit()
        current_ems_sensor.query.filter_by(OutputVariable_or_OutputMeter_Index_Key_Name=data['keyValue'], OutputVariable_or_OutputMeter_Name=data['variableName']).delete()
        db.session.commit()
        current_fmu_from_variable.query.filter_by(OutputVariable_Index_Key_Name=data['keyValue'], OutputVariable_Name=data['variableName']).delete()
        db.session.commit()

        return jsonify({'message': 'Output Variable and associated objects removed successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove Output Variable and associated objects.', 'details': str(e)}), 500

@model_editor_bp.route('/remove_ems_sensors', methods=['DELETE'])
def remove_ems_sensors():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_ems_sensors = idf.idfobjects['EnergyManagementSystem:Sensor']
        for sensor in current_ems_sensors:
            if sensor.Name == data['name']:
                idf.removeidfobject(sensor)
                break

        current_output_variables = idf.idfobjects['Output:Variable']
        for variable in current_output_variables:
            if variable.Key_Value==data['outputVariableOrOutputMeterIndexKeyName'] and variable.Variable_Name==data['outputVariableOrOutputMeterName']:
                idf.removeidfobject(variable)
        
        idf.save()

        # Remove from database
        db_sensor = current_ems_sensor.query.filter_by(Name=data['name']).first()
        if db_sensor:
            db.session.delete(db_sensor)
            db.session.commit()

        db_output_variables = current_output_variable.query.filter_by(Key_Value=data['outputVariableOrOutputMeterIndexKeyName'], Variable_Name=data['outputVariableOrOutputMeterName'])
        if db_output_variables:
            for variable in db_output_variables:
                db.session.delete(variable)
                db.session.commit()

        return jsonify({'message': 'Sensor Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove Sensor', 'details': str(e)}), 500

@model_editor_bp.route('/remove_ems_actuators', methods=['DELETE'])
def remove_ems_actuators():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_ems_actuators = idf.idfobjects['EnergyManagementSystem:Actuator']
        for actuator in current_ems_actuators:
            if actuator.Name == data['name']:
                idf.removeidfobject(actuator)
                break
        
        idf.save()

        # Remove from database
        db_actuator = current_ems_actuator.query.filter_by(Name=data['name']).first()
        if db_actuator:
            db.session.delete(db_actuator)
            db.session.commit()

        return jsonify({'message': 'Actuator Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove Actuator', 'details': str(e)}), 500

@model_editor_bp.route('/remove_ems_program_calling_managers', methods=['DELETE'])
def remove_ems_program_calling_managers():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_ems_program_calling_managers = idf.idfobjects['EnergyManagementSystem:ProgramCallingManager']
        for manager in current_ems_program_calling_managers:
            if manager.Name == data['name']:
                idf.removeidfobject(manager)
                break
        
        idf.save()

        # Remove from database
        db_manager = CurrentEMSProgramCallingManager.query.filter_by(name=data['name']).first()
        if db_manager:
            db.session.delete(db_manager)
            db.session.commit()

        return jsonify({'message': 'Program Calling Manager Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove Program Calling Manager', 'details': str(e)}), 500

@model_editor_bp.route('/remove_ems_programs', methods=['DELETE'])
def remove_ems_programs():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()
        program_name = data['name']

        # Remove from IDF
        current_ems_programs = idf.idfobjects['EnergyManagementSystem:Program']
        programs_to_remove = set()

        for program in current_ems_programs:
            if program.Name == program_name:
                idf.removeidfobject(program)
                programs_to_remove.add(program_name)

        # Regex pattern to match exact program names
        program_pattern = re.compile(r'\b' + re.escape(program_name) + r'\b')

        # Find and remove programs that reference the deleted program in their lines
        for program in current_ems_programs:
            program_lines = []
            for i in range(1, 500):  # Assuming there won't be more than 500 lines in a program
                line_attr = f'Program_Line_{i}'
                if hasattr(program, line_attr):
                    line = getattr(program, line_attr)
                    program_lines.append(line)
                else:
                    break

            # Use regex to match exact program names
            if any(program_pattern.search(line) for line in program_lines):
                programs_to_remove.add(program.Name)
                idf.removeidfobject(program)

        # Remove related entries in ProgramCallingManagers
        current_program_calling_managers = idf.idfobjects['EnergyManagementSystem:ProgramCallingManager']
        for manager in current_program_calling_managers:
            manager_programs = [getattr(manager, f'Program_Name_{i}') for i in range(1, 500) if hasattr(manager, f'Program_Name_{i}')]
            if any(prog in manager_programs for prog in programs_to_remove):
                idf.removeidfobject(manager)

        idf.save()

        # Remove from database
        for prog in programs_to_remove:
            db_program = CurrentEMSProgram.query.filter_by(name=prog).first()
            if db_program:
                db.session.delete(db_program)
                db.session.commit()

        # Remove related entries in CurrentEMSProgramCallingManager
        db_managers = CurrentEMSProgramCallingManager.query.all()
        for manager in db_managers:
            manager_programs = [name.line_text for name in manager.program_names]
            if any(prog in manager_programs for prog in programs_to_remove):
                db.session.delete(manager)
                db.session.commit()

        return jsonify({'message': 'Program and related entries removed successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove program', 'details': str(e)}), 500

@model_editor_bp.route('/remove_fmu_actuators', methods=['DELETE'])
def remove_fmu_actuators():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])

    try:
        data = request.get_json()

        current_fmu_actuators = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Actuator']
        for actuator in current_fmu_actuators:
            if actuator.Name == data['name']:
                _drop_roles([str(actuator.FMU_Variable_Name)])
                idf.removeidfobject(actuator)
                break
        
        idf.save()

        # Remove from database
        db_actuator = current_fmu_actuator.query.filter_by(Name=data['name']).first()
        if db_actuator:
            db.session.delete(db_actuator)
            db.session.commit()

        return jsonify({'message': 'FMU Actuator Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove FMU Actuator', 'details': str(e)}), 500

@model_editor_bp.route('/remove_fmu_from_variables', methods=['DELETE'])
def remove_fmu_from_variables():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_fmu_from_variables = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable']
        for variable in current_fmu_from_variables:
            if variable.FMU_Variable_Name == data['fmuVariableName']:
                idf.removeidfobject(variable)
                fmu_roles.drop(data['fmuVariableName'])
                break

        current_output_variables = idf.idfobjects['Output:Variable']
        for variable in current_output_variables:
            if variable.Key_Value==data['outputVariableIndexKeyName'] and variable.Variable_Name==data['outputVariableName']:
                idf.removeidfobject(variable)
        
        idf.save()

        # Remove from database
        db_variable = current_fmu_from_variable.query.filter_by(FMU_Variable_Name=data['fmuVariableName']).first()
        if db_variable:
            db.session.delete(db_variable)
            db.session.commit()

        db_output_variables = current_output_variable.query.filter_by(Key_Value=data['outputVariableIndexKeyName'], Variable_Name=data['outputVariableName'])
        if db_output_variables:
            for variable in db_output_variables:
                db.session.delete(variable)
                db.session.commit()

        return jsonify({'message': 'From:Variable Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove From:Variable', 'details': str(e)}), 500

@model_editor_bp.route('/remove_fmu_to_variables', methods=['DELETE'])
def remove_fmu_to_variables():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()
        variable_name = data['name']

        # Remove from IDF
        current_fmu_to_variables = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Variable']
        variables_to_remove = set()

        for variable in current_fmu_to_variables:
            if variable.Name == variable_name:
                variables_to_remove.add(variable.Name)
                fmu_roles.drop(str(variable.FMU_Variable_Name))
                idf.removeidfobject(variable)
                break

        # Regex pattern to match exact variable names
        variable_pattern = re.compile(r'\b' + re.escape(variable_name) + r'\b')

        # Find and remove programs that reference the deleted variable in their lines
        current_ems_programs = idf.idfobjects['EnergyManagementSystem:Program']
        programs_to_remove = set()

        for program in current_ems_programs:
            program_lines = []
            for i in range(1, 500):  # Assuming there won't be more than 500 lines in a program
                line_attr = f'Program_Line_{i}'
                if hasattr(program, line_attr):
                    line = getattr(program, line_attr)
                    program_lines.append(line)
                else:
                    break

            # Use regex to match exact variable names
            if any(variable_pattern.search(line) for line in program_lines):
                programs_to_remove.add(program.Name)
                idf.removeidfobject(program)

        # Remove related entries in ProgramCallingManagers
        current_program_calling_managers = idf.idfobjects['EnergyManagementSystem:ProgramCallingManager']
        for manager in current_program_calling_managers:
            manager_programs = [getattr(manager, f'Program_Name_{i}') for i in range(1, 500) if hasattr(manager, f'Program_Name_{i}')]
            if any(prog in programs_to_remove for prog in manager_programs):
                idf.removeidfobject(manager)

        idf.save()

        # Remove from database
        db_variable = current_fmu_to_variable.query.filter_by(Name=variable_name).first()
        if db_variable:
            db.session.delete(db_variable)
            db.session.commit()

        for prog in programs_to_remove:
            db_program = CurrentEMSProgram.query.filter_by(name=prog).first()
            if db_program:
                db.session.delete(db_program)
                db.session.commit()

        # Remove related entries in CurrentEMSProgramCallingManager
        db_managers = CurrentEMSProgramCallingManager.query.all()
        for manager in db_managers:
            manager_programs = [name.line_text for name in manager.program_names]
            if any(prog in manager_programs for prog in programs_to_remove):
                db.session.delete(manager)
                db.session.commit()

        return jsonify({'message': 'To:Variable and related entries removed successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to remove To:Variable', 'details': str(e)}), 500

@model_editor_bp.route('/remove_fmu_schedules', methods=['DELETE'])
def remove_fmu_schedules():
    idf_path = glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf'))
    IDF.setiddname(IDD_PATH)
    idf = IDF(idf_path[0])
    try:
        data = request.get_json()

        current_fmu_schedules = idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Schedule']
        for schedule in current_fmu_schedules:
            if schedule.Schedule_Name == data['scheduleName']:
                _drop_roles([str(schedule.FMU_Variable_Name)])
                idf.removeidfobject(schedule)
                break
        
        idf.save()

        # Remove from database
        db_schedule = current_fmu_schedule.query.filter_by(Schedule_Name=data['scheduleName']).first()
        if db_schedule:
            db.session.delete(db_schedule)
            db.session.commit()

        return jsonify({'message': 'Schedule Removed Successfully'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove FMU Schedule', 'details': str(e)}), 500
    
@model_editor_bp.route('/remove_ems_output_variables', methods=['DELETE'])
def remove_ems_output_variables():
    try:
        data = request.get_json()

        def strip(idf):
            for eo in list(idf.idfobjects['EnergyManagementSystem:OutputVariable']):
                if eo.Name == data['name']:
                    idf.removeidfobject(eo)
                    break

        idf_session.mutate(strip)
        return jsonify({'message': 'Removed'}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to Remove Object', 'details': str(e)}), 500


def clean_dir(path, keep=()):
    """
    Limpia un directorio borrando subdirectorios y archivos, pero preserva cualquier Dockerfile
    y las entradas de `keep`.
    """
    if os.path.isdir(path):
        for entry in os.listdir(path):
            # No borramos Dockerfile
            if entry == 'Dockerfile' or entry in keep:
                continue
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            elif os.path.isfile(full_path) or os.path.islink(full_path):
                os.remove(full_path)

def clear_workspace():
    """Empty the working state: SQL tables, files, notebooks restored from templates.

    Everything reset_session does except the Flask cookie session and InfluxDB.
    Raises on failure; the caller decides how to report it.
    """
    # 2) Delete all relevant DB entries (SQLAlchemy models)
    models = [
        edd_Actuator, rdd_Variable,
        current_ems_sensor, current_ems_actuator,
        CurrentEMSProgram, ProgramLine,
        CurrentEMSProgramCallingManager, ProgramName,
        current_fmu_actuator, current_fmu_from_variable,
        current_fmu_to_variable, current_fmu_schedule,
        existing_schedule_name, existing_shedule_type_limit,
        current_output_variable,
        idf_Material, idf_Construction,
        idf_FenestrationSurfaceDetailed,
        idf_ZoneVentilationDesignFlowRate,
        idf_Lights, idf_WindowShadingControl
    ]
    for model in models:
        model.query.delete()
    db.session.commit()

    # 3) Remove and recreate core directories
    fmu_roles.clear()
    idf_session.clear()
    # Empty, never remove: these are bind-mount roots shared with the other
    # containers, and removing one detaches them from the host directory.
    core_dirs = ['simulation_outputs', 'uploads', 'user_files', 'originals']
    for directory in core_dirs:
        os.makedirs(directory, exist_ok=True)
        clean_dir(directory)

    # 4) Remove stray files in workspace
    for ext in ['*.fmu', '*.exe', '*.zip']:
        for fpath in glob.glob(ext):
            try:
                os.remove(fpath)
            except OSError:
                pass

    # 5) Strip outputs from notebooks or delete if unparsable
    nb_dirs = ['simulation_notebooks', 'surrogate_notebooks']
    for nb_dir in nb_dirs:
        if not os.path.isdir(nb_dir):
            os.makedirs(nb_dir, exist_ok=True)
        for entry in os.listdir(nb_dir):
            full_path = os.path.join(nb_dir, entry)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=True)
            elif entry.endswith('.ipynb'):
                try:
                    nb = read(full_path, as_version=4)
                    for cell in nb.cells:
                        cell.pop('outputs', None)
                        cell.pop('execution_count', None)
                    write(nb, full_path)
                except Exception:
                    os.remove(full_path)
            else:
                try:
                    os.remove(full_path)
                except OSError:
                    pass

    # 5.1) Restore the surrogate notebook template of the active engine (BESOS or
    # bdopt, see engine.py; Agent training now lives in workspace/ai/, provided by
    # the workspace templates below).
    templates_dir = os.path.join(os.getcwd(), 'notebook_templates')
    shutil.copy(inject_data.template_path(surrogate_engine(), templates_dir),
                os.path.join(os.getcwd(), 'surrogate_notebooks/SurrogateNotebook.ipynb'))

    # 7) Field/ (FMUs, parameters.py, points*.yaml): empty the contents, never the
    # directory -- it is a bind mount shared with the gateway containers.
    base = current_app.root_path
    field_dir = os.path.join(base, 'field')
    os.makedirs(field_dir, exist_ok=True)
    clean_dir(field_dir)

    # 8) Workspace/: wipe (keeping the teacher's .emergency flag), then restore the
    # student skeletons from notebook_templates/workspace/ and recreate logs/.
    workspace_dir = os.path.join(base, 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    clean_dir(workspace_dir, keep=('.emergency',))
    skeletons = os.path.join(templates_dir, 'workspace')
    if os.path.isdir(skeletons):
        for entry in os.listdir(skeletons):
            src = os.path.join(skeletons, entry)
            dst = os.path.join(workspace_dir, entry)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
    os.makedirs(os.path.join(workspace_dir, 'logs'), exist_ok=True)


@model_editor_bp.route('/reset_session', methods=['DELETE'])
def reset_session():
    import direct_run
    if direct_run.is_active():
        return jsonify({'success': False,
                        'error': 'A direct EnergyPlus run is in progress: wait for it in the Control room.'}), 409
    try:
        # 1) Clear Flask session
        session.clear()

        # 2) Empty the workspace (SQL tables, files, notebooks)
        clear_workspace()

        # 6) Reset InfluxDB databases
        influx_host = 'influxdb'
        influx_port = 8086
        influx_user = os.getenv('INFLUX_USERNAME', 'admin')
        influx_pass = os.getenv('INFLUX_PASSWORD', 'admin123')
        db1 = os.getenv('INFLUX_BUCKET', 'controlled_building')
        db2 = 'base_building'
        db3 = 'direct_building'  # written by direct_run.py
        client_v1 = InfluxDBClientV1(
            host=influx_host,
            port=influx_port,
            username=influx_user,
            password=influx_pass
        )
        for name in (db1, db2, db3):
            client_v1.drop_database(name)
            client_v1.create_database(name)
        client_v1.close()

        # 9) Return success
        return jsonify({'success': True, 'message': 'Session Reset Done.'}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500