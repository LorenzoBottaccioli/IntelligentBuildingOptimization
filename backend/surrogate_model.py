"""Surrogate modelling: the design stage that produces the model everything else uses.

The student picks objectives and design variables here, explores the space, and
applies the design they choose. Applying it writes a new working IDF -- that is
the point of the stage, and the reason it comes first:

    optimise the design  ->  new IDF  ->  monitor  ->  control  ->  optimise operation
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import CORS
import glob
import json
import os

import design_sections
import design_space
import engine
import envelope
import idf_reader
import idf_version
import schedule_model
import thermostats
import idf_session
import window_library
from methods import parse_mdd_file

SIMULATION_OUTPUTS = 'simulation_outputs'

surrogate_modeling_bp = Blueprint('surrogate_modeling', __name__)
CORS(surrogate_modeling_bp)


@surrogate_modeling_bp.route('/get_surrogate_objects', methods=['GET'])
def get_surrogate_objects():
    """The design-related objects, read from the live model.

    This used to query the SQL tables filled once at upload, so it kept showing
    the model as it arrived however much the student had since changed -- the same
    drift that made the Model Editor look empty after an edit.
    """
    if not idf_session.has_model():
        return jsonify({key: [] for key in
                        ('materials', 'constructions', 'fenestration_surfaces',
                         'zone_ventilations', 'lights', 'window_shading_controls')}), 200

    idf = idf_session.get()
    return jsonify({
        'materials': idf_reader.materials(idf),
        'constructions': idf_reader.constructions(idf),
        'fenestration_surfaces': idf_reader.fenestration_surfaces(idf),
        'zone_ventilations': idf_reader.zone_ventilations(idf),
        'lights': idf_reader.lights(idf),
        'window_shading_controls': idf_reader.window_shading_controls(idf),
    }), 200


def _thermostat_schedules(idf):
    """Every ZoneControl:Thermostat with its zones, and every schedule it reaches, read.

    Read by schedule_model, so any schedule kind works and a schedule an EMS
    program overwrites says so. The panel groups zones whose schedules have the
    same structure, so "the same box in every zone" is one choice.
    """
    chain = schedule_model.thermostats(idf)
    names = set()
    for t in chain:
        names.add(t['controlTypeSchedule'].upper())
        for c in t['controls']:
            names.update(n.upper() for n in c['schedules'].values())
    idx = schedule_model._Index(idf)
    over = schedule_model.overrides(idf)
    read = []
    for n in sorted(names):
        s = schedule_model.read(idf, n, idx)
        if s is not None:
            s['overrides'] = over.get(n, [])
            read.append(s)
    return {'thermostats': chain, 'schedules': read}


@surrogate_modeling_bp.route('/design_space', methods=['GET'])
def design_space_options():
    """What can be varied, and what it is worth optimising for.

    Both halves come from this one call so the interface never has to guess:
    the design variables from the model's own objects, the objectives from the
    meters EnergyPlus reported it can produce.

    'engine' is the library the students' notebook is written for ("besos" or
    "bdopt"), so the panel can word the handover to match.
    """
    if not idf_session.has_model():
        return jsonify({'parameters': [], 'structure': [], 'objectives': [],
                        'engine': engine.surrogate_engine()}), 200

    mdd_files = glob.glob(os.path.join(SIMULATION_OUTPUTS, '*.mdd'))
    meters = [m['Meter_Name'] for m in (parse_mdd_file(mdd_files[0]) if mdd_files else [])]

    # The three facility meters are what the control side exports too, so design
    # and operation are judged on the same quantities. Offer them first.
    preferred = [m for m in ('Electricity:Facility', 'DistrictHeating:Facility',
                             'DistrictCooling:Facility', 'NaturalGas:Facility')
                 if m in meters]
    rest = sorted(m for m in meters if m not in preferred)

    idf = idf_session.get()
    original = idf_session.original_path()

    return jsonify({
        'engine': engine.surrogate_engine(),
        'parameters': design_space.catalogue(idf),
        'structure': design_space.structure(idf),
        'sections': [{'id': i, 'label': l, 'description': d}
                     for i, l, d in design_sections.SECTIONS],
        'thermostatSchedules': _thermostat_schedules(idf),
        'schedules': design_sections.schedules(idf),
        'objectives': [{'name': m, 'preferred': m in preferred} for m in preferred + rest],
        'model': {
            'name': os.path.basename(original or idf_session.working_path() or ''),
            'zones': len(idf.idfobjects['ZONE']),
            # Carried here rather than left in the upload response: the panel is
            # where a student decides what to vary, and a model parsed against the
            # wrong IDD gives wrong answers silently -- surfaces stop facing
            # outdoors, and nothing says why.
            'version': idf_version.check(original) if original else None,
            # BESOS 2.1.3 cannot parse the .eso line EnergyPlus writes for an
            # Output:Variable that carries a schedule -- it ends in ",ON" and the
            # reader's pattern stops at the bracket before it. The run succeeds,
            # the evaluator then raises "could not match". Counted here so the
            # handover can say so for the models that have them.
            'scheduledOutputs': sum(1 for o in idf.idfobjects['OUTPUT:VARIABLE']
                                    if (getattr(o, 'Schedule_Name', '') or '').strip()),
        },
    }), 200


@surrogate_modeling_bp.route('/apply_design', methods=['POST'])
def apply_design():
    """Adopt an optimised design: write the values in and keep the resulting model.

    From here on the rest of the platform -- monitoring, FMU export, control --
    works on this model, which is what makes the design stage more than a study.
    """
    try:
        data = request.get_json() or {}
        design = data.get('design') or []
        if not design:
            return jsonify({'error': 'No design values supplied.'}), 400

        applied = idf_session.mutate(lambda idf: design_space.apply(idf, design))

        return jsonify({
            'message': 'Design applied; this is now the working model.',
            'applied': applied,
            'model': os.path.basename(idf_session.working_path() or ''),
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f'apply_design failed: {e}')
        return jsonify({'error': 'Failed to apply the design.', 'details': str(e)}), 500


# Where the problem definition lives. A plain JSON file beside the working model,
# because the student's notebook has to read it: the interface defines the
# problem, the notebook does the sampling, the surrogate and the optimisation.
def _engine_problems():
    """Problems the students' library would hit with this model, reported before a cell is offered.

    bdopt runs the model exactly as it is and refuses one that does not declare the EnergyPlus version of the
    students' image (9.6): it cannot upgrade it there (IDFVersionUpdater is not shipped), and the platform
    does not either, it only reports it (idf_version.py). Showing a cell that is bound to fail would be worse.
    """
    if engine.surrogate_engine() != 'bdopt':
        return []
    path = idf_session.working_path()
    if not path:
        return []
    info = idf_version.check(path)
    return [] if info['ok'] else ['bdopt cannot evaluate this model. ' + (info['message'] or '')]


PROBLEM_FILE = 'problem.json'


def _problem_path():
    working = idf_session.working_path()
    return os.path.join(os.path.dirname(working), PROBLEM_FILE) if working else None


@surrogate_modeling_bp.route('/envelope', methods=['GET'])
def envelope_route():
    """The envelope as a builder sees it, which is the only way it can be varied.

    A bare class list is the wrong handle here: "Material" does not say what the
    material is part of, so thickening an insulant silently thickens the
    partitions it also sits in. Elements say what, and they carry the two
    different levers -- swap the build-up of a window, thicken the layer inside a
    wall.
    """
    if not idf_session.has_model():
        return jsonify({'elements': [], 'handles': []}), 200
    idf = idf_session.get()
    return jsonify({'elements': envelope.elements(idf),
                    'handles': envelope.handles(idf)}), 200


@surrogate_modeling_bp.route('/window_library', methods=['GET', 'POST'])
def window_library_route():
    """The window constructions EnergyPlus ships, and bringing some into the model.

    GET lists them; POST copies the named ones, with their layers, into the
    working model, where they become options for the windows. Nothing already
    in the model is changed: a window keeps its construction until a design
    point assigns another.
    """
    if request.method == 'GET':
        return jsonify({'constructions': window_library.catalogue()}), 200
    if not idf_session.has_model():
        return jsonify({'error': 'No model loaded.'}), 400
    names = (request.get_json() or {}).get('names') or []
    try:
        added = idf_session.mutate(lambda idf: window_library.import_into(idf, names))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'added': added}), 200


@surrogate_modeling_bp.route('/thermostat_edit', methods=['POST'])
def thermostat_edit_route():
    """Change setpoint temperatures, hours or dates in the model itself.

    Separate from the problem definition: this edits the working model, the
    way the Model Editor does, and is undone by Reset Session. Refused, and
    nothing written, if the new hours or dates would fall out of order.
    """
    if not idf_session.has_model():
        return jsonify({'error': 'No model loaded.'}), 400
    changes = (request.get_json() or {}).get('changes') or []
    try:
        n = idf_session.mutate(lambda idf: thermostats.edit(idf, changes))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'written': n}), 200


@surrogate_modeling_bp.route('/thermostat_structure', methods=['POST'])
def thermostat_structure_route():
    """Add a change of hour or of season to setpoint schedules.

    {schedules: [...], hour: 8, days: "feriali"}   splits the day at 08:00
    {schedules: [...], date: 105}                    splits the year after 15 Apr
    The temperature is the same on both sides, so nothing changes until a value
    does. Edits the working model; Reset Session undoes it.
    """
    if not idf_session.has_model():
        return jsonify({'error': 'No model loaded.'}), 400
    data = request.get_json() or {}
    schedules = data.get('schedules') or []
    try:
        if data.get('hour') is not None:
            n = idf_session.mutate(lambda idf: thermostats.add_hour(
                idf, schedules, data.get('days') or '', float(data['hour'])))
        elif data.get('date') is not None:
            n = idf_session.mutate(lambda idf: thermostats.add_season(
                idf, schedules, int(data['date'])))
        else:
            return jsonify({'error': 'A time or a date is needed.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'changed': n}), 200


@surrogate_modeling_bp.route('/zone_independent', methods=['POST'])
def zone_independent_route():
    """Give one zone its own copy of the setpoint schedules it shares.

    Needed to vary that zone's setpoints alone. The model behaves exactly as
    before until a design point changes the copy.
    """
    if not idf_session.has_model():
        return jsonify({'error': 'No model loaded.'}), 400
    zone = (request.get_json() or {}).get('zone') or ''
    try:
        made = idf_session.mutate(lambda idf: thermostats.make_independent(idf, zone))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'made': made}), 200


@surrogate_modeling_bp.route('/problem', methods=['GET', 'POST'])
def problem():
    """Read or write the problem definition: the variables and what they are for.

    This is the handover. The interface owns parameter selection and problem
    definition; everything downstream -- sampling, surrogate, optimisation, and
    adaptive sampling later -- is the student's own code, reading this file.

    Schema 2 (design_space.SCHEMA_VERSION) adds fieldIndex and iddField to
    every variable and target; a file of schema 1 is read as it is.
    """
    path = _problem_path()
    if not path:
        return jsonify({'error': 'No model loaded.'}), 400

    if request.method == 'GET':
        if not os.path.exists(path):
            return jsonify({'variables': [], 'objectives': [], 'defined': False}), 200
        with open(path, encoding='utf-8') as handle:
            saved = json.load(handle)
        # Written for another model: its objects need not exist in this one.
        if saved.get('model') and saved['model'] != os.path.basename(idf_session.working_path() or ''):
            return jsonify({'variables': [], 'objectives': [], 'defined': False,
                            'staleFor': saved['model']}), 200
        return jsonify({**saved, 'defined': True}), 200

    data = request.get_json() or {}
    variables = data.get('variables') or []
    objectives = data.get('objectives') or []

    clean, problems = design_space.validate_problem(
        idf_session.get(), variables, objectives)
    problems = list(problems) + _engine_problems()
    if problems:
        return jsonify({'error': 'The problem cannot be defined like this.',
                        'problems': problems}), 400

    definition = {
        'schemaVersion': design_space.SCHEMA_VERSION,
        'model': os.path.basename(idf_session.working_path() or ''),
        'variables': clean,
        'objectives': [{'name': o.get('name'),
                        'direction': o.get('direction', 'minimize')}
                       for o in objectives],
        'notes': data.get('notes', ''),
    }
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(definition, handle, indent=2)

    return jsonify({'message': 'Problem defined.', 'problem': definition,
                    'cell': design_space.notebook_cell(clean, definition['objectives']),
                    'path': PROBLEM_FILE}), 200


@surrogate_modeling_bp.route('/problem_preview', methods=['POST'])
def problem_preview():
    """Validate a problem without saving it, and return the notebook cell it becomes."""
    if not idf_session.has_model():
        return jsonify({'error': 'No model loaded.'}), 400
    data = request.get_json() or {}
    objectives = data.get('objectives') or []
    clean, problems = design_space.validate_problem(
        idf_session.get(), data.get('variables') or [], objectives)
    # A preview is useful before the problem is complete: missing objectives or
    # variables are not errors yet.
    problems = [p for p in problems if not p.startswith('At least one')] + _engine_problems()
    return jsonify({'problems': problems, 'columns': len(clean),
                    'cell': design_space.notebook_cell(clean, objectives) if clean else ''}), 200
