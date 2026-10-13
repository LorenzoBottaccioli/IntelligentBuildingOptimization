"""The weather summary of the Control room: from the text of the EPW, no EnergyPlus needed.

    python -m unittest tests.backend.test_weather_info
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'backend'))
import direct_run  # noqa: E402
import weather_info  # noqa: E402


def epw(path, years, city='TORINO'):
    head = ['LOCATION,%s,-,ITA,IWEC Data,160590,45.22,7.65,1.0,287.0' % city] + ['X'] * 6 + ['DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31']
    rows = ['%d,1,1,%d,60,rest' % (years[i % len(years)], i % 24 + 1) for i in range(48)]
    with open(path, 'w') as handle:
        handle.write('\n'.join(head + rows) + '\n')


class WeatherInfoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_file(self):
        self.assertEqual(weather_info.info(self.tmp), {})

    def test_a_real_year_and_a_typical_year(self):
        epw(os.path.join(self.tmp, 'a_2022_openmeteo.epw'), [2022])
        got = weather_info.info(self.tmp)
        self.assertEqual((got['kind'], got['years'], got['city'], got['country']), ('real', [2022], 'TORINO', 'ITA'))
        self.assertEqual((got['latitude'], got['longitude'], got['hours']), (45.22, 7.65, 48))
        time.sleep(0.05)
        epw(os.path.join(self.tmp, 'a_2022_openmeteo.epw'), [1986, 1992, 1999], city='MILANO')   # replaced: not served from cache
        os.utime(os.path.join(self.tmp, 'a_2022_openmeteo.epw'), (time.time() + 5, time.time() + 5))
        got = weather_info.info(self.tmp)
        self.assertEqual((got['kind'], got['years'], got['city']), ('typical', [1986, 1992, 1999], 'MILANO'))

    def test_the_session_holds_one_the_first_by_name(self):
        epw(os.path.join(self.tmp, 'b.epw'), [2020])
        epw(os.path.join(self.tmp, 'a.epw'), [2021])
        got = weather_info.info(self.tmp)
        self.assertEqual((got['file'], got['others']), ('a.epw', 1))


class EntryTest(unittest.TestCase):
    def test_the_file_list_keeps_kind_and_adds_the_years(self):
        sys.path.insert(0, os.path.join(HERE, '..', '..', 'backend'))
        try:
            import weather_editor
        except ImportError as exc:       # Flask, pyepw: where the backend runs
            self.skipTest(str(exc))
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'w.epw')
            epw(path, [2022])
            e = weather_editor._entry(path, 'lib:w.epw', 'library')
            self.assertEqual((e['kind'], e['years'], e['yearKind']), ('library', [2022], 'real'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class StoredYearTest(unittest.TestCase):
    """The year of the dates in InfluxDB follows the weather: a real year is that year, a typical one is site.year."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.field = os.path.join(self.tmp, 'field')
        os.makedirs(self.field)
        with open(os.path.join(self.field, 'points.yaml'), 'w') as handle:
            handle.write('site: {name: "x", year: 2031}' + chr(10))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_real_year_wins_over_site_year(self):
        epw(os.path.join(self.tmp, 'w.epw'), [2022])
        self.assertEqual(direct_run.stamp_year(self.field, self.tmp), (2022, 'weather'))

    def test_typical_year_and_no_file_use_site_year(self):
        self.assertEqual(direct_run.stamp_year(self.field, self.tmp), (2031, 'site'))
        epw(os.path.join(self.tmp, 'w.epw'), [1986, 1992])
        self.assertEqual(direct_run.stamp_year(self.field, self.tmp), (2031, 'site'))

    def test_keep_adds_beside_what_is_stored(self):
        calls = []

        class Client:
            def drop_database(self, name): calls.append(('drop', name))
            def create_database(self, name): calls.append(('create', name))
            def write_points(self, batch, **kw): calls.append(('write', len(batch), batch[0]['time']))

        plan = [{'id': 'p', 'type': 'measurement', 'unit': 'C'}]
        series = {'p': [(1, 1, 1, 0, 20.0), (1, 1, 2, 0, 21.0)]}
        real = direct_run._influx_client
        direct_run._influx_client = lambda: Client()
        try:
            direct_run.write_influx(series, plan, 2021)
            self.assertEqual([c[0] for c in calls if c[0] != 'write'], ['drop', 'create'])
            calls.clear()
            self.assertEqual(direct_run.write_influx(series, plan, 2022, keep=True), 2)
            self.assertEqual([c[0] for c in calls if c[0] != 'write'], ['create'])      # nothing dropped
            import datetime
            self.assertEqual(datetime.datetime.utcfromtimestamp(calls[-1][2]).year, 2022)
        finally:
            direct_run._influx_client = real


class QueueTest(unittest.TestCase):
    """Several weather years one after the other: the first replaces unless asked to keep, the rest add; the run ends once."""

    def setUp(self):
        self.calls = []
        self.real = (direct_run._worker, direct_run._set)

        def worker(period, field_dir, prune, keep=False, epw_path=None, final=True):
            self.calls.append((os.path.basename(epw_path), keep, final))
            return self.ok
        direct_run._worker = worker
        direct_run._set = lambda **kw: None
        self.ok = True

    def tearDown(self):
        direct_run._worker, direct_run._set = self.real

    def files(self):
        return [('/x/a_2021.epw', 'a_2021.epw', 2021), ('/x/a_2022.epw', 'a_2022.epw', 2022), ('/x/a_2023.epw', 'a_2023.epw', 2023)]

    def test_first_replaces_the_rest_add_and_only_the_last_closes_the_run(self):
        direct_run._queue({}, 'f', True, False, self.files())
        self.assertEqual(self.calls, [('a_2021.epw', False, False), ('a_2022.epw', True, False), ('a_2023.epw', True, True)])

    def test_keep_from_the_first(self):
        direct_run._queue({}, 'f', True, True, self.files()[:2])
        self.assertEqual(self.calls, [('a_2021.epw', True, False), ('a_2022.epw', True, True)])

    def test_a_failed_year_stops_the_queue(self):
        self.ok = False
        direct_run._queue({}, 'f', True, False, self.files())
        self.assertEqual(len(self.calls), 1)

    def test_stamp_year_of_the_file_the_run_used(self):
        tmp = tempfile.mkdtemp()
        try:
            a, b = os.path.join(tmp, 'a.epw'), os.path.join(tmp, 'b.epw')
            epw(a, [2021])
            epw(b, [1986, 1992])
            self.assertEqual(direct_run.stamp_year(tmp, tmp, epw=a), (2021, 'weather'))
            self.assertEqual(direct_run.stamp_year(tmp, tmp, epw=b)[1], 'site')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
