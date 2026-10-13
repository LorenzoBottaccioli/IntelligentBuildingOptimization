"""Sessions that ship with the platform: seeding into sessions/ and opening the demo on a fresh instance.

Run where the backend runs (Flask, eppy), from the repository root:

    BACKEND_DIR=/app python -m unittest tests.backend.test_seed_sessions

Nothing here touches Docker, InfluxDB or the real workspace: the working directory is a temporary
folder and the opening itself (`_open`) is replaced by a stub.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(HERE, '..', '..', 'backend'))


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        if isinstance(data, (dict, list)):
            json.dump(data, handle)
        else:
            handle.write(data)


class SeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.abspath(BACKEND))
        import sessions
        cls.sessions = sessions

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.seed = os.path.join(self.tmp.name, 'seed_sessions')
        _write(os.path.join(self.seed, 'bdopt-demo', 'meta.json'), {'id': 'bdopt-demo', 'name': 'Demo'})
        _write(os.path.join(self.seed, 'bdopt-demo', 'state', 'uploads', 'test.idf'), 'Version,9.6;')
        # a folder without meta.json and one with a name that is not a session id are not sessions
        _write(os.path.join(self.seed, 'notes', 'readme.txt'), 'x')
        _write(os.path.join(self.seed, 'Bad_Name', 'meta.json'), {'id': 'Bad_Name'})

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_copies_only_real_sessions(self):
        copied = self.sessions.seed_sessions_if_missing(self.seed)
        self.assertEqual(copied, ['bdopt-demo'])
        self.assertTrue(os.path.isfile('sessions/bdopt-demo/state/uploads/test.idf'))
        self.assertFalse(os.path.exists('sessions/Bad_Name'))
        self.assertFalse(os.path.exists('sessions/notes'))
        listed = [m['id'] for m in self.sessions._list_payload()['sessions']]
        self.assertEqual(listed, ['bdopt-demo'])

    def test_never_overwrites(self):
        _write('sessions/bdopt-demo/meta.json', {'id': 'bdopt-demo', 'name': 'Edited by the teacher'})
        self.assertEqual(self.sessions.seed_sessions_if_missing(self.seed), [])
        with open('sessions/bdopt-demo/meta.json', encoding='utf-8') as handle:
            self.assertEqual(json.load(handle)['name'], 'Edited by the teacher')

    def test_a_deleted_seed_does_not_come_back(self):
        self.sessions.seed_sessions_if_missing(self.seed)
        import shutil
        shutil.rmtree('sessions/bdopt-demo')
        self.assertEqual(self.sessions.seed_sessions_if_missing(self.seed), [])
        self.assertFalse(os.path.exists('sessions/bdopt-demo'))

    def test_no_seed_folder(self):
        self.assertEqual(self.sessions.seed_sessions_if_missing(os.path.join(self.tmp.name, 'absent')), [])

    def test_demo_opens_only_on_a_fresh_instance(self):
        self.sessions.seed_sessions_if_missing(self.seed)
        with mock.patch.object(self.sessions, '_open', return_value=[]) as opened, \
                mock.patch.object(self.sessions, '_stores_for_demo', return_value=False), \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value=None):
            warnings = self.sessions.open_demo_if_empty()
            opened.assert_called_once_with('bdopt-demo', check_building=False, restore_stores=False)
            # the demo opened without its data: the log says why
            self.assertEqual(len(warnings), 1)
            self.assertIn('InfluxDB and Grafana', warnings[0])

    def test_only_the_demo_opens_by_itself(self):
        # the Lab is shipped too, and it is the newest and the first of the menu: it is still never the one that opens
        _write(os.path.join(self.seed, 'lab', 'meta.json'), {'id': 'lab', 'name': 'Lab', 'saved': '2099-01-01T00:00:00+00:00'})
        _write(os.path.join(self.seed, 'lab', 'state', 'uploads', 'x.txt'), 'x')
        self.assertEqual(sorted(self.sessions.seed_sessions_if_missing(self.seed)), ['bdopt-demo', 'lab'])
        listed = [m['id'] for m in self.sessions._list_payload()['sessions']]
        self.assertEqual(listed[0], 'lab')                      # the menu lists the most recently saved first
        with mock.patch.object(self.sessions, '_open', return_value=[]) as opened, \
                mock.patch.object(self.sessions, '_stores_for_demo', return_value=True), \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value=None):
            self.sessions.open_demo_if_empty()
            opened.assert_called_once_with('bdopt-demo', check_building=False, restore_stores=True)
        self.assertIsNone(self.sessions._current_id())          # _open is a stub here: nothing else set a current session

    def test_demo_brings_its_data_when_the_stores_are_empty(self):
        self.sessions.seed_sessions_if_missing(self.seed)
        with mock.patch.object(self.sessions, '_open', return_value=[]) as opened, \
                mock.patch.object(self.sessions, '_stores_for_demo', return_value=True), \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value=None):
            self.sessions.open_demo_if_empty()
            opened.assert_called_once_with('bdopt-demo', check_building=False, restore_stores=True)

    def test_stores_for_demo(self):
        stores = self.sessions.session_stores
        with mock.patch.object(stores, 'ready', return_value=True), mock.patch.object(stores, 'pristine', return_value=True):
            self.assertTrue(self.sessions._stores_for_demo(wait=0))
        # something of somebody's in them: never dropped
        with mock.patch.object(stores, 'ready', return_value=True), mock.patch.object(stores, 'pristine', return_value=False):
            self.assertFalse(self.sessions._stores_for_demo(wait=0))
        # they do not answer in time: the demo opens without them, as before
        with mock.patch.object(stores, 'ready', return_value=False), \
                mock.patch.object(stores, 'pristine', side_effect=AssertionError('not asked when they are down')):
            self.assertFalse(self.sessions._stores_for_demo(wait=0))

    def test_stores_are_waited_for(self):
        stores = self.sessions.session_stores
        answers = iter([False, False, True])
        with mock.patch.object(stores, 'ready', side_effect=lambda: next(answers)), \
                mock.patch.object(stores, 'pristine', return_value=True), \
                mock.patch.object(self.sessions.time, 'sleep'):
            self.assertTrue(self.sessions._stores_for_demo(wait=30))

    def test_the_plan_travels_with_the_session(self):
        # openHAB's plan page and Home Assistant's picture-elements read these files
        targets = self.sessions.HMI_TARGETS
        self.assertIn('www/floorplan/*.svg', targets['homeassistant']['globs'])
        self.assertEqual(targets['openhab_plan']['globs'], ['html/floorplan/*.svg'])
        for rel, target, name in (('www/floorplan/west_ok.svg', dict(targets['homeassistant']), 'homeassistant'),
                                  ('html/floorplan/plan.svg', dict(targets['openhab_plan']), 'openhab_plan')):
            target['live'] = os.path.join(self.tmp.name, 'live_' + name)
            _write(os.path.join(target['live'], rel), '<svg/>')
            _write(os.path.join(target['live'], 'other.svg'), '<svg/>')           # not part of the session
            self.assertEqual(sorted(self.sessions._hmi_live_files(target)), [rel])

    def test_the_session_files_win_over_the_defaults(self):
        state = os.path.join(self.tmp.name, 'state')
        _write(os.path.join(state, 'hmi', 'openhab_plan', 'html', 'floorplan', 'plan.svg'), '<svg id="mine"/>')
        wanted = self.sessions._hmi_wanted(self.sessions.HMI_TARGETS['openhab_plan'], 'openhab_plan', state)
        self.assertEqual(wanted, {'html/floorplan/plan.svg': b'<svg id="mine"/>'})
        self.assertEqual(self.sessions._hmi_wanted(self.sessions.HMI_TARGETS['openhab_plan'], 'openhab_plan', None), {})

    def test_demo_does_not_open_with_a_model_loaded(self):
        self.sessions.seed_sessions_if_missing(self.seed)
        with mock.patch.object(self.sessions, '_open') as opened, \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value='uploads/mine.idf'):
            self.assertIsNone(self.sessions.open_demo_if_empty())
            opened.assert_not_called()

    def test_demo_does_not_open_over_a_current_session(self):
        self.sessions.seed_sessions_if_missing(self.seed)
        _write('sessions/other/meta.json', {'id': 'other', 'name': 'Other'})
        _write('sessions/current.json', {'id': 'other'})
        with mock.patch.object(self.sessions, '_open') as opened, \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value=None):
            self.assertIsNone(self.sessions.open_demo_if_empty())
            opened.assert_not_called()

    def test_no_demo_no_open(self):
        with mock.patch.object(self.sessions, '_open') as opened, \
                mock.patch.object(self.sessions.idf_session, 'working_path', return_value=None):
            self.assertIsNone(self.sessions.open_demo_if_empty())
            opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
