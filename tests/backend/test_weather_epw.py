"""backend/weather_epw.py: build an EPW from Open-Meteo, summarise it, edit it.

Open-Meteo is replaced by a function that answers like the archive (hourly lists keyed by UTC time
stamps), so the mapping to EPW rows is tested without the network. What the real service answers was
checked by hand against archive-api.open-meteo.com (units, the preceding-hour radiation, nulls).

It needs pyepw and requests (the backend image has them). Run it there, mounting the sources read-only:

    MSYS_NO_PATHCONV=1 docker run --rm -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python \
        -v C:/.../backend:/repo/backend:ro -v C:/.../tests/backend:/repo/tests/backend:ro \
        backend:latest -m unittest discover -v -s /repo/tests/backend -p "test_weather_epw.py"

BACKEND_SRC overrides the location of the backend sources (default: ../../backend of this file).
"""

import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('BACKEND_SRC', os.path.join(HERE, '..', '..', 'backend')))

import weather_epw as we  # noqa: E402


def archive_answer(params, overrides=None, drop=None):
    """What the archive returns for `params`: every requested variable, hourly, from start to end date."""
    start = dt.datetime.fromisoformat(params['start_date'])
    end = dt.datetime.fromisoformat(params['end_date']) + dt.timedelta(hours=23)
    times = []
    t = start
    while t <= end:
        times.append(t)
        t += dt.timedelta(hours=1)
    n = len(times)
    hourly = {'time': [t.strftime('%Y-%m-%dT%H:%M') for t in times]}
    for name in we.HOURLY:
        hourly[name] = [0.0] * n
    hourly['temperature_2m'] = [10.0 + 5.0 * ((t.hour % 24) / 24.0) for t in times]
    hourly['relative_humidity_2m'] = [60] * n
    hourly['dew_point_2m'] = [3.0] * n
    hourly['surface_pressure'] = [1000.0] * n
    hourly['cloud_cover'] = [40] * n
    hourly['wind_speed_10m'] = [2.5] * n
    hourly['wind_direction_10m'] = [90] * n
    hourly['shortwave_radiation'] = [100.0 if 8 <= t.hour <= 16 else 0.0 for t in times]
    hourly['direct_normal_irradiance'] = [200.0 if 8 <= t.hour <= 16 else 0.0 for t in times]
    hourly['diffuse_radiation'] = [50.0 if 8 <= t.hour <= 16 else 0.0 for t in times]
    for name, values in (overrides or {}).items():
        hourly[name] = values(times) if callable(values) else values
    for name in drop or []:
        hourly.pop(name, None)
    return {'latitude': 45.1, 'longitude': 7.7, 'elevation': 241.0, 'hourly': hourly}


def build(year=2021, tz='Europe/Rome', **kw):
    answer = kw.pop('answer', archive_answer)
    with mock.patch.object(we, '_fetch', side_effect=lambda p: answer(p)) as fetch:
        epw, report = we.build_from_openmeteo(45.07, 7.69, year, timezone=tz, city='Torino', country='ITA', **kw)
    return epw, report, fetch


