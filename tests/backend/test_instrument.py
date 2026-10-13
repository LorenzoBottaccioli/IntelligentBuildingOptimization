"""Sensors & actuators backend: EDD units, zones with geometry, proposed ranges, writes in a block.

From the repository root, with eppy 0.5.63 and Flask installed and EnergyPlus 9.6 on the machine:

    python -m unittest tests.backend.test_instrument

The EDD parser is read out of methods.py without importing the module (it pulls in SQLAlchemy, which the
tests do not need). The zone test runs EnergyPlus once, for design days only, on one of its own examples
(about a second); everything is skipped when the install is not there.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(ROOT, 'backend'))
EPLUS = os.environ.get('EPLUS_DIR', 'C:/EnergyPlusV9-6-0')
IDD = os.path.join(EPLUS, 'Energy+.idd')
EXE = os.path.join(EPLUS, 'energyplus.exe')
EXAMPLE = os.environ.get('EXAMPLE_IDF', os.path.join(EPLUS, 'ExampleFiles', '5ZoneAirCooled.idf'))
DEMO_EDD = os.path.join(BACKEND, 'seed_sessions', 'bdopt-demo', 'state', 'simulation_outputs', 'eplusout.edd')

os.environ.setdefault('IDD_PATH', IDD)
sys.path.insert(0, BACKEND)


def load_function(path, name):
    """A top-level function of a module, compiled on its own."""
    with open(path, encoding='utf-8') as handle:
        tree = ast.parse(handle.read())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), scope)
    return scope[name]


class EddParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parse = staticmethod(load_function(os.path.join(BACKEND, 'methods.py'), 'parse_edd_file'))

    def test_units_and_header(self):
        text = (
            '! <EnergyManagementSystem:Actuator Available>, Component Unique Name, Component Type,  Control Type, Units\n'
            'EnergyManagementSystem:Actuator Available,ZONE A,Zone Temperature Control,Heating Setpoint,[C]\n'
            'EnergyManagementSystem:Actuator Available,ON,Schedule:Compact,Schedule Value,[ ]\n'
            'EnergyManagementSystem:Actuator Available,A, B,Surface,Construction State,[ ]\n'
            'EnergyManagementSystem:Actuator Available,PUMP,Plant Component Pump:VariableSpeed,On/Off Supervisory,[fraction]\n'
            'Some EMS runtime trace line, 1, 2, 3, 4\n'
        )
        with tempfile.NamedTemporaryFile('w', suffix='.edd', delete=False, encoding='latin-1') as handle:
            handle.write(text)
        try:
            rows = self.parse(handle.name)
        finally:
            os.remove(handle.name)
        self.assertEqual([r['Component_Unique_Name'] for r in rows], ['ZONE A', 'ON', 'A, B', 'PUMP'])
        self.assertEqual([r['Units'] for r in rows], ['C', '', '', 'fraction'])
        self.assertEqual(rows[0]['Control_Type'], 'Heating Setpoint')
        self.assertEqual(rows[2]['Component_Type'], 'Surface')

    @unittest.skipUnless(os.path.exists(DEMO_EDD), 'demo EDD not found')
    def test_demo_file(self):
        rows = self.parse(DEMO_EDD)
        self.assertEqual(len(rows), 509)              # the header is no longer counted as an actuator
        self.assertFalse(any(r['Component_Unique_Name'].startswith('!') for r in rows))
        units = {r['Units'] for r in rows}
        self.assertTrue({'C', 'kg/s', 'm3/s', 'W', ''} <= units)
        setpoints = [r for r in rows if r['Component_Type'] == 'Zone Temperature Control']
        self.assertTrue(setpoints and all(r['Units'] == 'C' for r in setpoints))


@unittest.skipUnless(os.path.exists(IDD) and os.path.exists(EXAMPLE), 'EnergyPlus 9.6 or the example not found')
class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from eppy.modeleditor import IDF
        IDF.setiddname(IDD)
        cls.tmp = tempfile.mkdtemp(prefix='instrument_test_')
        cls.idf_path = os.path.join(cls.tmp, 'model.idf')
        shutil.copyfile(EXAMPLE, cls.idf_path)
        cls.IDF = IDF
        cls.idf = IDF(cls.idf_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---- zones ---------------------------------------------------------------------

    @unittest.skipUnless(os.path.exists(EXE), 'energyplus.exe not found')
    def test_zones_geometry_matches_the_vertices(self):
        import instrument
        run = os.path.join(self.tmp, 'run')
        os.makedirs(run)
        probe = self.IDF(self.idf_path)
        probe.newidfobject('OUTPUT:SURFACES:LIST', Report_Type='Details')
        probe.saveas(os.path.join(run, 'in.idf'))
        subprocess.run([EXE, '-D', '-d', run, os.path.join(run, 'in.idf')], cwd=run, capture_output=True, timeout=240)
        eio = os.path.join(run, 'eplusout.eio')
        self.assertTrue(os.path.exists(eio))

        rows = instrument.zones_overview(self.idf, eio=eio)
        self.assertEqual([r['name'] for r in rows], [z.Name for z in self.idf.idfobjects['Zone']])
        self.assertTrue(all(r['geometry'] for r in rows))
        levels = sorted({r['level'] for r in rows})
        self.assertEqual(levels, list(range(len(levels))))     # counted from the lowest floor, no gaps
        self.assertEqual(levels[0], 0)

        # EnergyPlus' floor area against the shoelace sum of the floor polygons in the IDF.
        def floor_area(zone_name):
            total = 0.0
            for s in self.idf.idfobjects['BuildingSurface:Detailed']:
                if s.Zone_Name.upper() != zone_name.upper() or s.Surface_Type.lower() != 'floor':
                    continue
                pts = [(getattr(s, 'Vertex_%d_Xcoordinate' % i), getattr(s, 'Vertex_%d_Ycoordinate' % i))
                       for i in range(1, 100) if getattr(s, 'Vertex_%d_Xcoordinate' % i, '') not in ('', None)]
                total += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2
            return total
        for r in rows:
            self.assertAlmostEqual(r['floorArea'], floor_area(r['name']), delta=0.01 * max(1.0, r['floorArea']))
            for f in r['facings']:
                self.assertIn(f['facing'], 'NESW')
            if r['facings']:
                self.assertEqual(r['mainFacing'], r['facings'][0]['facing'])
        self.assertTrue(any(r['facings'] for r in rows))

    def test_zones_without_a_probe_still_listed(self):
        import instrument
        rows = instrument.zones_overview(self.idf, eio=os.path.join(self.tmp, 'missing.eio'))
        self.assertEqual(len(rows), len(self.idf.idfobjects['Zone']))
        self.assertFalse(any(r['geometry'] for r in rows))

    def test_owners_follow_the_idd_not_the_name(self):
        import instrument
        owners = instrument.owners_of(self.idf)
        zones = {z.Name.upper() for z in self.idf.idfobjects['Zone']}
        for z in zones:
            self.assertEqual([x.upper() for x in owners[z]], [z])
        for s in self.idf.idfobjects['BuildingSurface:Detailed']:
            self.assertEqual(owners[s.Name.upper()], [s.Zone_Name])
        for w in self.idf.idfobjects['FenestrationSurface:Detailed']:
            base = next(s for s in self.idf.idfobjects['BuildingSurface:Detailed']
                        if s.Name.upper() == w.Building_Surface_Name.upper())
            self.assertEqual(owners[w.Name.upper()], [base.Zone_Name])
        # Objects found through the IDD alone: people, lights, equipment, infiltration, thermostats.
        for cls in ('People', 'Lights', 'ElectricEquipment', 'ZoneInfiltration:DesignFlowRate'):
            for o in self.idf.idfobjects[cls]:
                self.assertIn(o.Name.upper(), owners, cls)
                self.assertTrue(set(x.upper() for x in owners[o.Name.upper()]) <= zones)
        self.assertTrue(len(owners) > len(zones) + len(self.idf.idfobjects['BuildingSurface:Detailed']))

    # ---- ranges --------------------------------------------------------------------

    def _ranges(self, items):
        import instrument
        import schedule_model
        schedules = [{'name': s['name'], 'limits': s.get('limits', '')} for s in schedule_model.overview(self.idf)]
        return instrument.suggest_ranges(self.idf, items, schedules, schedule_model.thermostats(self.idf))

    def test_setpoint_range_comes_from_the_thermostat_schedule(self):
        import schedule_model
        t = next(t for t in schedule_model.thermostats(self.idf)
                 if t['zones'] and any(c['schedules'].get('heating') for c in t['controls']))
        zone = t['zones'][0]
        sched = next(c['schedules']['heating'] for c in t['controls'] if c['schedules'].get('heating'))
        limits_name = next(s.get('limits') for s in schedule_model.overview(self.idf) if s['name'].upper() == sched.upper())
        lim = next(o for o in self.idf.idfobjects['ScheduleTypeLimits'] if o.Name.upper() == str(limits_name).upper())
        got = self._ranges([{'component': zone, 'type': 'Zone Temperature Control', 'control': 'Heating Setpoint', 'units': 'C'}])[0]
        low, high = float(lim.Lower_Limit_Value), float(lim.Upper_Limit_Value)
        if high - low > 60:     # -60..200 is true of the schedule and useless as the range of a setpoint
            self.assertEqual(got['source'], 'default')
            self.assertEqual((got['min'], got['max']), (10, 30))
            self.assertIn('too wide', got['note'])
        else:
            self.assertEqual(got['source'], 'model')
            self.assertEqual((got['min'], got['max']), (low, high))

    def test_other_sources_in_order(self):
        got = self._ranges([
            {'component': 'M1', 'type': 'Material', 'control': 'Surface Property Solar Absorptance', 'units': ''},
            {'component': 'P1', 'type': 'People', 'control': 'Number of People', 'units': 'each'},
            {'component': 'F1', 'type': 'Plant Component Pump:VariableSpeed', 'control': 'On/Off Supervisory', 'units': 'fraction'},
            {'component': 'N1', 'type': 'System Node Setpoint', 'control': 'Temperature Setpoint', 'units': 'C'},
            {'component': 'W1', 'type': 'Weather Data', 'control': 'Outdoor Dry Bulb', 'units': 'C'},
        ])
        self.assertEqual([g['source'] for g in got], ['idd', 'idd', 'unit', 'default', 'none'])
        self.assertEqual((got[0]['min'], got[0]['max']), (0.0, 1.0))       # IDD: Solar Absorptance
        self.assertEqual((got[1]['min'], got[1]['max']), (0.0, None))      # IDD: Number of People, no maximum
        self.assertEqual((got[2]['min'], got[2]['max']), (0, 1))           # a fraction
        self.assertEqual((got[3]['min'], got[3]['max']), (10, 30))
        self.assertEqual((got[4]['min'], got[4]['max']), (None, None))     # nothing to say: left to the student

    # ---- writes in a block ---------------------------------------------------------

    def test_batch_is_one_pass_with_an_error_per_item(self):
        import fmu_roles
        import idf_session
        import instrument

        path = os.path.join(self.tmp, 'batch.idf')
        shutil.copyfile(EXAMPLE, path)
        idf = self.IDF(path)
        calls = []

        def mutate(fn):
            calls.append(1)
            result = fn(idf)
            idf.save()
            return result

        saved = {n: getattr(idf_session, n) for n in ('mutate', 'working_path', 'has_model', 'get')}
        idf_session.mutate, idf_session.working_path = mutate, (lambda: path)
        idf_session.has_model, idf_session.get = (lambda: True), (lambda: idf)
        try:
            zones = [z.Name for z in idf.idfobjects['Zone']][:3]
            ops = [{'op': 'variable', 'mode': 'direct', 'indexKey': z, 'variableName': 'Zone Mean Air Temperature',
                    'fmuVariableName': 'T_%d' % i, 'role': 'observation'} for i, z in enumerate(zones)]
            ops.append({'op': 'meter', 'meterName': 'Electricity:Facility', 'name': 'Elec', 'role': 'reward'})
            ops.append({'op': 'actuator', 'mode': 'direct', 'name': 'SP0', 'component': zones[0],
                        'type': 'Zone Temperature Control', 'control': 'Heating Setpoint', 'initial': 20,
                        'min': 10, 'max': 30})
            ops.append({'op': 'actuator', 'name': 'broken'})                        # missing fields
            ops.append({'op': 'variable', 'role': 'boss'})                          # bad role
            ops.append({'op': 'actuator', 'min': 5, 'max': 1})                      # min above max
            results = instrument.run_batch(ops)
            roles = fmu_roles.load()
        finally:
            for n, f in saved.items():
                setattr(idf_session, n, f)

        self.assertEqual(len(calls), 1, 'the whole batch is one pass over the model')
        self.assertEqual([r['ok'] for r in results], [True] * 5 + [False] * 3)
        self.assertTrue(all('error' in r for r in results[5:]))
        reads = {o.FMU_Variable_Name for o in idf.idfobjects['ExternalInterface:FunctionalMockupUnitExport:From:Variable']}
        self.assertTrue({'T_0', 'T_1', 'T_2'} <= reads)
        self.assertEqual(roles['T_0']['role'], 'observation')
        self.assertEqual(roles[results[3]['fmuVariableName']]['role'], 'reward')
        sp = roles[results[4]['fmuVariableName']]
        self.assertEqual((sp['min'], sp['max']), (10, 30))
        # What was written is on disk, once, in a model that still parses.
        again = self.IDF(path)
        self.assertEqual(len(again.idfobjects['ExternalInterface:FunctionalMockupUnitExport:To:Actuator']), 1)


    def test_batch_writes_what_the_single_routes_write(self):
        """The same choices, once through add_* one at a time and once through the batch: the same model."""
        import ems_chain
        import fmu_roles
        import idf_session
        import instrument

        zones = [z.Name for z in self.IDF(EXAMPLE).idfobjects['Zone']][:3]
        ops = [{'op': 'variable', 'mode': 'direct', 'indexKey': z, 'variableName': 'Zone Mean Air Temperature',
                'fmuVariableName': 'T%d' % i, 'role': 'observation'} for i, z in enumerate(zones)]
        ops += [{'op': 'meter', 'meterName': 'Electricity:Facility', 'name': 'Elec', 'role': 'reward'},
                {'op': 'actuator', 'mode': 'direct', 'name': 'SP0', 'component': zones[0], 'type': 'Zone Temperature Control',
                 'control': 'Heating Setpoint', 'initial': 20, 'min': 10, 'max': 30},
                {'op': 'actuator', 'mode': 'program', 'name': 'SP1', 'component': zones[1], 'type': 'Zone Temperature Control',
                 'control': 'Cooling Setpoint', 'initial': 25, 'min': 20, 'max': 30}]

        def run(label, writer):
            path = os.path.join(self.tmp, label + '.idf')
            shutil.copyfile(EXAMPLE, path)
            idf = self.IDF(path)
            saved = {n: getattr(idf_session, n) for n in ('mutate', 'working_path', 'has_model', 'get')}
            idf_session.mutate, idf_session.working_path = (lambda fn: (fn(idf), idf.save())[0]), (lambda: path)
            idf_session.has_model, idf_session.get = (lambda: True), (lambda: idf)
            try:
                writer(idf)
            finally:
                for n, f in saved.items():
                    setattr(idf_session, n, f)
            idf.save()
            with open(path, encoding='latin-1') as handle:
                return handle.read()

        def one_by_one(idf):
            for op in ops:
                idf_session.mutate(lambda i, op=op: instrument.apply_op(i, op))
        single = run('single', one_by_one)
        block = run('block', lambda idf: instrument.run_batch(ops))
        self.assertEqual(single, block)
        self.assertIn('SP1', block)

    # ---- the state of the exported FMU ---------------------------------------------

    def test_fmu_state_counts_what_came_after_the_export(self):
        import fmu_roles
        import fmu_state
        import idf_session
        import instrument

        path = os.path.join(self.tmp, 'state.idf')
        shutil.copyfile(EXAMPLE, path)
        idf = self.IDF(path)
        field = os.path.join(self.tmp, 'field')
        os.makedirs(field)
        saved = {n: getattr(idf_session, n) for n in ('mutate', 'working_path', 'has_model', 'get')}
        idf_session.mutate, idf_session.working_path = (lambda fn: (fn(idf), idf.save())[0]), (lambda: path)
        idf_session.has_model, idf_session.get = (lambda: True), (lambda: idf)
        try:
            zones = [z.Name for z in idf.idfobjects['Zone']][:2]
            self.assertEqual(fmu_state.status(field, idf), {'exported': False})

            instrument.run_batch([{'op': 'variable', 'mode': 'direct', 'indexKey': zones[0], 'variableName': 'Zone Mean Air Temperature',
                                   'fmuVariableName': 'T0', 'role': 'observation'}])
            # What an export records.
            with open(os.path.join(field, 'export_info.json'), 'w') as handle:
                import json
                json.dump({'exported_at': 'now', 'fmu': 'x.fmu', 'timestep': 6, 'interface': fmu_state.interface(idf)}, handle)
            now = fmu_state.status(field, idf)
            self.assertTrue(now['tracked'] and now['upToDate'] and now['changes'] == 0)

            instrument.run_batch([{'op': 'variable', 'mode': 'direct', 'indexKey': zones[1], 'variableName': 'Zone Mean Air Temperature',
                                   'fmuVariableName': 'T1', 'role': 'observation'}])
            fmu_roles.set_entry('T0', role='reward')
            later = fmu_state.status(field, idf)
            self.assertFalse(later['upToDate'])
            self.assertEqual((later['added'], later['changed'], later['removed']), (['T1'], ['T0'], []))
            self.assertEqual(later['changes'], 2)

            # An export from before the tracking existed is told apart from a fresh one.
            with open(os.path.join(field, 'export_info.json'), 'w') as handle:
                json.dump({'exported_at': 'old', 'fmu': 'x.fmu', 'timestep': 6}, handle)
            self.assertEqual(fmu_state.status(field, idf)['tracked'], False)
        finally:
            for n, f in saved.items():
                setattr(idf_session, n, f)

    def test_try_get_does_not_wait_for_a_write(self):
        import threading
        import idf_session
        started, release = threading.Event(), threading.Event()

        def writer():
            with idf_session._lock:
                started.set()
                release.wait(5)
        th = threading.Thread(target=writer)
        th.start()
        started.wait(5)
        try:
            self.assertIsNone(idf_session.try_get())
        finally:
            release.set()
            th.join()


class KitsTest(unittest.TestCase):
    def setUp(self):
        import idf_session
        self.idf_session = idf_session
        self.saved_folder = idf_session.UPLOAD_FOLDER
        self.tmp = tempfile.mkdtemp(prefix='kits_test_')
        idf_session.UPLOAD_FOLDER = self.tmp

    def tearDown(self):
        self.idf_session.UPLOAD_FOLDER = self.saved_folder
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_provided_kits_are_valid_and_always_there(self):
        import instrument_kits as k
        got = k.all_kits()
        self.assertEqual([p['name'] for p in got['provided']], ['Comfort control', 'Energy'])
        self.assertEqual(got['saved'], [])
        for p in k.PROVIDED:      # a provided kit passes the same check as one of the student, under another name
            k.check_kit(dict(p, name='copy of ' + p['name']))

    def test_save_replace_delete_in_the_session_folder(self):
        import instrument_kits as k
        kit = {'name': 'Mine', 'entries': [
            {'tab': 'sensors', 'title': 'Zone Mean Air Temperature', 'where': ['BLOCK1:ZONEWEST'], 'role': 'reward'},
            {'tab': 'actuators', 'title': 'Heating Setpoint', 'type': 'Zone Temperature Control', 'where': 'scope', 'min': 10, 'max': 30}]}
        k.save(kit)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'instrument_kits.json')))
        self.assertEqual([x['name'] for x in k.all_kits()['saved']], ['Mine'])
        k.save(dict(kit, name='mine', description='again'))             # same name, any case: replaced
        self.assertEqual([x['description'] for x in k.all_kits()['saved']], ['again'])
        self.assertEqual(k.all_kits()['saved'][0]['entries'][1]['max'], 30.0)
        k.delete('MINE')
        self.assertEqual(k.all_kits()['saved'], [])

    def test_bad_kits_are_refused_with_a_reason(self):
        import instrument_kits as k
        good = {'tab': 'sensors', 'title': 'X', 'where': 'all'}
        for kit, why in (
            ({'name': '', 'entries': [good]}, 'name'),
            ({'name': 'Energy', 'entries': [good]}, 'platform'),
            ({'name': 'A', 'entries': []}, 'at least one'),
            ({'name': 'A', 'entries': [{'tab': 'pumps', 'title': 'X'}]}, 'tab'),
            ({'name': 'A', 'entries': [dict(good, where='somewhere')]}, 'where'),
            ({'name': 'A', 'entries': [dict(good, min=5, max=1)]}, 'min'),
        ):
            with self.assertRaises(ValueError, msg=why) as ctx:
                k.check_kit(kit)
            self.assertIn(why, str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
