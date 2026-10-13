"""Model editor: IDD schema and the editor API, on an IDF EnergyPlus itself ships.

Run where the backend runs (eppy 0.5.63, Flask), from the repository root:

    IDD_PATH=/app/EnergyPlus-9-6-0/Energy+.idd \
    EXAMPLE_IDF=/path/to/1ZoneUncontrolled_Win_ASH55_Thermal_Comfort.idf \
    python -m unittest tests.backend.test_idf_editor

The files are skipped when the IDD or the example is not there. Nothing here
runs EnergyPlus: that path (Check model) needs the energyplus container.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(HERE, '..', '..', 'backend'))
IDD = os.environ.get('IDD_PATH', 'C:/EnergyPlusV9-6-0/Energy+.idd')
EXAMPLE = os.environ.get('EXAMPLE_IDF', '')


@unittest.skipUnless(os.path.exists(IDD), 'IDD not found')
class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, BACKEND)
        import idd_schema
        cls.schema = idd_schema.load(IDD)

    def test_size(self):
        self.assertEqual(self.schema.version, '9.6.0')
        self.assertEqual(len(self.schema.classes), 826)
        self.assertEqual(len(self.schema.groups), 59)

    def test_people_comfort_slots(self):
        people = self.schema.get('people')
        slots = [f for f in people.fields if f.name.startswith('Thermal Comfort Model')]
        self.assertEqual(len(slots), 7)
        self.assertEqual(slots[0].keys[0], 'Fanger')
        self.assertEqual(people.min_fields, 10)
        self.assertEqual(people.fields[1].object_lists, ['ZoneAndZoneListNames', 'SpaceAndSpaceListNames'])

    def test_unique_and_bounds(self):
        balance = self.schema.get('ZoneAirContaminantBalance')
        self.assertTrue(balance.unique)
        rate = next(f for f in self.schema.get('People').fields if f.name == 'Carbon Dioxide Generation Rate')
        self.assertEqual((rate.units, rate.default, rate.minimum), ('m3/s-W', '3.82E-8', 0.0))

    def test_reference_index(self):
        self.assertIn(('PEOPLE', 0), self.schema.providers['PeopleNames'])
        self.assertGreater(len(self.schema.providers['ScheduleNames']), 3)


@unittest.skipUnless(os.path.exists(IDD) and os.path.exists(EXAMPLE), 'IDD or EXAMPLE_IDF not found')
class EditorCase(unittest.TestCase):
    """A Flask client on a private copy of the example IDF, which idf_session works on."""

    @classmethod
    def setUpClass(cls):
        cls.old = os.getcwd()
        cls.tmp = tempfile.mkdtemp()
        for folder in ('uploads', 'originals'):
            os.makedirs(os.path.join(cls.tmp, folder))
            shutil.copy(EXAMPLE, os.path.join(cls.tmp, folder, 'model.idf'))
        os.chdir(cls.tmp)
        sys.path.insert(0, BACKEND)
        os.environ['IDD_PATH'] = IDD
        import idf_session
        import idf_editor
        from flask import Flask
        idf_session.IDD_PATH = IDD
        idf_editor.IDD_PATH = IDD
        idf_session.invalidate()
        cls.session = idf_session
        app = Flask(__name__)
        app.register_blueprint(idf_editor.idf_editor_bp, url_prefix='/idf_editor')
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        r = self.client.get('/idf_editor' + path)
        self.assertEqual(r.status_code, 200, r.data)
        return r.get_json()

    def send(self, method, path, body, status=200):
        r = getattr(self.client, method)('/idf_editor' + path, json=body)
        self.assertEqual(r.status_code, status, r.data)
        return r.get_json()


class ApiTest(EditorCase):
    def test_comfort_models_replace_all_slots_in_idd_order(self):
        d = self.get('/comfort')
        gen = d['generation']
        out = self.send('post', '/comfort/models', {
            'indexes': [0], 'models': ['ksu', 'FANGER'], 'generation': gen})
        self.assertEqual(out['models'], ['Fanger', 'KSU'])
        person = self.get('/comfort')['people'][0]
        self.assertEqual(person['models'], ['Fanger', 'KSU'])
        self.assertEqual(person['values'][19:26], ['Fanger', 'KSU', '', '', '', '', ''])

    def test_unknown_model_and_stale_generation_are_refused(self):
        self.send('post', '/comfort/models', {'indexes': [0], 'models': ['Bogus']}, 400)
        self.send('post', '/comfort/models', {'indexes': [0], 'models': ['Fanger'], 'generation': -5}, 409)

    def test_co2_balance_created_schedule_and_rename_follows(self):
        gen = self.get('/co2')['generation']
        self.send('post', '/co2/balance', {
            'enabled': True, 'createSchedule': {'name': 'Outdoor CO2 t', 'value': 420}, 'generation': gen})
        state = self.get('/co2')['balance']
        self.assertEqual((state['enabled'], state['schedule']), (True, 'Outdoor CO2 t'))
        sched = next(o for o in self.get('/objects?class=Schedule:Constant')['objects'] if o['label'] == 'Outdoor CO2 t')
        self.assertEqual(sched['values'][2], '420')
        self.send('post', '/object/rename', {
            'class': 'Schedule:Constant', 'index': sched['index'], 'label': 'Outdoor CO2 t', 'newName': 'Outdoor CO2 u'})
        self.assertEqual(self.get('/co2')['balance']['schedule'], 'Outdoor CO2 u')

    def test_unique_class_cannot_be_created_twice(self):
        if not self.get('/co2')['balance']:
            self.send('post', '/co2/balance', {'enabled': False, 'schedule': ''})
        self.send('post', '/object', {'class': 'ZoneAirContaminantBalance', 'values': {'0': 'Yes'}}, 409)

    def test_validation_blocks_type_errors_and_only_warns_on_ranges(self):
        label = self.get('/objects?class=People')['objects'][0]['label']
        self.send('patch', '/object', {'class': 'People', 'index': 0, 'label': label,
                                       'values': {'6': 'abc'}}, 400)
        out = self.send('patch', '/object', {'class': 'People', 'index': 0, 'label': label,
                                             'values': {'10': '9.9e-7'}})
        self.assertTrue(any('above the maximum' in w for w in out['warnings']))
        self.send('patch', '/object', {'class': 'People', 'index': 0, 'label': 'not this one',
                                       'values': {'10': '3e-8'}}, 409)

    def test_every_class_spec_serialises(self):
        for group in self.get('/overview')['groups']:
            for cls in group['classes'][:3]:
                spec = self.get('/class?name=' + cls['name'])
                self.assertEqual(spec['name'], cls['name'])


class OutputsTest(EditorCase):
    """The Outputs tab: report variables and meters, and what reads them.

    The example has 16 Output:Variable (key *) and no meter. Sensors and FMU
    outputs are built the way the platform builds them, with ems_chain.
    """

    def setUp(self):
        # Every test starts from the uploaded model.
        self.session.reset()

    def outputs(self):
        return self.get('/outputs')

    def ref(self, row, kind='variable'):
        out = {'class': row['class'], 'index': row['index'], 'name': row['name']}
        if kind == 'variable':
            out['key'] = row['key']
        return out

    def find(self, rows, name, key=None, frequency=None):
        for row in rows:
            if row['name'] == name and (key is None or row.get('key') == key) \
                    and (frequency is None or row['frequency'].lower() == frequency.lower()):
                return row
        self.fail('{} not among {}'.format(name, [r['name'] for r in rows]))

    def build(self, fn):
        import ems_chain
        self.session.mutate(lambda idf: fn(idf, ems_chain))

    def test_reads_what_the_model_requests(self):
        out = self.outputs()
        self.assertEqual(len(out['variables']), 16)
        self.assertEqual(out['meters'], [])
        first = out['variables'][0]
        self.assertEqual((first['key'], first['name'], first['frequency']),
                         ('*', 'Site Outdoor Air Barometric Pressure', 'Hourly'))
        self.assertFalse(first['locked'])
        self.assertIn('Timestep', out['frequencies']['variable'])
        self.assertEqual(len(out['frequencies']['meter']), len(set(out['frequencies']['meter'])))
        self.assertEqual(out['meterClasses']['0|0'], 'Output:Meter')

    def test_add_variable_and_meter_validate_before_writing(self):
        gen = self.outputs()['generation']
        self.send('post', '/outputs/variable', {'key': 'ZONE ONE', 'name': 'Zone Air Temperature',
                                                'frequency': 'timestep', 'generation': gen})
        row = self.find(self.outputs()['variables'], 'Zone Air Temperature')
        self.assertEqual((row['key'], row['frequency']), ('ZONE ONE', 'Timestep'))
        self.send('post', '/outputs/variable', {'key': 'zone one', 'name': 'zone air temperature',
                                                'frequency': 'Timestep'}, 409)
        self.send('post', '/outputs/variable', {'name': 'Zone Air Temperature', 'frequency': 'fortnightly'}, 400)
        self.send('post', '/outputs/variable', {'name': ' ', 'frequency': 'Hourly'}, 400)
        self.send('post', '/outputs/variable', {'name': 'Zone Air Temperature', 'frequency': 'Hourly',
                                                'generation': -3}, 409)
        out = self.send('post', '/outputs/variable', {'name': 'Zone Air Humidity Ratio', 'frequency': 'Daily',
                                                      'schedule': 'Always On'})
        self.assertTrue(any('BESOS' in w for w in out['warnings']))
        self.assertEqual(self.find(self.outputs()['variables'], 'Zone Air Humidity Ratio')['key'], '*')
        self.send('post', '/outputs/meter', {'name': 'Electricity:Facility', 'frequency': 'Hourly'})
        self.send('post', '/outputs/meter', {'name': 'Electricity:Facility', 'frequency': 'hourly'}, 409)
        meters = self.outputs()['meters']
        self.assertEqual([(m['class'], m['cumulative'], m['fileOnly']) for m in meters],
                         [('Output:Meter', False, False)])

    def test_a_request_without_a_frequency_reports_every_time_step(self):
        self.send('post', '/outputs/variable', {'name': 'Zone Air Temperature'})
        self.send('post', '/outputs/meter', {'name': 'Electricity:Facility'})
        out = self.outputs()
        self.assertEqual(self.find(out['variables'], 'Zone Air Temperature')['frequency'], 'Timestep')
        self.assertEqual(out['meters'][0]['frequency'], 'Timestep')

    def test_meter_options_choose_the_class_and_the_file(self):
        for name, options in (('Cooling:EnergyTransfer', {}), ('Heating:EnergyTransfer', {'fileOnly': True}),
                              ('Electricity:Facility', {'cumulative': True}),
                              ('Gas:Facility', {'cumulative': True, 'fileOnly': True})):
            self.send('post', '/outputs/meter', dict(options, name=name, frequency='Monthly'))
        classes = {m['name']: m['class'] for m in self.outputs()['meters']}
        self.assertEqual(classes, {
            'Cooling:EnergyTransfer': 'Output:Meter',
            'Heating:EnergyTransfer': 'Output:Meter:MeterFileOnly',
            'Electricity:Facility': 'Output:Meter:Cumulative',
            'Gas:Facility': 'Output:Meter:Cumulative:MeterFileOnly'})
        # A meter file only meter is put into the results file (.eso) by making it an Output:Meter.
        row = self.find(self.outputs()['meters'], 'Heating:EnergyTransfer')
        out = self.send('patch', '/outputs/request', {'requests': [self.ref(row, 'meter')],
                                                      'changes': {'fileOnly': False}})
        self.assertEqual(out['changed'], 1)
        classes = {m['name']: (m['class'], m['frequency']) for m in self.outputs()['meters']}
        self.assertEqual(classes['Heating:EnergyTransfer'], ('Output:Meter', 'Monthly'))
        self.assertEqual(len(classes), 4)

    def test_bulk_frequency_and_single_edits(self):
        out = self.outputs()
        rows = [r for r in out['variables'] if r['name'].startswith('Zone Thermal Comfort')]
        self.send('patch', '/outputs/request', {'requests': [self.ref(r) for r in rows],
                                                'changes': {'frequency': 'timestep'}})
        after = [r for r in self.outputs()['variables'] if r['name'].startswith('Zone Thermal Comfort')]
        self.assertEqual({r['frequency'] for r in after}, {'Timestep'})
        self.assertEqual(len(after), len(rows))
        one = after[0]
        self.send('patch', '/outputs/request', {'requests': [self.ref(one)],
                                                'changes': {'key': 'ZONE ONE', 'schedule': 'Always On'}})
        edited = self.find(self.outputs()['variables'], one['name'], key='ZONE ONE')
        self.assertEqual(edited['schedule'], 'Always On')
        self.send('patch', '/outputs/request', {'requests': [self.ref(one)], 'changes': {'cumulative': True}}, 409)
        self.send('patch', '/outputs/request', {'requests': [self.ref(edited)], 'changes': {'cumulative': True}}, 400)
        self.send('patch', '/outputs/request', {'requests': [self.ref(edited)], 'changes': {'frequency': 'never'}}, 400)

    def test_the_last_source_of_a_sensor_chain_is_locked_and_takes_it_on_cascade(self):
        self.build(lambda idf, ems: ems.add_monitored_quantity(
            idf, 'meter', 'Electricity:Facility', 'elec', fmu_variable_name='elec_fmu'))
        self.send('post', '/outputs/meter', {'name': 'Electricity:Facility', 'frequency': 'Hourly'})
        out = self.outputs()
        meters = {(m['name'], m['frequency']): m for m in out['meters']}
        # The chain's own Output:Meter is at Timestep; the hourly one the student added is a second request.
        timestep, hourly = meters[('Electricity:Facility', 'Timestep')], meters[('Electricity:Facility', 'Hourly')]
        for m in (timestep, hourly):
            self.assertEqual([(u['kind'], u['name'], u['fmu']) for u in m['usedBy']],
                             [('platform-sensor', 'elec', ['elec_fmu'])])
            # Another request serves the sensor, so neither is locked.
            self.assertFalse(m['locked'])
            self.assertFalse(m['usedBy'][0]['sole'])
        ems = self.find(out['variables'], 'elec', key='EMS')
        self.assertTrue(ems['platform'])
        self.assertEqual([u['kind'] for u in ems['usedBy']], ['fmu-output'])
        self.assertTrue(ems['locked'])
        # One of two sources can change, never both in the same request.
        both = [self.ref(timestep, 'meter'), self.ref(hourly, 'meter')]
        changed = self.send('patch', '/outputs/request', {'requests': both, 'changes': {'frequency': 'Daily'}})
        self.assertEqual((changed['changed'], len(changed['skipped'])), (1, 1))
        self.assertEqual(sorted(m['frequency'] for m in self.outputs()['meters']), ['Daily', 'Hourly'])
        # The redundant one can go without touching the sensor ...
        hourly = self.find(self.outputs()['meters'], 'Electricity:Facility', frequency='Hourly')
        self.send('delete', '/outputs/request', {'requests': [self.ref(hourly, 'meter')]})
        self.assertEqual(len(self.outputs()['meters']), 1)
        # ... the last source is locked, and takes the chain with it, but only when asked.
        timestep = self.outputs()['meters'][0]
        self.assertTrue(timestep['locked'])
        self.send('patch', '/outputs/request', {'requests': [self.ref(timestep, 'meter')],
                                                'changes': {'frequency': 'Monthly'}}, 409)
        refused = self.send('delete', '/outputs/request', {'requests': [self.ref(timestep, 'meter')]}, 409)
        self.assertTrue(refused['needsCascade'])
        self.assertEqual([d['name'] for d in refused['dependants']], ['elec'])
        done = self.send('delete', '/outputs/request', {'requests': [self.ref(timestep, 'meter')], 'cascade': True})
        self.assertEqual([d['name'] for d in done['cascaded']], ['elec'])
        idf = self.session.get()
        for cls in ('EnergyManagementSystem:Sensor', 'EnergyManagementSystem:OutputVariable',
                    'ExternalInterface:FunctionalMockupUnitExport:From:Variable'):
            self.assertEqual(len(idf.idfobjects[cls.upper()]), 0, cls)
        after = self.outputs()
        self.assertEqual(after['meters'], [])
        self.assertEqual(len(after['variables']), 16)

    def test_removing_every_source_together_needs_the_cascade(self):
        self.build(lambda idf, ems: ems.add_monitored_quantity(
            idf, 'meter', 'Electricity:Facility', 'elec', fmu_variable_name='elec_fmu'))
        self.send('post', '/outputs/meter', {'name': 'Electricity:Facility', 'frequency': 'Hourly'})
        both = [self.ref(m, 'meter') for m in self.outputs()['meters']]
        refused = self.send('delete', '/outputs/request', {'requests': both}, 409)
        self.assertEqual([d['name'] for d in refused['dependants']], ['elec'])
        self.send('delete', '/outputs/request', {'requests': both, 'cascade': True})
        self.assertEqual(self.outputs()['meters'], [])
        self.assertEqual(len(self.session.get().idfobjects['ENERGYMANAGEMENTSYSTEM:SENSOR']), 0)

    def test_fmu_output_on_a_variable_and_a_wildcard_request(self):
        self.build(lambda idf, ems: ems.add_direct_variable(idf, 'ZONE ONE', 'Zone Mean Air Temperature', 'tz'))
        rows = self.outputs()['variables']
        wildcard = self.find(rows, 'Zone Mean Air Temperature', key='*')
        specific = self.find(rows, 'Zone Mean Air Temperature', key='ZONE ONE')
        for row in (wildcard, specific):
            self.assertEqual([u['kind'] for u in row['usedBy']], ['fmu-output'])
        # Another request still serves the FMU output: removing one needs no cascade.
        self.send('delete', '/outputs/request', {'requests': [self.ref(wildcard)]})
        self.assertEqual(len(self.session.get().idfobjects['EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:FROM:VARIABLE']), 1)
        specific = self.find(self.outputs()['variables'], 'Zone Mean Air Temperature', key='ZONE ONE')
        self.assertTrue(specific['usedBy'][0]['sole'])
        refused = self.send('delete', '/outputs/request', {'requests': [self.ref(specific)]}, 409)
        self.assertEqual(refused['dependants'][0]['fmu'], ['tz'])
        self.send('delete', '/outputs/request', {'requests': [self.ref(specific)], 'cascade': True})
        self.assertEqual(len(self.session.get().idfobjects['EXTERNALINTERFACE:FUNCTIONALMOCKUPUNITEXPORT:FROM:VARIABLE']), 0)

    def test_removing_the_ems_request_of_a_chain_removes_the_chain(self):
        self.build(lambda idf, ems: ems.add_monitored_quantity(
            idf, 'variable', 'Zone Air Temperature', 'tair', index_key='ZONE ONE', fmu_variable_name='tair_fmu'))
        ems_row = self.find(self.outputs()['variables'], 'tair', key='EMS')
        self.send('delete', '/outputs/request', {'requests': [self.ref(ems_row)]}, 409)
        self.send('delete', '/outputs/request', {'requests': [self.ref(ems_row)], 'cascade': True})
        idf = self.session.get()
        self.assertEqual(len(idf.idfobjects['ENERGYMANAGEMENTSYSTEM:SENSOR']), 0)
        names = [r['name'] for r in self.outputs()['variables']]
        self.assertNotIn('tair', names)
        # The source request the chain created stays: it was the user's to keep or remove.
        self.assertIn('Zone Air Temperature', names)

    def test_a_models_own_sensor_is_reported_and_left_alone(self):
        self.send('post', '/outputs/variable', {'key': 'ZONE ONE', 'name': 'Zone Air Temperature', 'frequency': 'Timestep'})

        def own_sensor(idf, ems):
            s = idf.newidfobject('EnergyManagementSystem:Sensor')
            s.Name = 'mysensor'
            s.OutputVariable_or_OutputMeter_Index_Key_Name = 'ZONE ONE'
            s.OutputVariable_or_OutputMeter_Name = 'Zone Air Temperature'
        self.build(own_sensor)
        row = self.find(self.outputs()['variables'], 'Zone Air Temperature')
        self.assertEqual([(u['kind'], u['cascade']) for u in row['usedBy']], [('model-sensor', False)])
        out = self.send('delete', '/outputs/request', {'requests': [self.ref(row)]})
        self.assertTrue(any('mysensor' in w for w in out['warnings']))
        self.assertEqual(len(self.session.get().idfobjects['ENERGYMANAGEMENTSYSTEM:SENSOR']), 1)

    def test_stale_references_are_refused(self):
        row = self.outputs()['variables'][0]
        self.send('delete', '/outputs/request', {'requests': [dict(self.ref(row), name='Not this one')]}, 409)
        self.send('delete', '/outputs/request', {'requests': [dict(self.ref(row), index=999)]}, 409)
        self.send('delete', '/outputs/request', {'requests': []}, 400)
        self.send('delete', '/outputs/request', {'requests': [{'class': 'Zone', 'index': 0}]}, 400)

    def test_all_classes_marks_platform_outputs_as_managed(self):
        self.build(lambda idf, ems: ems.add_monitored_quantity(
            idf, 'variable', 'Zone Air Temperature', 'tair', index_key='ZONE ONE'))
        rows = self.get('/objects?class=Output:Variable&q=tair')['objects']
        self.assertEqual([r['managed'] for r in rows], [True])


@unittest.skipUnless(os.path.exists(IDD), 'IDD not found')
class MddUnitsTest(unittest.TestCase):
    def test_meter_units_are_kept(self):
        sys.path.insert(0, BACKEND)
        import methods
        path = os.path.join(tempfile.mkdtemp(), 'x.mdd')
        with open(path, 'w') as handle:
            handle.write('Program Version,EnergyPlus\n'
                         'Var Type (reported time step),Var Report Type,Variable Name [Units]\n'
                         'Zone,Meter,Electricity:Facility [J]\n'
                         'Zone,Meter,Water:Facility [m3]\n'
                         'Zone,Average,Zone Mean Air Temperature [C]\n')
        self.assertEqual(methods.parse_mdd_file(path), [
            {'Var_Type': 'Zone', 'Meter_Name': 'Electricity:Facility', 'Units': 'J'},
            {'Var_Type': 'Zone', 'Meter_Name': 'Water:Facility', 'Units': 'm3'}])
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
