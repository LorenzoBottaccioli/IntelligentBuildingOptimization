"""Tests of the students' "Define the problem" cell: backend/bdopt_cell.py and design_space.notebook_cell.

Two images, two halves. From the repository root:

  Backend image (python 3.9, eppy 0.5.63): the text of both cells, schema 2 of problem.json, the routes.

    docker run --rm --memory=2g -v <repo>:/work:ro -w /work --entrypoint python backend:latest \\
        tests/backend/test_bdopt_cell.py -v

  Students' image (python 3.11, bdopt, EnergyPlus 9.6): the generated cells run against the real models.

    docker run --rm --memory=3g -v <repo>:/work:ro -w /work -e BDOPT_CELL_EXEC=1 \\
        --entrypoint python jupyter:smartbuilding-surrogate tests/backend/test_bdopt_cell.py -v

The default run needs only the standard library (plus eppy for the BESOS half). Switches, all environment variables:

  BDOPT_CELL_MODELS=1   load the real models with eppy and regenerate schema 2 from them (minutes; backend image)
  SWEEP_IDF_LIST=file   one .idf path per line; with SWEEP_DUMP=out.json: dump what eppy says about every field the
                        panel can offer, and about the whole IDD (backend image)
  SWEEP_COMPARE=out.json  compare that dump with bdopt's own IDD parser (students' image)
  BDOPT_CELL_EXEC=1     exec the generated cells on the real models, build problem / evaluator / samples (no EnergyPlus run)
  BDOPT_CELL_EPLUS=1    ... and simulate one week of lab_optimal with and without its Output:Variable (seconds);
  BDOPT_CELL_ANNUAL=1   ... plus two annual runs of the demo problem on E1_RES1, as the cell is written (minutes)
  UPDATE_GOLDEN=1       rewrite the bdopt golden text (the BESOS golden files are frozen and never rewritten)
"""

import ast
import builtins
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO_ROOT') or os.path.abspath(os.path.join(HERE, '..', '..'))
BACKEND = os.path.join(REPO, 'backend')
GOLDEN = os.path.join(HERE, 'golden')
FIXTURES = os.path.join(REPO, 'tests', 'fixtures', 'platform')
sys.path.insert(0, BACKEND)

import bdopt_cell  # noqa: E402  (pure: no bdopt, no eppy)

try:
    import design_space  # noqa: E402  (needs eppy)
except ImportError:  # the students' image has no eppy: the BESOS half is skipped there
    design_space = None

# stem -> files. v1 is the definition as the panel wrote it before schema 2; v2 the same with positions.
CASES = {
    'demo_E1_RES1': dict(
        v1=os.path.join(FIXTURES, 'problem_demo_E1_RES1_multitarget.json'),
        v2=os.path.join(GOLDEN, 'problem_demo_E1_RES1_multitarget.v2.json'),
        model=os.path.join(FIXTURES, 'E1_RES1.idf'),
        epw=os.path.join(REPO, 'tutorials', 'ITA_Torino.160590_IWEC.epw')),
    'lab_optimal': dict(
        v1=os.path.join(FIXTURES, 'problem_lab_optimal_10var.json'),
        v2=os.path.join(GOLDEN, 'problem_lab_optimal_10var.v2.json'),
        model=os.path.join(FIXTURES, 'lab_optimal_mutated.idf'),
        epw=os.path.join(REPO, 'backend', 'uploads', 'my_epw_file.epw')),
    'synthetic_E1_RES1': dict(
        v1=os.path.join(GOLDEN, 'synthetic_E1_RES1.v1.json'),
        v2=os.path.join(GOLDEN, 'synthetic_E1_RES1.v2.json'),
        variables=os.path.join(GOLDEN, 'synthetic_E1_RES1.variables.json'),
        model=os.path.join(FIXTURES, 'E1_RES1.idf'),
        epw=os.path.join(REPO, 'tutorials', 'ITA_Torino.160590_IWEC.epw')),
    'synthetic_Res_flat1': dict(
        v1=os.path.join(GOLDEN, 'synthetic_Res_flat1.v1.json'),
        v2=os.path.join(GOLDEN, 'synthetic_Res_flat1.v2.json'),
        variables=os.path.join(GOLDEN, 'synthetic_Res_flat1.variables.json'),
        model=os.path.join(FIXTURES, 'Res_flat1.idf'),
        epw=os.path.join(REPO, 'tutorials', 'ITA_Torino.160590_IWEC.epw')),
}

