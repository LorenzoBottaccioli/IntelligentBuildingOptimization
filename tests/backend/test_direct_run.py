"""The EnergyPlus-only run: what can be checked without EnergyPlus.

Timestamps, the reader of eplusout.sql (on a small database built here with the same tables and
columns EnergyPlus 9.6 writes), the site year and the error summary. The whole run is checked
against the real stack by tests/integrity/direct_run_check.py. From the repository root:

    python -m unittest tests.backend.test_direct_run
"""

import datetime
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(HERE, '..', '..', 'backend'))
sys.path.insert(0, BACKEND)
import direct_run  # noqa: E402


def epoch(*args):
    return int(datetime.datetime(*args, tzinfo=datetime.timezone.utc).timestamp())


class Timestamps(unittest.TestCase):
    def test_an_interval_is_labelled_by_its_end(self):
        self.assertEqual(direct_run.timestamp(2026, 1, 1, 0, 10), epoch(2026, 1, 1, 0, 10))

    def test_the_last_interval_of_a_day_is_hour_24(self):
        # EnergyPlus writes the end of 7 Jan as 7 Jan 24:00, which is 8 Jan 00:00 -- like the FMU's last step.
        self.assertEqual(direct_run.timestamp(2026, 1, 7, 24, 0), epoch(2026, 1, 8))

    def test_31_december_24_goes_into_the_next_year(self):
        self.assertEqual(direct_run.timestamp(2026, 12, 31, 24, 0), epoch(2027, 1, 1))

    def test_a_day_that_does_not_exist_in_the_year_is_an_error(self):
        with self.assertRaises(ValueError):
            direct_run.timestamp(2026, 2, 29, 1, 0)


def make_sql(path, rows, warmup=False, design=True):
    """A database with the tables direct_run reads. rows: {(key, name, frequency, units): [values]}."""
    con = sqlite3.connect(path)
    con.executescript("""
        create table EnvironmentPeriods (EnvironmentPeriodIndex integer, SimulationIndex integer,
                                         EnvironmentName text, EnvironmentType integer);
        create table Time (TimeIndex integer primary key, Year integer, Month integer, Day integer,
                           Hour integer, Minute integer, Dst integer, Interval integer, IntervalType integer,
                           SimulationDays integer, DayType text, EnvironmentPeriodIndex integer, WarmupFlag integer);
        create table ReportDataDictionary (ReportDataDictionaryIndex integer primary key, IsMeter integer,
                                           Type text, IndexGroup text, TimestepType text, KeyValue text,
                                           Name text, ReportingFrequency text, ScheduleName text, Units text);
        create table ReportData (ReportDataIndex integer primary key, TimeIndex integer,
                                 ReportDataDictionaryIndex integer, Value real);
    """)
    con.execute("insert into EnvironmentPeriods values (1, 1, 'DESIGN DAY', 1)")
    con.execute("insert into EnvironmentPeriods values (5, 1, 'RUN PERIOD 1', 3)")
    # three ten-minute steps on 1 Jan, then the end of the day; plus a warm-up row and a design-day row
    steps = [(5, 1, 1, 0, 10, 0), (5, 1, 1, 0, 20, 0), (5, 1, 1, 24, 0, 0)]
    if warmup:
        steps.insert(0, (5, 1, 1, 0, 0, 1))
    if design:
        steps.append((1, 7, 21, 1, 0, 0))
    for i, (env, month, day, hour, minute, warm) in enumerate(steps, start=1):
        con.execute("insert into Time (TimeIndex, Year, Month, Day, Hour, Minute, Interval, EnvironmentPeriodIndex, WarmupFlag) "
                    "values (?,?,?,?,?,?,10,?,?)", (i, 2017, month, day, hour, minute, env, warm))
    n = len(steps)
    for d, ((key, name, freq, units), values) in enumerate(rows.items(), start=1):
        con.execute("insert into ReportDataDictionary (ReportDataDictionaryIndex, KeyValue, Name, ReportingFrequency, Units) "
                    "values (?,?,?,?,?)", (d, key, name, freq, units))
        for t in range(1, n + 1):
            value = values[t - 1] if t - 1 < len(values) else 99.0
            con.execute("insert into ReportData (TimeIndex, ReportDataDictionaryIndex, Value) values (?,?,?)", (t, d, value))
    con.commit()
    con.close()


