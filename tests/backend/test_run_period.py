"""The shared simulated period: Field/parameters.py <-> run_period.py.

Pure Python, nothing else needed. From the repository root:

    python -m unittest tests.backend.test_run_period
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.environ.get('BACKEND_DIR', os.path.join(HERE, '..', '..', 'backend'))
sys.path.insert(0, BACKEND)
import run_period  # noqa: E402

# What the FMU export wrote on 10 Oct 2026 (Field/parameters.py), plus the export page's warm-up variant.
EXPORTED = """import numpy as np

parameter = {}
# fmi_gym parameter
parameter['seed'] = 1
parameter['store_data'] = True

# fmu parameter
dtype = np.float64
parameter['fmu_step_size'] = 600  # s, = 3600 / 6 timesteps per hour of the model
parameter['fmu_path'] = 'test.fmu'
parameter['fmu_start_time'] = 0 * 60 * 60 * 24  # day 0, 1 Jan 00:00
parameter['fmu_warmup_time'] = None  # no fmi_gym warm-up: the controller acts from the start
parameter['fmu_final_time'] = 7 * 60 * 60 * 24  # day 7, 8 Jan 00:00

# data exchange parameter
parameter['action_names'] = ["ZONEWEST_Heating_Setpoint_FMU"]
parameter['action_min'] = np.array([10], dtype=np.float64)
parameter['reward_names'] = []
"""

PERIOD = {'timestep': 4, 'startDay': 30, 'warmupDays': 3, 'endDay': 365}


class WithField(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'parameters.py'), 'w', encoding='utf-8') as handle:
            handle.write(EXPORTED)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def text(self):
        with open(os.path.join(self.dir, 'parameters.py'), encoding='utf-8') as handle:
            return handle.read()


class Read(WithField):
    def test_reads_what_the_export_wrote(self):
        got = run_period.read(self.dir)
        self.assertEqual((got['exists'], got['timestep'], got['startDay'], got['warmupDays'], got['endDay']),
                         (True, 6, 0, 0, 7))

    def test_without_an_export_it_gives_defaults_and_the_model_timestep(self):
        os.remove(os.path.join(self.dir, 'parameters.py'))
        got = run_period.read(self.dir, model_timestep=12)
        self.assertFalse(got['exists'])
        self.assertEqual((got['timestep'], got['startDay'], got['endDay']), (12, 0, 7))

    def test_the_export_fallback_text_with_a_division_is_read_too(self):
        text = EXPORTED.replace("= 600  #", "= 3600 / 4  #")
        with open(os.path.join(self.dir, 'parameters.py'), 'w', encoding='utf-8') as handle:
            handle.write(text)
        self.assertEqual(run_period.read(self.dir)['timestep'], 4)

    def test_an_unreadable_file_is_not_an_exported_period(self):
        with open(os.path.join(self.dir, 'parameters.py'), 'w', encoding='utf-8') as handle:
            handle.write("parameter['fmu_step_size'] = os.getcwd()\n")
        self.assertFalse(run_period.read(self.dir)['exists'])


class Write(WithField):
    def test_round_trip_with_a_controller_warm_up(self):
        run_period.write(self.dir, PERIOD)
        got = run_period.read(self.dir)
        self.assertEqual({k: got[k] for k in PERIOD}, PERIOD)

    def test_only_the_four_period_lines_change(self):
        before = self.text().splitlines()
        run_period.write(self.dir, PERIOD)
        after = self.text().splitlines()
        self.assertEqual(len(before), len(after))
        changed = [b.split('=')[0].strip() for b, a in zip(before, after) if a != b]
        self.assertEqual(changed, ["parameter['fmu_step_size']", "parameter['fmu_start_time']",
                                   "parameter['fmu_warmup_time']", "parameter['fmu_final_time']"])

    def test_the_comments_say_the_dates(self):
        run_period.write(self.dir, PERIOD)
        self.assertIn('day 30, 31 Jan 00:00', self.text())
        self.assertIn('absolute: controller acts from day 33 (3 Feb)', self.text())

    def test_back_to_no_warm_up_writes_none(self):
        run_period.write(self.dir, PERIOD)
        run_period.write(self.dir, dict(PERIOD, warmupDays=0))
        self.assertIn("parameter['fmu_warmup_time'] = None", self.text())

    def test_nothing_exported_is_refused_not_invented(self):
        os.remove(os.path.join(self.dir, 'parameters.py'))
        with self.assertRaises(FileNotFoundError):
            run_period.write(self.dir, PERIOD)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'parameters.py')))

    def test_an_invalid_period_leaves_the_file_alone(self):
        before = self.text()
        with self.assertRaises(ValueError):
            run_period.write(self.dir, dict(PERIOD, endDay=400))
        self.assertEqual(self.text(), before)


class Validate(unittest.TestCase):
    def test_what_the_export_page_refuses_is_refused_here(self):
        for bad, why in ((dict(PERIOD, timestep=7), 'divide 60'),
                         (dict(PERIOD, endDay=366), 'at most 365'),
                         (dict(PERIOD, startDay=5, warmupDays=2, endDay=7), 'at least one day'),
                         (dict(PERIOD, startDay=1.5), 'whole number'),
                         (dict(PERIOD, startDay=-1), 'whole number'),
                         ({'timestep': 'x'}, 'numbers')):
            with self.assertRaises(ValueError, msg=why) as ctx:
                run_period.validate(bad)
            self.assertIn(why, str(ctx.exception))

    def test_a_full_year_is_valid(self):
        self.assertEqual(run_period.validate({'timestep': 6, 'startDay': 0, 'warmupDays': 0, 'endDay': 365})['endDay'], 365)


class Dates(unittest.TestCase):
    def test_day_to_date_uses_a_non_leap_year(self):
        self.assertEqual(run_period.day_date(0), (1, 1))
        self.assertEqual(run_period.day_date(59), (3, 1))
        self.assertEqual(run_period.day_date(364), (12, 31))

    def test_the_last_simulated_day_is_the_one_before_the_end_day(self):
        # fmu_final_time = 7 days is 8 Jan 00:00: the last simulated day is 7 Jan.
        self.assertEqual(run_period.day_date(7 - 1), (1, 7))


class ExportedTimestep(unittest.TestCase):
    """The timestep baked into the exported FMU: what the 're-export' warning compares with."""

    def test_read_from_export_info(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'export_info.json'), 'w', encoding='utf-8') as handle:
                handle.write('{"model": "test", "timestep": 6}')
            self.assertEqual(run_period.exported_timestep(d), 6)

    def test_an_older_export_did_not_record_it(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'export_info.json'), 'w', encoding='utf-8') as handle:
                handle.write('{"model": "test"}')
            self.assertIsNone(run_period.exported_timestep(d))

    def test_no_export_no_timestep(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(run_period.exported_timestep(d))


class ModelFiles(unittest.TestCase):
    def test_timestep_is_read_from_the_idf_text(self):
        with tempfile.NamedTemporaryFile('w', suffix='.idf', delete=False) as handle:
            handle.write('Version,9.6;\n\nTimestep,\n    6;                        !- Number of Timesteps per Hour\n')
            path = handle.name
        try:
            self.assertEqual(run_period.model_timestep(path), 6)
        finally:
            os.remove(path)

    def test_no_idf_no_timestep(self):
        self.assertIsNone(run_period.model_timestep(None))
        self.assertIsNone(run_period.model_timestep('does-not-exist.idf'))


if __name__ == '__main__':
    unittest.main()
