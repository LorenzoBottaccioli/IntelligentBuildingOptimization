"""The stores a session carries: what is new in session_stores.py (a new instance's stores, Grafana's home dashboard).

Run where the backend runs (requests is needed), from the repository root:

    BACKEND_DIR=/app python -m unittest tests.backend.test_session_stores

Nothing here touches Docker, InfluxDB or Grafana: their calls are replaced by stubs.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(HERE, '..', '..', 'backend'))


class FakeGrafana(object):
    """Answers the calls session_stores makes; records the ones that change something."""

    def __init__(self, dashboards=None, home=''):
        self.dashboards = dashboards or {}      # uid -> {'provisioned': bool}
        self.home = home
        self.calls = []

    def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get('json')))
        if path == '/api/user':
            return {}
        if path == '/api/folders':
            return []
        if path == '/api/search':
            return [{'uid': uid, 'title': uid} for uid in self.dashboards]
        if path.startswith('/api/dashboards/uid/'):
            uid = path.rsplit('/', 1)[1]
            if method == 'DELETE':
                self.dashboards.pop(uid)
                return {}
            return {'dashboard': {'uid': uid, 'title': uid},
                    'meta': {'provisioned': self.dashboards[uid]['provisioned'], 'folderUid': ''}}
        if path == '/api/org/preferences':
            if method == 'GET':
                return {'homeDashboardUID': self.home}
            self.home = kwargs['json']['homeDashboardUID']
            return {}
        if path == '/api/dashboards/db':
            dash = kwargs['json']['dashboard']
            self.dashboards[dash['uid']] = {'provisioned': False}
            return {}
        raise AssertionError('unexpected call %s %s' % (method, path))


class StoresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.abspath(BACKEND))
        import session_stores
        cls.stores = session_stores

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    # ---- a new instance

    def test_ready_needs_both(self):
        with mock.patch.object(self.stores, '_influx_query'), mock.patch.object(self.stores, '_check_auth'):
            self.assertTrue(self.stores.ready())
        with mock.patch.object(self.stores, '_influx_query', side_effect=OSError('down')), \
                mock.patch.object(self.stores, '_check_auth'):
            self.assertFalse(self.stores.ready())
        with mock.patch.object(self.stores, '_influx_query'), \
                mock.patch.object(self.stores, '_check_auth', side_effect=OSError('down')):
            self.assertFalse(self.stores.ready())

    def test_empty_stores_are_pristine(self):
        fake = FakeGrafana({'provided': {'provisioned': True}})
        with mock.patch.object(self.stores, '_influx_has_data', return_value=False), \
                mock.patch.object(self.stores, '_grafana', fake):
            self.assertTrue(self.stores.pristine())

    def test_data_or_a_dashboard_of_somebody_is_not_pristine(self):
        fake = FakeGrafana()
        with mock.patch.object(self.stores, '_influx_has_data', side_effect=lambda db: db == 'controlled_building'), \
                mock.patch.object(self.stores, '_grafana', fake):
            self.assertFalse(self.stores.pristine())
        fake = FakeGrafana({'mine': {'provisioned': False}})
        with mock.patch.object(self.stores, '_influx_has_data', return_value=False), \
                mock.patch.object(self.stores, '_grafana', fake):
            self.assertFalse(self.stores.pristine())

    def test_a_store_that_fails_is_not_pristine(self):
        with mock.patch.object(self.stores, '_influx_has_data', side_effect=OSError('down')):
            self.assertFalse(self.stores.pristine())

    # ---- Grafana's home dashboard

    def test_snapshot_keeps_the_home_dashboard(self):
        fake = FakeGrafana({'demo-building': {'provisioned': False}}, home='demo-building')
        with mock.patch.object(self.stores, '_grafana', fake):
            self.assertEqual(self.stores.grafana_snapshot(self.tmp.name), [])
        with open(os.path.join(self.tmp.name, 'grafana', 'preferences.json'), encoding='utf-8') as handle:
            self.assertEqual(json.load(handle), {'homeDashboardUID': 'demo-building'})

    def test_snapshot_ignores_a_home_that_is_not_exported(self):
        # a provisioned dashboard is not exported, so it cannot be the home of a session
        fake = FakeGrafana({'provided': {'provisioned': True}}, home='provided')
        with mock.patch.object(self.stores, '_grafana', fake):
            self.stores.grafana_snapshot(self.tmp.name)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'grafana', 'preferences.json')))

    def _state_with_home(self, uid):
        root = os.path.join(self.tmp.name, 'grafana')
        os.makedirs(os.path.join(root, 'dashboards'))
        with open(os.path.join(root, 'folders.json'), 'w', encoding='utf-8') as handle:
            json.dump([], handle)
        with open(os.path.join(root, 'dashboards', uid + '.json'), 'w', encoding='utf-8') as handle:
            json.dump({'dashboard': {'uid': uid, 'title': uid}, 'folderUid': ''}, handle)
        with open(os.path.join(root, 'preferences.json'), 'w', encoding='utf-8') as handle:
            json.dump({'homeDashboardUID': uid}, handle)

    def test_restore_sets_the_home_dashboard(self):
        self._state_with_home('demo-building')
        fake = FakeGrafana()
        with mock.patch.object(self.stores, '_grafana', fake):
            self.assertEqual(self.stores.grafana_restore(self.tmp.name), [])
        self.assertEqual(fake.home, 'demo-building')
        self.assertIn('demo-building', fake.dashboards)
        # a partial update: the theme and time zone of the organisation are not reset
        self.assertIn(('PATCH', '/api/org/preferences', {'homeDashboardUID': 'demo-building'}), fake.calls)
        self.assertFalse([c for c in fake.calls if c[0] == 'PUT'])

    def test_restore_of_nothing_clears_the_home_dashboard(self):
        fake = FakeGrafana({'old': {'provisioned': False}}, home='old')
        with mock.patch.object(self.stores, '_grafana', fake):
            self.assertEqual(self.stores.grafana_restore(None), [])
        self.assertEqual(fake.home, '')
        self.assertEqual(fake.dashboards, {})

    def test_a_failing_home_is_a_warning_not_an_error(self):
        self._state_with_home('demo-building')
        fake = FakeGrafana()

        def broken(method, path, **kwargs):
            if method == 'PATCH':
                raise OSError('403')
            return fake(method, path, **kwargs)
        with mock.patch.object(self.stores, '_grafana', broken):
            warnings = self.stores.grafana_restore(self.tmp.name)
        self.assertEqual(len(warnings), 1)
        self.assertIn('home dashboard', warnings[0])


if __name__ == '__main__':
    unittest.main()