class ReadSeries(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.sql = os.path.join(self.dir, 'eplusout.sql')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    PLAN = [
        {'id': 'temp', 'query': {'key': 'block1:zonewest', 'variable': 'zone mean air temperature'}},
        {'id': 'setpoint', 'query': {'key': 'BLOCK1:ZONEWEST', 'variable': 'Zone Thermostat Heating Setpoint Temperature'}},
        {'id': 'absent', 'query': {'key': 'NOPE', 'variable': 'Nothing'}},
        {'id': 'unreadable', 'query': None},
    ]

    def rows(self):
        return {
            ('BLOCK1:ZONEWEST', 'Zone Mean Air Temperature', 'Zone Timestep', 'C'): [12.0, 13.0, 14.0],
            ('BLOCK1:ZONEWEST', 'Zone Thermostat Heating Setpoint Temperature', 'Zone Timestep', 'C'): [12, 12, 20],
            # the same variable at another frequency must never be taken for the timestep one
            ('BLOCK1:ZONEWEST', 'Zone Mean Air Temperature', 'Hourly', 'C'): [-1.0, -1.0, -1.0],
        }

    def test_keys_and_names_match_whatever_the_case(self):
        make_sql(self.sql, self.rows())
        series, missing, units = direct_run.read_series(self.sql, self.PLAN)
        self.assertEqual([v for *_, v in series['temp']], [12.0, 13.0, 14.0])
        self.assertEqual(units['temp'], 'degC')

    def test_only_the_run_period_and_never_the_warm_up(self):
        make_sql(self.sql, self.rows(), warmup=True, design=True)
        series, _, _ = direct_run.read_series(self.sql, self.PLAN)
        self.assertEqual(len(series['temp']), 3)
        self.assertEqual([row[:4] for row in series['temp']], [(1, 1, 0, 10), (1, 1, 0, 20), (1, 1, 24, 0)])

    def test_a_variable_the_model_does_not_report_is_named_not_invented(self):
        make_sql(self.sql, self.rows())
        series, missing, _ = direct_run.read_series(self.sql, self.PLAN)
        self.assertEqual(missing, ['absent'])
        self.assertNotIn('absent', series)
        self.assertNotIn('unreadable', series)


class SiteYear(unittest.TestCase):
    def test_the_year_of_points_yaml_is_used(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'points.yaml'), 'w', encoding='utf-8') as handle:
                handle.write('# header\nsite: {name: "test", year: 2031}\npoints:\n')
            self.assertEqual(direct_run._site_year(d), 2031)

    def test_without_it_the_current_year(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(direct_run._site_year(d), datetime.date.today().year)


class ErrSummary(unittest.TestCase):
    def test_severe_and_fatal_messages_are_counted_and_quoted(self):
        text = ("   ** Warning ** something mild\n"
                "   ** Severe  ** Invalid Name=SHADE\n"
                "   **   ~~~   ** Object name conflicts with a global variable name in EMS\n"
                "   **  Fatal  ** Program terminated\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'eplusout.err')
            with open(path, 'w', encoding='latin-1') as handle:
                handle.write(text)
            severe, lines = direct_run._err_summary(path)
        self.assertEqual(severe, 2)
        self.assertIn('Invalid Name=SHADE', lines[0])
        self.assertIn('conflicts with a global variable', lines[0])

    def test_a_missing_file_is_zero(self):
        self.assertEqual(direct_run._err_summary('nope.err'), (0, []))


class State(unittest.TestCase):
    def test_a_run_needs_a_valid_period(self):
        with self.assertRaises(ValueError):
            direct_run.start({'timestep': 7, 'startDay': 0, 'warmupDays': 0, 'endDay': 7}, '.')
        self.assertFalse(direct_run.is_active())


if __name__ == '__main__':
    unittest.main()