class Build(unittest.TestCase):
    def test_rows_and_header(self):
        epw, report, _ = build(2021)
        self.assertEqual(len(epw.weatherdata), 8760)
        self.assertEqual(epw.location.city, 'Torino')
        self.assertEqual(epw.location.timezone, 1)
        self.assertEqual(epw.location.elevation, 241.0)
        self.assertEqual(report['time_zone'], 1)
        first, last = epw.weatherdata[0], epw.weatherdata[-1]
        self.assertEqual((first.year, first.month, first.day, first.hour, first.minute), (2021, 1, 1, 1, 60))
        self.assertEqual((last.month, last.day, last.hour), (12, 31, 24))

    def test_leap_year_drops_29_february(self):
        epw, _, _ = build(2020)
        self.assertEqual(len(epw.weatherdata), 8760)
        self.assertFalse(any(int(r.month) == 2 and int(r.day) == 29 for r in epw.weatherdata))

    def test_comments_survive_the_file(self):
        # A comma would cut a comment short when the file is read back.
        epw, _, _ = build(2021)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.epw')
            we.save(epw, p)
            c = we.summary(we.read(p))['comments']
        self.assertIn('Open-Meteo', c[0])
        self.assertIn('29 February is left out', c[1])

    def test_data_period_starts_on_the_right_weekday(self):
        epw, _, _ = build(2021)
        self.assertEqual(epw.data_periods.data_periods[0].data_period_start_day_of_week, 'Friday')   # 1 Jan 2021

    def test_time_stamps_become_local_standard_time(self):
        # Value = the UTC stamp itself (hours since 2020-12-31), so each EPW row shows which stamp it took.
        def hours_since(times):
            base = dt.datetime(2020, 12, 31)
            return [(t - base).total_seconds() / 3600.0 / 100.0 for t in times]

        def answer(p):
            return archive_answer(p, {'wind_speed_10m': hours_since})

        epw, _, fetch = build(2021, answer=answer)
        # Rome is UTC+1 in winter: EPW hour 1 of 1 January ends at 01:00 local = 00:00 UTC of 1 January,
        # 24 hours after the base.
        self.assertAlmostEqual(epw.weatherdata[0].wind_speed, 24.0 / 100.0, places=2)
        # The request starts at that UTC day and ends the UTC day of the last hour (23:00 UTC on 31 December).
        params = fetch.call_args[0][0]
        self.assertEqual(params['start_date'], '2021-01-01')
        self.assertEqual(params['end_date'], '2021-12-31')
        self.assertEqual(params['wind_speed_unit'], 'ms')

    def test_daylight_saving_is_not_applied(self):
        # July in Rome is UTC+2 on the clock, but the file stays on UTC+1: hour 13 of 1 July = 11:00+... UTC
        def hours_since(times):
            base = dt.datetime(2020, 12, 31)
            return [(t - base).total_seconds() / 3600.0 / 10000.0 for t in times]

        epw, _, _ = build(2021, answer=lambda p: archive_answer(p, {'wind_speed_10m': hours_since}))
        row = next(r for r in epw.weatherdata if (r.month, r.day, r.hour) == (7, 1, 13))
        utc = dt.datetime(2021, 7, 1) + dt.timedelta(hours=13 - 1)
        expected = (utc - dt.datetime(2020, 12, 31)).total_seconds() / 3600.0 / 10000.0
        self.assertAlmostEqual(row.wind_speed, expected, places=2)

    def test_units_and_missing_codes(self):
        epw, _, _ = build(2021)
        r = epw.weatherdata[12]                       # 1 January, hour 13
        self.assertEqual(r.atmospheric_station_pressure, 100000)      # hPa -> Pa
        self.assertEqual(r.total_sky_cover, 4)                          # 40 % -> tenths
        self.assertEqual(r.opaque_sky_cover, 4)
        self.assertEqual(r.horizontal_infrared_radiation_intensity, 9999)  # E+ derives the sky temperature
        self.assertEqual(r.present_weather_observation, 9)
        self.assertEqual(r.present_weather_codes, 999999999)
        self.assertEqual(r.global_horizontal_illuminance, 999999)
        self.assertEqual(r.visibility, 9999)

    def test_radiation_passes_through_unchanged(self):
        epw, _, _ = build(2021)
        s = we.summary(epw)
        # 100 W/m2 for 9 hours a day for 365 days = 328.5 kWh/m2.
        self.assertAlmostEqual(s['annual']['ghi_kwh_m2'], 328.5, places=1)

    def test_snow_and_rain_in_cm_and_mm(self):
        epw, _, _ = build(2021, answer=lambda p: archive_answer(
            p, {'snow_depth': lambda t: [0.12] * len(t), 'precipitation': lambda t: [0.4] * len(t)}))
        r = epw.weatherdata[0]
        self.assertEqual(r.snow_depth, 12)
        self.assertEqual(r.liquid_precipitation_depth, 0.4)

    def test_no_snow_data_is_written_as_zero_with_a_warning(self):
        epw, report, _ = build(2021, answer=lambda p: archive_answer(
            p, {'snow_depth': lambda t: [None] * len(t)}))
        self.assertEqual(epw.weatherdata[0].snow_depth, 0)
        self.assertTrue(any('snow' in w for w in report['warnings']))

    def test_short_gap_is_interpolated_long_gap_refused(self):
        def gap(n):
            def f(times):
                v = [10.0] * len(times)
                for i in range(100, 100 + n):
                    v[i] = None
                return v
            return f

        epw, report, _ = build(2021, answer=lambda p: archive_answer(p, {'temperature_2m': gap(4)}))
        self.assertTrue(any('interpolation' in w for w in report['warnings']))
        self.assertTrue(all(r.dry_bulb_temperature == 10.0 for r in epw.weatherdata[90:110]))
        with self.assertRaises(we.OpenMeteoError):
            build(2021, answer=lambda p: archive_answer(p, {'temperature_2m': gap(9)}))

    def test_a_variable_the_model_does_not_have_is_refused(self):
        with self.assertRaises(we.OpenMeteoError):
            build(2021, answer=lambda p: archive_answer(p, drop=['diffuse_radiation']))

    def test_southern_hemisphere_standard_time(self):
        std, _ = we.standard_offset('Australia/Sydney', 2021, 151.2)
        self.assertEqual(std, 10)                                  # AEST, not AEDT
        self.assertEqual(we.standard_offset('Europe/Rome', 2021, 7.7)[0], 1)
        self.assertEqual(we.standard_offset('America/New_York', 2021, -74)[0], -5)
        self.assertEqual(we.standard_offset(None, 2021, 30.0)[0], 2)   # no zone: from the longitude

    def test_years_and_models(self):
        today = dt.date(2026, 10, 10)
        we.valid_year(2025, 'era5', today)
        for year, model in ((2026, 'era5'), (2016, 'ecmwf_ifs'), (2022, 'cerra'), (1930, 'era5')):
            with self.assertRaises(we.OpenMeteoError, msg=f'{year} {model}'):
                we.valid_year(year, model, today)

    def test_file_survives_a_save_and_read(self):
        epw, _, _ = build(2021)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'x.epw')
            we.save(epw, path)
            again = we.read(path)
            self.assertEqual(len(again.weatherdata), 8760)
            self.assertEqual(again.location.city, 'Torino')
            a, b = epw.weatherdata[4000], again.weatherdata[4000]
            for f in ('dry_bulb_temperature', 'relative_humidity', 'global_horizontal_radiation', 'wind_speed'):
                self.assertEqual(getattr(a, f), getattr(b, f))
            self.assertEqual([p for p in os.listdir(d)], ['x.epw'])    # no temporary left behind