# What a schema 2 definition adds to a schema 1 one.
NEW_TOP = ('fieldIndex', 'iddField')
NEW_TARGET = ('fieldIndex', 'iddField', 'iddClass')
NEW_REWRITE = ('constructionIndex', 'constructionField', 'materialIndex', 'materialField')


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def read_text(path):
    """A golden file as text; a checkout that turned LF into CRLF (git autocrlf on Windows) compares equal."""
    with open(path, encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')


def strip_schema2(variables):
    out = copy.deepcopy(variables)
    for v in out:
        for k in NEW_TOP:
            v.pop(k, None)
        for t in v.get('targets') or []:
            if isinstance(t, dict):
                for k in NEW_TARGET:
                    t.pop(k, None)
        for r in v.get('shading') or []:
            for k in NEW_REWRITE:
                r.pop(k, None)
    return out


def cell_of(definition, module=bdopt_cell):
    return module.notebook_cell(definition['variables'], definition['objectives'])


def free_names(source):
    """Names a cell reads without defining them (builtins excluded)."""
    stored, loaded = set(), set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            (loaded if isinstance(node.ctx, ast.Load) else stored).add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                stored.add((a.asname or a.name).split('.')[0])
    return loaded - stored - set(dir(builtins))


def bdopt_imports(source):
    """The names a cell imports from bdopt (not bdopt.sampling)."""
    node = [n for n in ast.parse(source).body if isinstance(n, ast.ImportFrom) and n.module == 'bdopt'][0]
    return {a.name for a in node.names}


def top_level_targets(source):
    """Names assigned at the top level of the cell, in order."""
    out = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            out += [t.id for t in node.targets if isinstance(t, ast.Name)]
    return out


def check_golden(test, name, text):
    path = os.path.join(GOLDEN, name)
    if os.environ.get('UPDATE_GOLDEN') == '1' and name.startswith('bdopt_'):
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    test.assertEqual(read_text(path), text, name + ' differs from the golden text')


# ============================================================================================================
# 1. The BESOS cell did not move
# ============================================================================================================

@unittest.skipIf(design_space is None, 'needs the backend image (eppy)')
class BesosCellIsFrozen(unittest.TestCase):
    """design_space.notebook_cell with engine "besos" gives, byte for byte, what it gave before this work.

    The golden files besos_*.py.txt are the output of the ORIGINAL design_space.py -- the file of git HEAD before
    this work: sha256 bb25ace86d04... as committed (LF), 843428920930... as checked out on Windows (CRLF) -- run
    on the two fixtures (schema 1) and on two synthetic problems. They were checked to be byte for byte what the
    modified module gives for the same definitions in schema 1 and in schema 2, and are never rewritten."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        os.environ['SURROGATE_ENGINE'] = 'besos'

    def tearDown(self):
        self.env.stop()

    def golden(self, stem):
        return read_text(os.path.join(GOLDEN, 'besos_%s.py.txt' % stem))

    def test_both_fixtures_schema_1(self):
        for stem in ('demo_E1_RES1', 'lab_optimal'):
            d = read_json(CASES[stem]['v1'])
            self.assertEqual(cell_of(d, design_space), self.golden(stem), stem)

    def test_both_fixtures_schema_2(self):
        for stem in ('demo_E1_RES1', 'lab_optimal'):
            d = read_json(CASES[stem]['v2'])
            self.assertEqual(cell_of(d, design_space), self.golden(stem), stem)

    def test_synthetic_every_source_kind(self):
        kinds = set()
        for stem in ('synthetic_E1_RES1', 'synthetic_Res_flat1'):
            for version in ('v1', 'v2'):
                d = read_json(CASES[stem][version])
                kinds |= {v.get('source', {}).get('kind') for v in d['variables']}
                self.assertEqual(cell_of(d, design_space), self.golden(stem), stem + ' ' + version)
        self.assertEqual(kinds, {'field', 'layer', 'construction', 'setpoint', 'schedule_value', 'schedule_time'})

    def test_besos_is_still_selectable(self):
        d = read_json(CASES['demo_E1_RES1']['v2'])
        for value in ('besos', 'BESOS'):
            with mock.patch.dict(os.environ, {'SURROGATE_ENGINE': value}):
                self.assertEqual(cell_of(d, design_space), self.golden('demo_E1_RES1'), repr(value))

    def test_the_default_engine_is_bdopt(self):
        d = read_json(CASES['demo_E1_RES1']['v2'])
        for value in (None, '', 'nonsense'):
            env = {k: v for k, v in os.environ.items() if k != 'SURROGATE_ENGINE'}
            if value is not None:
                env['SURROGATE_ENGINE'] = value
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(cell_of(d, design_space), cell_of(d, bdopt_cell), repr(value))

    def test_bdopt_engine_switches_the_cell(self):
        d = read_json(CASES['demo_E1_RES1']['v2'])
        with mock.patch.dict(os.environ, {'SURROGATE_ENGINE': 'bdopt'}):
            text = cell_of(d, design_space)
        self.assertEqual(text, cell_of(d, bdopt_cell))
        self.assertNotIn('besos', text.lower())


# ============================================================================================================
# 2. The bdopt cell
# ============================================================================================================

class BdoptCellGolden(unittest.TestCase):
    """The text of the bdopt cell for the two fixtures and for the synthetic problems (every source kind)."""

    def test_golden_text(self):
        for stem, files in CASES.items():
            with self.subTest(stem):
                check_golden(self, 'bdopt_%s.py.txt' % stem, cell_of(read_json(files['v2'])))

    def test_a_definition_of_schema_1_gives_the_same_cell(self):
        # The fallback (eppy name -> IDD name, Field_N -> position N + 1) must agree with the positions of schema 2.
        for stem, files in CASES.items():
            with self.subTest(stem):
                self.assertEqual(cell_of(read_json(files['v1'])), cell_of(read_json(files['v2'])))

    def test_python_39_syntax_and_names(self):
        for stem, files in CASES.items():
            with self.subTest(stem):
                text = cell_of(read_json(files['v2']))
                compile(text, stem, 'exec')
                self.assertEqual(free_names(text), {'idf', 'epw_file'})
                order = [n for n in top_level_targets(text) if n in ('parameters', 'problem', 'evaluator', 'samples')]
                self.assertEqual(order, ['parameters', 'problem', 'evaluator', 'samples'])

    def test_every_variable_is_one_parameter(self):
        for stem, files in CASES.items():
            with self.subTest(stem):
                d = read_json(files['v2'])
                text = cell_of(d)
                self.assertEqual(text.count('parameters.append(Parameter('), len(d['variables']))
                for v in d['variables']:
                    self.assertIn('name=' + json.dumps(v['name'], ensure_ascii=False), text)

    def test_nothing_of_besos(self):
        for stem, files in CASES.items():
            text = cell_of(read_json(files['v2']))
            for word in ('besos', 'EPProblem', 'value_descriptors', 'dist_sampler', "'minimize'", 'building.getobject'):
                self.assertNotIn(word, text, stem)

    def test_the_module_imports_nothing_it_should_not(self):
        with open(os.path.join(BACKEND, 'bdopt_cell.py'), encoding='utf-8') as f:
            tree = ast.parse(f.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or '').split('.')[0])
        self.assertEqual(imported, {'json', 're', 'textwrap'})


def var(name, **kw):
    """A variable of schema 2 for the mapping tests."""
    v = {'name': name, 'type': 'range', 'min': 1, 'max': 2, 'className': 'Lights',
         'field': 'Watts_per_Zone_Floor_Area', 'targets': ['*'], 'fieldIndex': 5,
         'iddField': 'Watts per Zone Floor Area', 'label': name, 'unit': '', 'source': {'kind': 'field'}}
    v.update(kw)
    return v


def cell(*variables, objectives=('Electricity:Facility',)):
    return bdopt_cell.notebook_cell(list(variables), [{'name': o, 'direction': 'minimize'} if isinstance(o, str) else o
                                                      for o in objectives])


class Mapping(unittest.TestCase):

    def test_every_object_of_a_class(self):
        text = cell(var('Lights'))
        self.assertIn('lights_sel = FieldSelector(\n    class_name="Lights",\n    object_name="*",\n'
                      '    field_name="Watts per Zone Floor Area",\n)', text)
        self.assertNotIn('MultiSelector', text)

    def test_one_object(self):
        text = cell(var('Roof', className='Material', field='Thickness', iddField='Thickness', fieldIndex=2,
                        targets=['Wool']))
        self.assertIn('object_name="Wool"', text)
        self.assertIn('field_name="Thickness"', text)
        self.assertNotIn('MultiSelector', text)

    def test_several_objects_of_one_class_and_field(self):
        text = cell(var('Lights', targets=['A', 'B']))
        self.assertIn('MultiSelector.from_targets(', text)
        self.assertIn('"A", "B",', text)
        self.assertIn('class_name="Lights", field_name="Watts per Zone Floor Area"', text)

    def test_dict_targets_of_one_class_and_field_are_the_same_as_names(self):
        t = [{'object': o, 'field': 'Watts_per_Zone_Floor_Area', 'className': 'Lights', 'fieldIndex': 5,
              'iddField': 'Watts per Zone Floor Area'} for o in ('A', 'B')]
        self.assertEqual(cell(var('Lights', targets=['A', 'B'])), cell(var('Lights', targets=t)))

    def test_a_numbered_field_is_written_by_position_and_says_which(self):
        text = cell(var('Heat', className='Schedule:Compact', field='Field_4', iddField='Field 4', fieldIndex=5,
                        targets=['S1', 'S2']))
        self.assertIn('field_index=5', text)
        self.assertNotIn('field_name="Field 4"', text)
        self.assertIn('field_index=5 is its "Field 4"', text)

    def test_schema_1_guesses_the_names(self):
        v1 = var('Lights')
        del v1['fieldIndex'], v1['iddField']
        self.assertEqual(cell(v1), cell(var('Lights')))
        sched = var('Heat', className='Schedule:Compact', field='Field_4', targets=['S1', 'S2'])
        del sched['fieldIndex'], sched['iddField']
        self.assertIn('field_index=5', cell(sched))
        # only a Schedule:Compact counts its fields from Name, Schedule Type Limits Name
        other = var('X', className='Other', field='Field_4', targets=['S1'])
        del other['fieldIndex'], other['iddField']
        self.assertIn('field_name="Field 4"', cell(other))

    def test_mixed_fields_and_classes_become_a_list_of_mappings(self):
        targets = [
            {'object': 'S1', 'field': 'Field_6', 'className': 'Schedule:Compact', 'fieldIndex': 7, 'iddField': 'Field 6'},
            {'object': 'S2', 'field': 'Field_8', 'className': 'Schedule:Compact', 'fieldIndex': 9, 'iddField': 'Field 8'},
            {'object': 'D', 'field': 'Value_1', 'className': 'Schedule:Day:List', 'fieldIndex': 5, 'iddField': 'Value 1'},
        ]
        text = cell(var('Mixed', className=None, field=None, fieldIndex=None, iddField=None, targets=targets))
        self.assertIn('{"class": "Schedule:Compact", "object": "S1", "field_index": 7}', text)
        self.assertIn('{"class": "Schedule:Compact", "object": "S2", "field_index": 9}', text)
        self.assertIn('{"class": "Schedule:Day:List", "object": "D", "field": "Value 1"}', text)
        self.assertIn('MultiSelector.from_targets([', text)

    def test_the_idd_spelling_of_a_class_wins(self):
        t = {'object': 'S', 'field': 'Field_4', 'className': 'SCHEDULE:COMPACT', 'iddClass': 'Schedule:Compact',
             'fieldIndex': 5, 'iddField': 'Field 4'}
        text = cell(var('Heat', className=None, field=None, fieldIndex=None, iddField=None, targets=[t]))
        self.assertIn('"Schedule:Compact"', text)
        self.assertNotIn('SCHEDULE:COMPACT', text)

    def test_directions(self):
        both = cell(var('Lights'), objectives=[
            {'name': 'Electricity:Facility', 'direction': 'minimize'},
            {'name': 'DistrictHeating:Facility', 'direction': 'maximize'}])
        self.assertIn('    "Electricity:Facility",\n', both)
        self.assertIn('    MeterReader("DistrictHeating:Facility", direction="max"),\n', both)
        self.assertIn('MeterReader', bdopt_imports(both))
        plain = cell(var('Lights'))
        self.assertNotIn('MeterReader', bdopt_imports(plain))
        self.assertNotIn('direction="max"),', plain)
        # objectives may be plain names too
        self.assertEqual(bdopt_cell.notebook_cell([var('Lights')], ['Electricity:Facility']), plain)

    def test_a_category_keeps_its_options_and_the_coding_is_a_comment(self):
        text = cell(var('Glazing', type='category', options=['single', 'double', 'triple'], className='Construction',
                        field='Layer_2', iddField='Layer 2', fieldIndex=3, targets=['W1', 'W2']))
        self.assertIn('CategoryParameter([', text)
        self.assertIn('"single", "double", "triple",', text)
        self.assertRegex(text, r'#\s+1 = single, 2 = double, 3 = triple')
        self.assertNotIn('RangeParameter', text)
        self.assertNotIn('encoding', text)

    def test_numbers_are_short_and_exact(self):
        text = cell(var('A', min=0.1, max=0.30000000000000004), var('B', min=18.0, max=22), var('C', min=1234567.5, max=2e6))
        self.assertIn('RangeParameter(0.1, 0.3)', text)
        self.assertIn('RangeParameter(18, 22)', text)
        self.assertIn('RangeParameter(1234567.5, 2000000)', text)

    def test_names_that_collapse_stay_distinct(self):
        text = cell(var('Lights, all'), var('Lights; all'), var('Lights/all', type='category', options=['a', 'b']))
        for name in ('lights_all_sel', 'lights_all_2_sel', 'lights_all_3_sel', 'lights_all_3_options'):
            self.assertIn(name + ' =', text)
        self.assertEqual(text.count('parameters.append(Parameter('), 3)

    def test_a_variable_without_targets_is_refused(self):
        with self.assertRaises(ValueError):
            cell(var('Lights', targets=[]))

    def test_a_slug_does_not_end_in_an_underscore_before_the_suffix(self):
        text = cell(var('Lights Watts per Zone Floor Area'))  # 28 characters cut it after "floor_"
        self.assertIn('lights_watts_per_zone_floor_sel =', text)
        self.assertNotIn('__sel', text)

    def test_a_name_with_a_line_break_stays_inside_its_comment(self):
        text = cell(var('Lights\nimport os', type='category', options=['a\nb', 'c']))
        compile(text, 'name', 'exec')
        self.assertNotIn('\nimport os', text)
        self.assertIn('# Lights import os\n', text)
        self.assertIn('"Lights\\nimport os"', text)  # the name itself is a string literal: exact
        self.assertRegex(text, r'#\s+1 = a b, 2 = c')

    def test_a_range_must_be_made_of_numbers(self):
        for bad in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                cell(var('Lights', min=1, max=bad))

    def test_imports_are_what_the_cell_uses(self):
        self.assertEqual(bdopt_imports(cell(var('Lights'))),
                         {'EnergyPlusEvaluator', 'FieldSelector', 'Parameter', 'Problem', 'RangeParameter'})
        self.assertEqual(bdopt_imports(cell(var('Lights', targets=['A', 'B']),
                                            var('G', type='category', options=['a', 'b']),
                                            objectives=[{'name': 'X', 'direction': 'maximize'}])),
                         {'EnergyPlusEvaluator', 'Parameter', 'Problem', 'RangeParameter', 'CategoryParameter',
                          'FieldSelector', 'MultiSelector', 'MeterReader'})
        self.assertEqual(bdopt_imports(cell(var('Lights', targets=['A', 'B']))),
                         {'EnergyPlusEvaluator', 'MultiSelector', 'Parameter', 'Problem', 'RangeParameter'})


class Evaluator(unittest.TestCase):
    """How EnergyPlus is run, and what is taken out of the model first."""

    def setUp(self):
        self.text = cell(var('Lights'))

    def test_settings(self):
        self.assertIn('out_dir="/tmp/bdopt_runs"', self.text)
        self.assertIn('err_dir="outputdir"', self.text)
        self.assertIn('processes=2', self.text)
        self.assertIn('samples = lhs(problem, 20)', self.text)
        self.assertIn('from bdopt.sampling import lhs', self.text)

    def test_output_variables_are_dropped_from_a_copy_before_the_evaluator_is_built(self):
        lines = self.text.split('\n')
        copy_at = lines.index('sim_idf = idf.copy()')
        remove_at = lines.index('sim_idf.remove(sim_idf.by_class("Output:Variable"))')
        build_at = next(i for i, l in enumerate(lines) if l.startswith('evaluator = EnergyPlusEvaluator('))
        self.assertTrue(copy_at < remove_at < build_at)
        self.assertIn('problem, sim_idf, epw_file,', self.text)
        self.assertNotIn('idf.remove(', self.text.replace('sim_idf.remove(', ''))  # idf itself is not touched
        comment = '\n'.join(l for l in lines[:copy_at] if l.startswith('#'))
        self.assertIn('Output:Variable', comment)
        self.assertIn('hundreds', comment)

    def test_the_blind_rewrite_is_explicit_and_comes_first(self):
        rewrites = [{'control': '11001', 'material': '20002', 'constructionIndex': 4, 'materialIndex': 10,
                     'constructionField': 'Construction with Shading Name',
                     'materialField': 'Shading Device Material Name'},
                    {'control': '11002', 'material': '20002'}]
        text = cell(var('Glazing', type='category', options=['a', 'b'], shading=rewrites))
        self.assertIn('for control, blind in [', text)
        self.assertIn('("11001", "20002"), ("11002", "20002"),', text)
        self.assertIn('    shading = idf.find("WindowShadingControl", control)[0]', text)
        self.assertIn('    shading.set(10, blind)', text)
        self.assertIn('    shading.set(4, "")', text)
        self.assertIn('field 4 is "Construction with Shading Name", field 10 is "Shading Device Material Name"', text)
        self.assertLess(text.index('shading.set(10, blind)'), text.index('parameters = []'))
        self.assertNotIn('getobject', text)

    def test_the_blind_positions_follow_the_definition(self):
        text = cell(var('G', type='category', options=['a', 'b'], shading=[
            {'control': 'c', 'material': 'm', 'constructionIndex': 7, 'materialIndex': 12}]))
        self.assertIn('shading.set(12, blind)', text)
        self.assertIn('shading.set(7, "")', text)

    def test_without_a_rewrite_there_is_no_block(self):
        self.assertNotIn('WindowShadingControl', self.text)


# ============================================================================================================
# 3. Schema 2 of problem.json, and the routes (backend image)
# ============================================================================================================

@unittest.skipIf(design_space is None, 'needs the backend image (eppy)')
class Schema2Offline(unittest.TestCase):
    """The parts of schema 2 that need no model: the constants and the stored definitions."""

    def test_schema_version(self):
        self.assertEqual(design_space.SCHEMA_VERSION, 2)

    def test_stored_definitions_carry_the_new_keys_and_nothing_else_changed(self):
        for stem, files in CASES.items():
            with self.subTest(stem):
                v1, v2 = read_json(files['v1']), read_json(files['v2'])
                self.assertEqual(v2['schemaVersion'], 2)
                self.assertNotIn('schemaVersion', v1)
                self.assertEqual(strip_schema2(v2['variables']), v1['variables'])
                self.assertEqual(v2['objectives'], v1['objectives'])
                for v in v2['variables']:
                    self.assertIn('fieldIndex', v)
                    self.assertIn('iddField', v)
                    for t in v['targets']:
                        if isinstance(t, dict):
                            self.assertIsInstance(t['fieldIndex'], int)
                            self.assertTrue(t['iddField'])

    def test_field_positions_in_the_stored_definitions(self):
        demo = read_json(CASES['demo_E1_RES1']['v2'])['variables']
        self.assertEqual([(v['fieldIndex'], v['iddField']) for v in demo],
                         [(2, 'Construction Name'), (2, 'Construction Name'), (None, None),
                          (5, 'Watts per Zone Floor Area')])
        self.assertEqual({(t['fieldIndex'], t['iddField']) for t in demo[2]['targets']}, {(5, 'Field 4')})

    def test_a_name_the_idd_file_does_not_give_is_no_name(self):
        """eppy counts on from Value 1 where the file stops; a reader of the file cannot find those names."""
        idd = ('Version,\n  A1 ; \\field Version Identifier\n\n'
               'Schedule:Day:List,\n  A1 , \\field Name\n  A2 , \\field Schedule Type Limits Name\n'
               '  A3 , \\field Interpolate to Timestep\n  N1 , \\field Minutes per Item\n'
               '  N2 , \\field Value 1\n       \\begin-extensible\n\n'
               'Twice,\n  A1 , \\field Name\n  A2 , \\field Same\n  A3 , \\field Same\n  A4 ;\n       \\field Last\n')
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, 'Energy+.idd')
        with open(path, 'w', encoding='latin-1') as f:
            f.write(idd)

        class Fake:
            def __init__(self, key, names):
                self.key = key
                self.fieldnames = ['key'] + names

            def getfieldidd(self, name):
                return {'field': [name.replace('_', ' ')]}

        day_list = Fake('SCHEDULE:DAY:LIST', ['Name', 'Schedule_Type_Limits_Name', 'Interpolate_to_Timestep',
                                              'Minutes_per_Item', 'Value_1', 'Value_2', 'Value_10'])
        twice = Fake('TWICE', ['Name', 'Same', 'Same', 'Last'])
        design_space._IDD_TEXT.clear()
        try:
            with mock.patch.object(design_space.idf_session, 'IDD_PATH', path):
                self.assertEqual(design_space._position(day_list, 'Minutes_per_Item'), (3, 'Minutes per Item'))
                self.assertEqual(design_space._position(day_list, 'Value_1'), (4, 'Value 1'))
                self.assertEqual(design_space._position(day_list, 'Value_2'), (5, None))
                self.assertEqual(design_space._position(day_list, 'Value_10'), (6, None))
                self.assertEqual(design_space._position(twice, 'Name'), (0, 'Name'))
                self.assertEqual(design_space._position(twice, 'Last'), (3, 'Last'))
                self.assertEqual(design_space._idd_text_names()['TWICE'], ['name', 'same', 'same', 'last'])
            # a class the file does not know, or no file at all: eppy's name stands
            with mock.patch.object(design_space.idf_session, 'IDD_PATH', os.path.join(folder, 'missing.idd')):
                design_space._IDD_TEXT.clear()
                self.assertEqual(design_space._position(day_list, 'Value_10'), (6, 'Value 10'))
        finally:
            design_space._IDD_TEXT.clear()

    def test_the_shading_positions_in_the_stored_definition(self):
        v = read_json(CASES['synthetic_Res_flat1']['v2'])['variables'][0]
        for r in v['shading']:
            self.assertEqual((r['constructionIndex'], r['constructionField']), (4, 'Construction with Shading Name'))
            self.assertEqual((r['materialIndex'], r['materialField']), (10, 'Shading Device Material Name'))
        self.assertEqual((bdopt_cell.SHADING_CONSTRUCTION_INDEX, bdopt_cell.SHADING_MATERIAL_INDEX), (4, 10))


def import_surrogate_model():
    """backend/surrogate_model.py, imported from a scratch directory: config.py makes flask_session/ in the cwd."""
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import surrogate_model
        return surrogate_model
    finally:
        os.chdir(cwd)


@unittest.skipIf(design_space is None, 'needs the backend image (eppy)')
class Routes(unittest.TestCase):

    def client(self):
        try:
            import flask
            surrogate_model = import_surrogate_model()
        except ImportError as e:  # pragma: no cover
            self.skipTest('flask / surrogate_model not importable: %s' % e)
        app = flask.Flask(__name__)
        app.register_blueprint(surrogate_model.surrogate_modeling_bp)
        return app.test_client(), surrogate_model

    def test_design_space_reports_the_engine_even_without_a_model(self):
        client, surrogate_model = self.client()
        for value, expected in (('', 'bdopt'), ('besos', 'besos'), ('bdopt', 'bdopt'), ('BDOPT', 'bdopt'), ('x', 'bdopt')):
            with mock.patch.dict(os.environ, {'SURROGATE_ENGINE': value}), \
                    mock.patch.object(surrogate_model.idf_session, 'has_model', return_value=False):
                body = client.get('/design_space').get_json()
            self.assertEqual(body['engine'], expected, value)
            self.assertEqual(body['parameters'], [])

    def test_design_space_reports_the_engine_with_a_model_too(self):
        client, sm = self.client()

        class FakeIdf:  # what the route reads of a model, without the minutes discover() would take
            idfobjects = {'ZONE': [1, 2], 'OUTPUT:VARIABLE': []}

        for value, expected in (('', 'bdopt'), ('besos', 'besos')):
            with mock.patch.dict(os.environ, {'SURROGATE_ENGINE': value}), \
                    mock.patch.object(sm.idf_session, 'has_model', return_value=True), \
                    mock.patch.object(sm.idf_session, 'get', return_value=FakeIdf()), \
                    mock.patch.object(sm.idf_session, 'original_path', return_value=None), \
                    mock.patch.object(sm.design_space, 'catalogue', return_value=[]), \
                    mock.patch.object(sm.design_space, 'structure', return_value=[]), \
                    mock.patch.object(sm.design_sections, 'schedules', return_value=[]), \
                    mock.patch.object(sm, '_thermostat_schedules', return_value=[]):
                body = client.get('/design_space').get_json()
            self.assertEqual(body['engine'], expected, value)
            self.assertEqual(body['model']['zones'], 2)
            self.assertIn('parameters', body)


# ============================================================================================================
# 4. The real models (backend image, slow)
# ============================================================================================================

def _eppy_model(path):
    from eppy.modeleditor import IDF
    IDF.setiddname(os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd'))
    return IDF(path)


@unittest.skipUnless(design_space is not None and os.environ.get('BDOPT_CELL_MODELS') == '1',
                     'set BDOPT_CELL_MODELS=1 in the backend image')
class RealModels(unittest.TestCase):
    """validate_problem on the real models gives the stored schema 2 definitions, and nothing else moved."""

    @classmethod
    def setUpClass(cls):
        cls.idf = {}

    def model(self, stem):
        path = CASES[stem]['model']
        if path not in self.idf:
            self.idf[path] = _eppy_model(path)
        return self.idf[path]

    def test_validate_problem_writes_the_stored_schema_2(self):
        for stem in ('synthetic_E1_RES1', 'synthetic_Res_flat1'):
            with self.subTest(stem):
                raw = read_json(CASES[stem]['variables'])
                clean, problems = design_space.validate_problem(self.model(stem), raw['variables'], raw['objectives'])
                self.assertEqual(problems, [])
                self.assertEqual(clean, read_json(CASES[stem]['v2'])['variables'])
                self.assertEqual(strip_schema2(clean), read_json(CASES[stem]['v1'])['variables'])

    def test_add_positions_upgrades_the_fixtures(self):
        for stem in ('demo_E1_RES1', 'lab_optimal'):
            with self.subTest(stem):
                v1 = read_json(CASES[stem]['v1'])
                self.assertEqual(design_space.add_positions(self.model(stem), v1['variables']),
                                 read_json(CASES[stem]['v2'])['variables'])

    def test_the_input_is_not_modified(self):
        v1 = read_json(CASES['lab_optimal']['v1'])
        before = copy.deepcopy(v1['variables'])
        design_space.add_positions(self.model('lab_optimal'), v1['variables'])
        self.assertEqual(v1['variables'], before)

    def test_the_shading_constants_are_the_idd_positions(self):
        control = self.model('synthetic_Res_flat1').idfobjects['WINDOWSHADINGCONTROL'][0]
        self.assertEqual(design_space._position(control, 'Construction_with_Shading_Name'),
                         (bdopt_cell.SHADING_CONSTRUCTION_INDEX, 'Construction with Shading Name'))
        self.assertEqual(design_space._position(control, 'Shading_Device_Material_Name'),
                         (bdopt_cell.SHADING_MATERIAL_INDEX, 'Shading Device Material Name'))
        # eppy's obj list starts with the class name, so IDF position i is obj[i + 1]
        self.assertEqual(control.obj[bdopt_cell.SHADING_MATERIAL_INDEX + 1], control.Shading_Device_Material_Name)
        self.assertEqual(control.obj[bdopt_cell.SHADING_CONSTRUCTION_INDEX + 1], control.Construction_with_Shading_Name)

    def test_the_problem_route_writes_schema_2_and_the_cell_of_the_engine(self):
        import flask
        import idf_session
        surrogate_model = import_surrogate_model()
        app = flask.Flask(__name__)
        app.register_blueprint(surrogate_model.surrogate_modeling_bp)
        stem = 'synthetic_E1_RES1'
        raw = read_json(CASES[stem]['variables'])
        folder = tempfile.mkdtemp()
        working = os.path.join(folder, 'E1_RES1.idf')
        with open(working, 'w', encoding='utf-8') as f:
            f.write('Version, 9.6;\n')  # the route checks the version the file declares
        for engine_name, first_line in (('besos', 'from besos import sampling'),
                                        ('bdopt', '# Define the problem')):
            with mock.patch.dict(os.environ, {'SURROGATE_ENGINE': engine_name}), \
                    mock.patch.object(idf_session, 'has_model', return_value=True), \
                    mock.patch.object(idf_session, 'working_path', return_value=working), \
                    mock.patch.object(idf_session, 'get', return_value=self.model(stem)):
                client = app.test_client()
                answer = client.post('/problem', json=raw)
                self.assertEqual(answer.status_code, 200, answer.get_data(as_text=True))
                self.assertTrue(answer.get_json()['cell'].startswith(first_line), engine_name)
                preview = client.post('/problem_preview', json=raw).get_json()
                self.assertEqual(preview['problems'], [])
                self.assertTrue(preview['cell'].startswith(first_line), engine_name)
                stored = client.get('/problem').get_json()
        saved = read_json(os.path.join(folder, 'problem.json'))
        self.assertEqual(saved['schemaVersion'], 2)
        self.assertEqual(saved['variables'], read_json(CASES[stem]['v2'])['variables'])
        self.assertEqual(stored['schemaVersion'], 2)
        # a file of schema 1 is still read as it is
        v1 = read_json(CASES[stem]['v1'])
        with open(os.path.join(folder, 'problem.json'), 'w', encoding='utf-8') as f:
            json.dump(v1, f)
        with mock.patch.object(idf_session, 'working_path', return_value=working), \
                mock.patch.object(idf_session, 'has_model', return_value=True):
            old = app.test_client().get('/problem').get_json()
        self.assertTrue(old['defined'])
        self.assertEqual(old['variables'], v1['variables'])
        self.assertNotIn('schemaVersion', old)

    def test_a_model_of_another_version_is_reported_for_bdopt_only(self):
        """bdopt refuses a model that does not declare the EnergyPlus of the students' image (9.6)."""
        import flask
        import idf_session
        surrogate_model = import_surrogate_model()
        app = flask.Flask(__name__)
        app.register_blueprint(surrogate_model.surrogate_modeling_bp)
        stem = 'synthetic_E1_RES1'
        raw = read_json(CASES[stem]['variables'])
        folder = tempfile.mkdtemp()
        working = os.path.join(folder, 'E1_RES1.idf')
        with open(working, 'w', encoding='utf-8') as f:
            f.write('Version, 9.4;\n')
        for engine_name, expected_status in (('bdopt', 400), ('besos', 200)):
            with self.subTest(engine_name),                     mock.patch.dict(os.environ, {'SURROGATE_ENGINE': engine_name}),                     mock.patch.object(idf_session, 'has_model', return_value=True),                     mock.patch.object(idf_session, 'working_path', return_value=working),                     mock.patch.object(idf_session, 'get', return_value=self.model(stem)):
                client = app.test_client()
                answer = client.post('/problem', json=raw)
                self.assertEqual(answer.status_code, expected_status, answer.get_data(as_text=True))
                preview = client.post('/problem_preview', json=raw).get_json()
                if engine_name == 'bdopt':
                    self.assertIn('bdopt cannot evaluate this model', answer.get_json()['problems'][0])
                    self.assertIn('9.4', answer.get_json()['problems'][0])
                    self.assertTrue(any('9.4' in p for p in preview['problems']))
                else:
                    self.assertEqual(preview['problems'], [])


# ============================================================================================================
# 5. Catalogue sweep: does bdopt find the field where eppy says it is?
# ============================================================================================================

def _norm(name):
    return re.sub(r'\s+', ' ', str(name).strip()).lower()


@unittest.skipUnless(design_space is not None and os.environ.get('SWEEP_DUMP') and os.environ.get('SWEEP_IDF_LIST'),
                     'set SWEEP_DUMP and SWEEP_IDF_LIST in the backend image')
class SweepDump(unittest.TestCase):
    """What eppy says: for every field the panel can offer on each model, its position and its IDD name."""

    def test_dump(self):
        from eppy.modeleditor import IDF
        idd_path = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')
        paths = [p.strip() for p in open(os.environ['SWEEP_IDF_LIST'], encoding='utf-8') if p.strip()]
        fields, models = {}, []

        def note(idf, class_name, field, source, model):
            objs = idf.idfobjects.get(class_name.upper()) or []
            if not objs or field not in objs[0].fieldnames:
                return
            index, idd = design_space._position(objs[0], field)
            key = (class_name, field)
            rec = fields.setdefault(key, {'className': class_name, 'field': field, 'fieldIndex': index,
                                          'iddField': idd, 'sources': [], 'models': []})
            assert (rec['fieldIndex'], rec['iddField']) == (index, idd), (key, rec, index, idd)
            if source not in rec['sources']:
                rec['sources'].append(source)
            if model not in rec['models']:
                rec['models'].append(model)

        for path in paths:
            idf = _eppy_model(path)
            model = os.path.basename(os.path.dirname(path)) + '/' + os.path.basename(path)
            catalogue = design_space.catalogue(idf)
            for e in catalogue:  # everything the panel offers as a variable
                note(idf, e['className'], e['field'], 'catalogue', model)
            present = {k for k, v in idf.idfobjects.items() if v}
            for cls in design_space._SCHEDULE_FIELD_CLASSES:  # every box of a schedule
                objs = idf.idfobjects.get(cls) or []
                longest = max((len(o.obj) for o in objs), default=0)
                if objs:
                    for f in objs[0].fieldnames[2:longest]:
                        note(idf, cls, f, 'schedule box', model)
            for cls in present:  # swapping a construction, and the blinds
                objs = idf.idfobjects[cls]
                if 'Construction_Name' in objs[0].fieldnames:
                    note(idf, cls, 'Construction_Name', 'construction swap', model)
            for f in ('Construction_with_Shading_Name', 'Shading_Device_Material_Name'):
                note(idf, 'WINDOWSHADINGCONTROL', f, 'blind rewrite', model)
            with open(path, 'rb') as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            models.append({'model': model, 'sha256': digest, 'catalogue': len(catalogue)})
            print('swept', model, len(catalogue), 'catalogue entries', flush=True)

        # the whole IDD as eppy reads it: class -> field names, in order
        info = getattr(IDF, 'idd_info', None) or idf.idd_info
        idd = {}
        for block in info:
            head = block[0].get('idfobj')
            if head:
                idd[head] = [(f.get('field') or [''])[0] for f in block[1:]]
        import eppy
        with open(idd_path, 'rb') as fh:
            idd_sha = hashlib.sha256(fh.read()).hexdigest()
        out = {'eppy': getattr(eppy, '__version__', '?'), 'idd': idd_path, 'idd_sha256': idd_sha,
               'models': models, 'fields': sorted(fields.values(), key=lambda r: (r['className'], r['field'])),
               'idd_fields': idd}
        with open(os.environ['SWEEP_DUMP'], 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print('%d (class, field) pairs on %d models; %d IDD classes' % (len(fields), len(models), len(idd)))
        self.assertTrue(fields)


@unittest.skipUnless(os.environ.get('SWEEP_COMPARE'), 'set SWEEP_COMPARE=<dump> in the students image')
class SweepCompare(unittest.TestCase):
    """What bdopt says about the same fields; every difference is listed, and must be explained."""

    def test_compare(self):
        from bdopt import EnergyPlus
        from bdopt.eplus.aliases import resolve_class, resolve_field
        eplus = EnergyPlus.find()
        idd = eplus.idd
        dump = read_json(os.environ['SWEEP_COMPARE'])
        report = {'bdopt_idd': str(eplus.idd.path), 'bdopt_idd_version': idd.version}
        with open(str(idd.path), 'rb') as fh:
            report['bdopt_idd_sha256'] = hashlib.sha256(fh.read()).hexdigest()
        report['same_idd_file'] = report['bdopt_idd_sha256'] == dump['idd_sha256']

        def lands_on(target):
            """The position bdopt reaches from what the cell writes for this target (None: it cannot say)."""
            arg, _ = bdopt_cell._field_args(target)
            key, value = arg.split('=', 1)
            if key == 'field_index':
                return int(value)
            try:
                return resolve_field(idd, bdopt_cell._class_of(target), json.loads(value))[1]
            except KeyError:
                return None

        by_class, by_name, by_position, wrong_v2, wrong_v1 = [], [], [], [], []
        for rec in dump['fields']:
            cls_eppy, index, idd_name = rec['className'], rec['fieldIndex'], rec['iddField']
            try:
                cls = resolve_class(idd, cls_eppy)
            except KeyError:
                by_class.append(rec)
                continue
            # the IDD name the definition carries, looked up the way bdopt looks it up
            if idd_name is None:
                by_position.append(rec)
            elif idd.field_index(cls, idd_name) != index:
                by_name.append(dict(rec, bdopt=idd.field_index(cls, idd_name)))
            # what the cell writes for it, from a definition of schema 2 and from one of schema 1
            target = {'object': 'x', 'className': cls_eppy, 'field': rec['field'], 'fieldIndex': index,
                      'iddField': idd_name}
            if lands_on(target) != index:
                wrong_v2.append(dict(rec, bdopt=lands_on(target)))
            old = {'object': 'x', 'className': cls_eppy, 'field': rec['field']}
            if lands_on(old) != index:
                wrong_v1.append(dict(rec, bdopt=lands_on(old)))
        report['pairs'] = len(dump['fields'])
        report['models'] = len(dump['models'])
        report['class_not_found'] = by_class
        report['iddField_is_null_so_written_by_position'] = by_position
        report['iddField_does_not_round_trip'] = by_name
        report['schema2_cell_lands_elsewhere'] = wrong_v2
        report['schema1_cell_lands_elsewhere'] = wrong_v1
        # the whole IDD
        whole = {'classes_eppy': len(dump['idd_fields']), 'class_missing_in_bdopt': [], 'length_differs': [],
                 'name_differs': [], 'first_match_is_not_this_field': 0, 'fields': 0, 'unnamed': 0}
        for cls, names in dump['idd_fields'].items():
            try:
                theirs = idd.fields(cls)
            except KeyError:
                whole['class_missing_in_bdopt'].append(cls)
                continue
            if len(theirs) != len(names):
                whole['length_differs'].append([cls, len(names), len(theirs)])
            for i, (a, b) in enumerate(zip(names, theirs)):
                whole['fields'] += 1
                if _norm(a) != _norm(b):
                    whole['name_differs'].append([cls, i, a, b])
                if not a.strip():
                    whole['unnamed'] += 1
                elif idd.field_index(cls, a) != i:
                    whole['first_match_is_not_this_field'] += 1
        report['whole_idd'] = whole
        out = os.environ['SWEEP_COMPARE'] + '.report.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=1, ensure_ascii=False)
        print(json.dumps({k: (v if not isinstance(v, (list, dict)) else (len(v) if isinstance(v, list) else v))
                          for k, v in report.items()}, indent=1, ensure_ascii=False))
        self.assertTrue(report['same_idd_file'], 'the two sides read different IDD files')
        self.assertEqual(by_class, [], 'classes bdopt does not know')
        self.assertEqual(by_name, [], 'IDD names that do not round-trip')
        self.assertEqual(wrong_v2, [], 'fields the cell of a schema 2 definition would write somewhere else')
        # Written by position only where the IDD file does not name the position: the extensible values
        # of a Schedule:Day:List (Value 2 and on), which eppy counts on to and the file does not list.
        self.assertEqual({(r['className'].upper(), re.sub(r'\d+$', '', r['field'])) for r in by_position},
                         {('SCHEDULE:DAY:LIST', 'Value_')} if by_position else set())
        # Schema 1 has no positions: the cell guesses from eppy's name. Known gaps, all of which fail loudly
        # when the evaluator is created (bdopt: KeyError, with suggestions) and none silently:
        known = {('WindowProperty:FrameAndDivider', 'Ratio_of_DividerEdge_Glass_Conductance_to_CenterOfGlass_Conductance'),
                 ('WindowProperty:FrameAndDivider', 'Ratio_of_FrameEdge_Glass_Conductance_to_CenterOfGlass_Conductance'),
                 ('ZoneHVAC:EquipmentList', 'Zone_Equipment_1_Heating_or_NoLoad_Sequence')}
        unexpected = [r for r in wrong_v1 if (r['className'], r['field']) not in known
                      and not (r['className'].upper() == 'SCHEDULE:DAY:LIST' and r['field'] != 'Value_1')]
        self.assertEqual(unexpected, [], 'schema 1 guesses that are wrong, and not known')
        self.assertTrue(all(r['bdopt'] is None for r in wrong_v1), 'a schema 1 guess that lands on ANOTHER field')


# ============================================================================================================
# 6. The cells run on the real models (students' image)
# ============================================================================================================

def _bdopt_available():
    try:
        import bdopt  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_bdopt_available() and os.environ.get('BDOPT_CELL_EXEC') == '1',
                     'set BDOPT_CELL_EXEC=1 in the students image')
class CellRuns(unittest.TestCase):
    """exec() of the generated cell with idf = load_idf(model): every selector is checked against the real model."""

    STEMS = ('demo_E1_RES1', 'lab_optimal', 'synthetic_E1_RES1', 'synthetic_Res_flat1')

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)  # err_dir="outputdir" is relative

    def tearDown(self):
        os.chdir(self.cwd)

    def run_cell(self, stem, text=None):
        from bdopt import load_idf
        files = CASES[stem]
        d = read_json(files['v2'])
        text = text if text is not None else read_text(os.path.join(GOLDEN, 'bdopt_%s.py.txt' % stem))
        ns = {'idf': load_idf(files['model']), 'epw_file': files['epw']}
        before = len(ns['idf'].by_class('Output:Variable'))
        exec(compile(text, stem, 'exec'), ns)  # noqa: S102
        return d, ns, before

    def expected_targets(self, v, idf):
        """Objects the variable reaches: one object holding two of its fields counts once."""
        t = v['targets']
        if t == ['*']:
            return len(idf.by_class(v['className']))
        return len({((x['className'] if isinstance(x, dict) else v['className']).lower(),
                     (x['object'] if isinstance(x, dict) else x).strip().lower()) for x in t})

    @staticmethod
    def positions_in_the_definition(v):
        """(class, object) -> the positions the definition says are written there ('*': every object of the class)."""
        out = {}
        for t in v['targets']:
            if isinstance(t, dict):
                cls, obj, index = (t.get('iddClass') or t['className']), t['object'], t['fieldIndex']
            else:
                cls, obj, index = (v.get('iddClass') or v['className']), t, v['fieldIndex']
            out.setdefault((cls.lower(), obj.strip().lower()), set()).add(index)
        return out

    def test_every_cell_builds_problem_evaluator_and_samples(self):
        for stem in self.STEMS:
            with self.subTest(stem):
                d, ns, before = self.run_cell(stem)
                problem, evaluator, samples = ns['problem'], ns['evaluator'], ns['samples']
                n = len(d['variables'])
                self.assertEqual(problem.n_var, n)
                self.assertEqual(problem.parameter_names, [v['name'] for v in d['variables']])
                self.assertEqual(problem.objective_names, [o['name'] for o in d['objectives']])
                self.assertEqual([o.direction for o in problem.objectives],
                                 ['max' if o['direction'] == 'maximize' else 'min' for o in d['objectives']])
                self.assertEqual(samples.shape, (20, n))
                self.assertEqual(list(samples.columns), problem.parameter_names)
                # idf keeps the model's own outputs; the simulated copy has none of the variables
                self.assertEqual(len(ns['idf'].by_class('Output:Variable')), before)
                self.assertEqual(len(evaluator.idf.by_class('Output:Variable')), 0)
                self.assertEqual(len(evaluator.idf.by_class('Output:SQLite')), 1)
                for o in problem.objectives:
                    self.assertTrue(any(m.get(0).lower() == o.meter.lower() and m.get(1).lower() == 'runperiod'
                                        for m in evaluator.idf.by_class('Output:Meter')), o.name)
                self.assertEqual(evaluator.processes, 2)
                self.assertEqual(str(evaluator.out_dir), '/tmp/bdopt_runs')
                self.assertEqual(evaluator.err_dir.name, 'outputdir')
                # one parameter, one column, however many objects: count what each one reaches
                idd = evaluator.eplus.idd
                for v, p in zip(d['variables'], problem.parameters):
                    reached = p.selector.targets(evaluator.idf, idd)
                    self.assertEqual(len(reached), self.expected_targets(v, ns['idf']), v['name'])

    def test_a_row_lands_in_every_target(self):
        for stem in self.STEMS:
            with self.subTest(stem):
                d, ns, _ = self.run_cell(stem)
                problem, evaluator = ns['problem'], ns['evaluator']
                idd = evaluator.eplus.idd
                row = ns['samples'].iloc[0].to_dict()
                for v, p in zip(d['variables'], problem.parameters):
                    # one parameter at a time: two variables may write the same field of the same object
                    model = evaluator.idf.copy()
                    want = row[p.name]
                    p.selector.apply(model, want, idd)
                    where = self.positions_in_the_definition(v)
                    for sel in getattr(p.selector, 'selectors', [p.selector]):
                        _, idx = sel._resolve(idd)
                        objs = sel.targets(model, idd)
                        self.assertTrue(objs, (v['name'], sel))
                        for o in objs:
                            # bdopt writes where eppy (the backend) said the field is, not just somewhere
                            expected = where.get((o.class_name.lower(), o.name.strip().lower())) \
                                or where.get((o.class_name.lower(), '*'))
                            self.assertIn(idx, expected, (v['name'], o.class_name, o.name))
                            got = o.get(idx)
                            if v['type'] == 'range':
                                self.assertAlmostEqual(float(got), float(want), places=9, msg=(v['name'], o.name))
                            else:
                                self.assertEqual(got, want, (v['name'], o.name))

    def test_the_blinds_are_rewritten_on_idf_and_idempotently(self):
        d, ns, _ = self.run_cell('synthetic_Res_flat1')
        idf = ns['idf']
        rewrites = d['variables'][0]['shading']
        for r in rewrites:
            control = idf.find('WindowShadingControl', r['control'])[0]
            self.assertEqual(control.get(r['materialIndex']), r['material'])
            self.assertEqual(control.get(r['constructionIndex']), '')
        # the evaluator's copy has it too
        evaluator = ns['evaluator']
        for r in rewrites:
            control = evaluator.idf.find('WindowShadingControl', r['control'])[0]
            self.assertEqual(control.get(r['constructionIndex']), '')
        # run the cell again on the already rewritten model: nothing changes
        text = read_text(os.path.join(GOLDEN, 'bdopt_synthetic_Res_flat1.py.txt'))
        ns2 = {'idf': idf, 'epw_file': CASES['synthetic_Res_flat1']['epw']}
        exec(compile(text, 'again', 'exec'), ns2)  # noqa: S102
        self.assertEqual(ns2['idf'].to_text(), idf.to_text())

    def test_a_typo_is_reported_when_the_evaluator_is_created(self):
        text = read_text(os.path.join(GOLDEN, 'bdopt_demo_E1_RES1.py.txt')).replace('"Lights"', '"Lighs"')
        with self.assertRaises(Exception) as caught:
            self.run_cell('demo_E1_RES1', text)
        self.assertIn('Lighs', str(caught.exception))