class Edit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, _, _ = build(2021)

    def fresh(self):
        # A copy through the file, as the editor does.
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.epw')
            we.save(self.base, p)
            return we.read(p)

    def test_dew_point_and_humidity_are_inverse(self):
        for t, rh in ((20, 50), (-5, 80), (35, 30)):
            self.assertAlmostEqual(we.relative_humidity(t, we.dew_point(t, rh)), rh, places=3)

    def test_temperature_offset_keeps_relative_humidity(self):
        epw = self.fresh()
        before = epw.weatherdata[100].dry_bulb_temperature
        we.apply_edits(epw, adjustments=[{'variable': 'dry_bulb_temperature', 'op': 'add', 'value': 2}])
        r = epw.weatherdata[100]
        self.assertAlmostEqual(r.dry_bulb_temperature, before + 2, places=1)
        self.assertEqual(r.relative_humidity, 60)
        self.assertAlmostEqual(r.dew_point_temperature, we.dew_point(before + 2, 60), delta=0.06)

    def test_temperature_offset_can_keep_the_dew_point(self):
        epw = self.fresh()
        we.apply_edits(epw, adjustments=[{'variable': 'dry_bulb_temperature', 'op': 'add', 'value': 3, 'keep': 'dew'}])
        r = epw.weatherdata[100]
        self.assertEqual(r.dew_point_temperature, 3.0)
        self.assertLess(r.relative_humidity, 60)

    def test_months_limit_the_edit(self):
        epw = self.fresh()
        done = we.apply_edits(epw, adjustments=[
            {'variable': 'dry_bulb_temperature', 'op': 'set', 'value': 30, 'months': [7, 8]}])
        for r in epw.weatherdata:
            if int(r.month) in (7, 8):
                self.assertEqual(r.dry_bulb_temperature, 30.0)
            elif int(r.month) == 1:
                self.assertNotEqual(r.dry_bulb_temperature, 30.0)
        self.assertIn('months 7,8', done[0])
        self.assertIn('1488 hours', done[0])

    def test_solar_scales_the_three_components_and_pressure_is_clipped(self):
        epw = self.fresh()
        we.apply_edits(epw, adjustments=[
            {'variable': 'solar_radiation', 'op': 'scale', 'value': 0.5},
            {'variable': 'atmospheric_station_pressure', 'op': 'add', 'value': -1e9},
        ])
        r = next(r for r in epw.weatherdata if r.global_horizontal_radiation)
        self.assertEqual((r.global_horizontal_radiation, r.direct_normal_radiation, r.diffuse_horizontal_radiation),
                         (50, 100, 25))
        self.assertEqual(r.atmospheric_station_pressure, 31001)

    def test_humidity_is_clipped_and_moves_the_dew_point(self):
        epw = self.fresh()
        we.apply_edits(epw, adjustments=[{'variable': 'relative_humidity', 'op': 'add', 'value': 80}])
        r = epw.weatherdata[0]
        self.assertEqual(r.relative_humidity, 100)
        self.assertAlmostEqual(r.dew_point_temperature, r.dry_bulb_temperature, delta=0.1)

    def test_location_edit_and_validation(self):
        epw = self.fresh()
        done = we.apply_edits(epw, location={'city': 'Milano', 'latitude': '45.46', 'elevation': 120, 'country': ''})
        self.assertEqual(epw.location.city, 'Milano')
        self.assertEqual(epw.location.latitude, 45.46)
        self.assertEqual(epw.location.country, 'ITA')                  # an empty field leaves it alone
        self.assertEqual(len(done), 3)
        for bad in ({'latitude': 95}, {'longitude': 'x'}, {'timezone': 14}, {'nonsense': 1}):
            with self.assertRaises(we.EditError):
                we.apply_edits(epw, location=bad)

    def test_bad_adjustments_are_refused(self):
        epw = self.fresh()
        for adj in ({'variable': 'x', 'op': 'add', 'value': 1}, {'variable': 'wind_speed', 'op': 'pow', 'value': 1},
                    {'variable': 'wind_speed', 'op': 'add', 'value': 'a'},
                    {'variable': 'wind_speed', 'op': 'add', 'value': 1, 'months': [13]}):
            with self.assertRaises(we.EditError, msg=str(adj)):
                we.apply_edits(epw, adjustments=[adj])