@unittest.skipUnless(_bdopt_available() and os.environ.get('BDOPT_CELL_EXEC') == '1'
                     and os.environ.get('BDOPT_CELL_EPLUS') == '1',
                     'set BDOPT_CELL_EXEC=1 and BDOPT_CELL_EPLUS=1 in the students image')
class CellSimulates(unittest.TestCase):
    """EnergyPlus runs of the generated cell: the demo problem on E1_RES1, and what dropping the variables does."""

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(tempfile.mkdtemp())  # err_dir="outputdir" is relative

    def tearDown(self):
        os.chdir(self.cwd)

    def test_two_annual_rows_of_the_demo_problem(self):
        """The cell as written, two rows of its own `samples`, two annual runs (minutes: set BDOPT_CELL_ANNUAL=1)."""
        if os.environ.get('BDOPT_CELL_ANNUAL') != '1':
            self.skipTest('two annual EnergyPlus runs of E1_RES1: set BDOPT_CELL_ANNUAL=1')
        import time
        from bdopt import load_idf
        files = CASES['demo_E1_RES1']
        text = read_text(os.path.join(GOLDEN, 'bdopt_demo_E1_RES1.py.txt'))
        ns = {'idf': load_idf(files['model']), 'epw_file': files['epw']}
        exec(compile(text, 'demo', 'exec'), ns)  # noqa: S102
        rows = ns['samples'].iloc[:2]
        t0 = time.time()
        result = ns['evaluator'].evaluate(rows, keep_input=True)
        print('\n2 annual rows, 2 processes, %d Output:Variable simulated: %.0f s\n%s' % (
            len(ns['evaluator'].idf.by_class('Output:Variable')), time.time() - t0, result.to_string()))
        names = ns['problem'].objective_names
        self.assertEqual(len(ns['evaluator'].failures), 0)
        self.assertFalse(result[names].isna().any().any())
        self.assertTrue((result[names] > 0).all().all())
        # the two rows are different designs and EnergyPlus noticed
        self.assertTrue((result[names].iloc[0] != result[names].iloc[1]).all())
        for rec in ns['evaluator'].history:
            self.assertEqual(rec.eplus_severe, 0, rec.errors)

    def test_dropping_the_output_variables_changes_nothing(self):
        """lab_optimal has an EMS that reads 10 zone temperatures and 41 Output:Variable; one week, both ways."""
        from bdopt import EnergyPlus, EnergyPlusEvaluator, load_idf
        files = CASES['lab_optimal']
        text = read_text(os.path.join(GOLDEN, 'bdopt_lab_optimal.py.txt'))
        idf = load_idf(files['model'])
        idd = EnergyPlus.find().idd
        run = idf.by_class('RunPeriod')[0]  # a week keeps this to seconds; the strip does not depend on the length
        run.set(idd.field_index('RunPeriod', 'End Month'), 1)
        run.set(idd.field_index('RunPeriod', 'End Day of Month'), 7)
        kept = len(idf.by_class('Output:Variable'))
        self.assertGreater(kept, 0)
        ns = {'idf': idf, 'epw_file': files['epw']}
        exec(compile(text, 'lab', 'exec'), ns)  # noqa: S102
        self.assertEqual(len(ns['evaluator'].idf.by_class('Output:Variable')), 0)
        self.assertEqual(len(idf.by_class('Output:Variable')), kept)
        rows = ns['samples'].iloc[:1]
        stripped = ns['evaluator'].evaluate(rows)
        full = EnergyPlusEvaluator(ns['problem'], idf, files['epw'], out_dir='/tmp/bdopt_runs_full',
                                   err_dir='outputdir_full', processes=1)
        self.assertEqual(len(full.idf.by_class('Output:Variable')), kept)
        with_variables = full.evaluate(rows)
        names = ns['problem'].objective_names
        print('\nstripped:\n%s\nwith %d Output:Variable:\n%s' % (stripped.to_string(), kept, with_variables.to_string()))
        self.assertEqual(len(ns['evaluator'].failures) + len(full.failures), 0)
        for name in names:
            self.assertTrue(stripped[name].iloc[0] > 0, name)
            self.assertEqual(stripped[name].iloc[0], with_variables[name].iloc[0], name)


if __name__ == '__main__':
    unittest.main()