class Summary(unittest.TestCase):
    def test_numbers(self):
        epw, _, _ = build(2021)
        s = we.summary(epw)
        self.assertEqual(s['period']['rows'], 8760)
        self.assertEqual(s['period']['years'], [2021])
        self.assertEqual(s['period']['days'], 365)
        self.assertEqual(len(s['daily']['temp_mean']), 365)
        self.assertEqual(len(s['monthly']), 12)
        self.assertAlmostEqual(s['annual']['temp_mean'], 10.0 + 5.0 * (sum(range(24)) / 24 / 24), delta=0.1)
        self.assertEqual(s['annual']['rh_mean'], 60)
        self.assertEqual(s['missing'], {})
        self.assertAlmostEqual(s['annual']['hdd18'], 365 * (18 - s['annual']['temp_mean']), delta=2)
        self.assertEqual(s['annual']['cdd24'], 0)

    def test_missing_codes_are_not_averaged(self):
        epw, _, _ = build(2021)
        epw.weatherdata[0].dry_bulb_temperature = None     # pyepw stores the missing code, 99.9
        s = we.summary(epw)
        self.assertEqual(s['missing'], {'dry_bulb_temperature': 1})
        self.assertLess(s['annual']['temp_max'], 30)


def text(path, new=None):
    """Read a file (or write `new` into it), closing it."""
    if new is not None:
        with open(path, 'w') as f:
            f.write(new)
        return None
    with open(path) as f:
        return f.read()


class UseInSession(unittest.TestCase):
    """weather_editor.use_in_session: uploads/, user_files/weather.epw, FMUs and notebook, in a scratch directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        for d in ('uploads', 'user_files'):
            os.makedirs(d)
        text('uploads/old.epw', 'old')
        text('uploads/model.idf', 'idf')
        text('library_new.epw', 'new')
        # model_converter pulls in Flask-SQLAlchemy and the database; it is replaced by a stub.
        self.fmu_calls = []
        stub = type(sys)('model_converter')
        stub.replace_weather_in_all_fmus = lambda p: (self.fmu_calls.append(p) or (2, []))
        self.patches = [mock.patch.dict(sys.modules, {'model_converter': stub})]
        for p in self.patches:
            p.start()
        import weather_editor
        self.we = weather_editor

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def use(self, has_model=True, returncode=0):
        run = mock.Mock(returncode=returncode)
        with mock.patch.object(self.we.idf_session, 'has_model', return_value=has_model),                 mock.patch.object(self.we.idf_session, 'working_path', return_value='uploads/model.idf'),                 mock.patch.object(self.we.subprocess, 'run', return_value=run) as sub:
            return self.we.use_in_session('library_new.epw', 'New Weather.epw'), sub

    def test_replaces_the_session_file_and_keeps_the_old_one(self):
        result, sub = self.use()
        self.assertEqual(os.listdir('uploads').count('New_Weather.epw'), 1)
        self.assertFalse(os.path.exists('uploads/old.epw'))
        self.assertEqual(text('uploads/New_Weather.epw'), 'new')
        self.assertEqual(text('user_files/weather.epw'), 'new')
        self.assertEqual(text('user_files/weather_library/old.epw'), 'old')
        self.assertEqual(result['kept'], 'old.epw')
        self.assertEqual(result['fmus'], 2)
        self.assertEqual(self.fmu_calls, [os.path.join('user_files', 'weather.epw')])

    def test_the_notebook_is_pointed_at_the_new_file_by_name(self):
        result, sub = self.use()
        self.assertEqual(sub.call_args[0][0], ['python', 'inject_data.py', 'model.idf', 'New_Weather.epw'])
        self.assertTrue(result['notebook'])

    def test_no_model_no_notebook(self):
        result, sub = self.use(has_model=False)
        sub.assert_not_called()
        self.assertIsNone(result['notebook'])

    def test_an_existing_library_copy_is_not_overwritten(self):
        os.makedirs('user_files/weather_library')
        text('user_files/weather_library/old.epw', 'already there')
        result, _ = self.use()
        self.assertEqual(text('user_files/weather_library/old.epw'), 'already there')
        self.assertIsNone(result['kept'])

    def test_using_the_session_file_again_loses_nothing(self):
        text('uploads/same.epw', 'same')
        os.remove('uploads/old.epw')
        with mock.patch.object(self.we.idf_session, 'has_model', return_value=False):
            result = self.we.use_in_session('uploads/same.epw', 'same.epw')
        self.assertEqual(text('uploads/same.epw'), 'same')
        self.assertIsNone(result['kept'])


class Tutorials(unittest.TestCase):
    def test_tutorial_notebooks_follow_the_weather(self):
        import nbformat
        from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
        stub = type(sys)('model_converter')
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, {'model_converter': stub}):
            cwd = os.getcwd()
            os.chdir(d)
            try:
                os.makedirs('surrogate_notebooks/tutorials')
                text('new.epw', 'x')
                nb = new_notebook(cells=[
                    new_markdown_cell("epw_file = 'ITA_Torino.160590_IWEC.epw' in prose"),
                    new_code_cell("idf = 'test.idf'\nepw_file = 'ITA_Torino.160590_IWEC.epw'\nprint(epw_file)"),
                    new_code_cell("epw_file = \"other.epw\"")])
                nbformat.write(nb, 'surrogate_notebooks/tutorials/1.ipynb')
                nbformat.write(new_notebook(cells=[new_code_cell('print(1)')]), 'surrogate_notebooks/tutorials/2.ipynb')
                import weather_editor
                changed = weather_editor.point_tutorials_at('new.epw', 'Madrid_2019.epw')
                self.assertEqual(changed, ['1.ipynb'])
                cells = nbformat.read('surrogate_notebooks/tutorials/1.ipynb', as_version=4).cells
                self.assertEqual(cells[1].source,
                                 "idf = 'test.idf'\nepw_file = 'Madrid_2019.epw'\nprint(epw_file)")
                self.assertEqual(cells[2].source, "epw_file = 'Madrid_2019.epw'")
                self.assertIn('ITA_Torino', cells[0].source)               # prose is left alone
                self.assertEqual(text('surrogate_notebooks/tutorials/Madrid_2019.epw'), 'x')
            finally:
                os.chdir(cwd)


class Hourly(unittest.TestCase):
    def test_series_units_and_missing(self):
        epw, _, _ = build(2021)
        epw.weatherdata[5].dry_bulb_temperature = None
        h = we.hourly(epw)
        self.assertEqual(len(h['month']), 8760)
        self.assertEqual(h['vars']['atmospheric_station_pressure']['values'][0], 1000.0)   # Pa -> hPa
        self.assertIsNone(h['vars']['dry_bulb_temperature']['values'][5])
        self.assertEqual(h['vars']['global_horizontal_radiation']['values'][12], 100.0)
        self.assertEqual(h['vars']['total_sky_cover']['values'][0], 4)


class ForeignFiles(unittest.TestCase):
    """Files from PVGIS or EnergyPlus are valid for EnergyPlus but not always to pyepw's letter."""

    ROW = ('2016,1,1,1,0,B8B8,1.14,-1.16,84.85,98190.00,9999,9999,255.26,0.00,-0.00,0.00,999999,999999,999999,'
           '9999,51,0.6,99,99,9999,99999,9,999999999,999,0.999,999,99,999,999,99')
    HEAD = ['LOCATION,unknown,-,unknown,ECMWF/ERA,unknown,45.07,7.69,1,248', 'DESIGN CONDITIONS,0',
            'TYPICAL/EXTREME PERIODS,0', 'GROUND TEMPERATURES,0', 'HOLIDAYS/DAYLIGHT SAVING,No,0,0,0',
            'COMMENTS 1,a', 'COMMENTS 2,b', 'DATA PERIODS,1,1,Data,Thursday, 1/ 1,12/31']

    def test_pvgis_style_row_is_read(self):
        row = self.ROW.replace('0.00,-0.00,0.00', '10.0,-0.00,-3.0')
        epw = we.read_text('\n'.join(self.HEAD + [row]) + '\n')
        r = epw.weatherdata[0]
        self.assertEqual((r.relative_humidity, r.atmospheric_station_pressure, r.minute), (85, 98190, 60))
        self.assertEqual((r.global_horizontal_radiation, r.direct_normal_radiation, r.diffuse_horizontal_radiation),
                         (10.0, 0.0, 0.0))                                     # -0.00 and -3.0 become 0
        self.assertEqual(r.dry_bulb_temperature, 1.14)

    def test_missing_code_in_a_checked_column_is_accepted(self):
        row = self.ROW.replace('1.14,-1.16', '99.9,99.9')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x.epw')
            text(p, '\n'.join(self.HEAD + [row]) + '\n')
            epw = we.read(p)                                                   # the file on disk is not touched
            self.assertEqual(we.summary(epw)['missing']['dry_bulb_temperature'], 1)
            out = os.path.join(d, 'y.epw')
            we.save(epw, out)
            self.assertIn(',99.9,99.9,', text(out))                             # the code is written back
            self.assertIn(',99,99,9999,99999,9,999999999,999,0.999,999,99,999,999,99', text(out))

    def test_a_real_error_is_still_an_error(self):
        row = self.ROW.replace('2016,1,1,1', '2016,13,1,1')
        with self.assertRaises(we.EpwReadError):
            we.read_text('\n'.join(self.HEAD + [row]) + '\n')


class Catalog(unittest.TestCase):
    def setUp(self):
        import weather_catalog as wc
        self.wc = wc
        feats = []
        for title, lon, lat in (('ITA_Torino.160590_IWEC', 7.65, 45.22), ('ITA_Milan.160660_IWEC', 9.28, 45.43),
                                ('FRA_Lyon.074810_IWEC', 4.95, 45.73)):
            url = f"{wc.ALLOWED_HOST}europe_wmo_region_6/{title[:3]}/{title}/{title}.epw"
            feats.append({'properties': {'title': title, 'epw': f'<a href={url}>Download Weather File</a>',
                                         'dir': f'<a href=https://energyplus.net/x/{title}>Go</a>'},
                          'geometry': {'coordinates': [lon, lat]}})
        feats.append({'properties': {'title': 'EVIL', 'epw': '<a href=https://evil.example/x.epw>x</a>'},
                      'geometry': {'coordinates': [0, 0]}})
        self.items = wc._parse({'features': feats})

    def test_parse_skips_foreign_hosts_and_reads_fields(self):
        self.assertEqual([i['id'] for i in self.items],
                         ['ITA_Torino.160590_IWEC', 'ITA_Milan.160660_IWEC', 'FRA_Lyon.074810_IWEC'])
        t = self.items[0]
        self.assertEqual((t['country'], t['kind'], t['name'], t['latitude']), ('ITA', 'IWEC', 'Torino.160590_IWEC', 45.22))

    def test_search_by_words_and_by_distance(self):
        r = self.wc.search(self.items, 'milan')
        self.assertEqual([h['id'] for h in r['results']], ['ITA_Milan.160660_IWEC'])
        near = self.wc.search(self.items, '', 45.07, 7.69)
        self.assertEqual([h['id'] for h in near['results']][0], 'ITA_Torino.160590_IWEC')
        self.assertTrue(10 < near['results'][0]['distance_km'] < 25)
        self.assertEqual(self.wc.search(self.items, 'ita iwec')['total'], 2)

    def test_only_the_energyplus_bucket_is_fetched(self):
        for url in ('https://evil.example/x.epw', self.wc.ALLOWED_HOST + 'a/b.zip'):
            with self.assertRaises(self.wc.CatalogError):
                self.wc.fetch_epw(url)


if __name__ == '__main__':
    unittest.main()
