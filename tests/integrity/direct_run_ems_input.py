"""EnergyPlus-only run, FMU inputs read from the model's own EMS -- and the refusal when that is impossible.

Runs inside the backend container (cwd /app), from the repo root:

    docker cp tests/integrity/direct_run_ems_input.py backend:/app/direct_run_ems_input.py
    docker exec backend python direct_run_ems_input.py MODEL.idf WEATHER.epw WINDOW [BEGIN_DAY]

MODEL must have an EnergyManagementSystem:Actuator on 'Window Shading Control / Control Status' of the
window WINDOW (lab_optimal.idf has them). Two cases are built from it:

 1. a platform FMU input (ems_chain.add_controlled_actuator) on that same window. Without an FMU nobody
    writes it, so the point must be read from the model's own EMS actuator: the run must end with no
    severe error and the stored values must be the shading status the model's program sets (0, 6, ...);
 2. an FMU input declared by hand and read by an EMS program: build_run_idf must raise ValueError,
    because without the FMU that Erl variable would not exist.

10 Oct 2026, lab_optimal.idf, window Block1B:Bathroom1_Wall_6_0_0_0_0_0_Win, begin day 181 (a July week):
severe 0, 1008 rows, values {0, 6}; the hand-declared input is refused.
"""
import os
import subprocess
import sys

import direct_run
import ems_chain
import model_converter
from eppy.modeleditor import IDF

model, epw, window = sys.argv[1:4]
begin = int(sys.argv[4]) if len(sys.argv) > 4 else 181
period = dict(timestep=6, startDay=begin, warmupDays=0, endDay=begin + 7)
folder = os.path.join('simulation_outputs', 'direct_ems_case')
os.makedirs(folder, exist_ok=True)
IDF.setiddname(model_converter.IDD_PATH)
ok = True

idf = IDF(model)
ems_chain.add_controlled_actuator(idf, 'Test_shade', window, 'Window Shading Control', 'Control Status', initial_value=0)
case = os.path.join(folder, 'with_input.idf')
idf.saveas(case)
target = os.path.join(folder, 'run.idf')
plan = direct_run.build_run_idf(case, target, period, 'case')
point = next(p for p in plan if p['fmu'] == 'Test_shade_FMU')
print('input source:', point['source'])
ok &= bool(point['source'] and 'ems_actuator' in point['source'])
status = next(p for p in plan if p['id'] == 'test_shade_status')
print('its status output:', status['source'], '-', status.get('reason'))
ok &= status['source'] is None

run = subprocess.run(['docker', 'exec', '-u', 'root', 'energyplus', direct_run.ENERGYPLUS_BIN,
                      '-d', '/workspace/' + folder.replace(os.sep, '/'), '-w', '/workspace/' + epw.replace(os.sep, '/'),
                      '/workspace/' + target.replace(os.sep, '/')], capture_output=True, text=True)
severe, lines = direct_run._err_summary(os.path.join(folder, 'eplusout.err'))
series, missing, _ = direct_run.read_series(os.path.join(folder, 'eplusout.sql'), [p for p in plan if p.get('query')])
values = [v for *_, v in series[point['id']]]
print('exit', run.returncode, 'severe', severe, lines, 'rows', len(values), 'distinct', sorted(set(values)), 'missing', missing)
ok &= run.returncode == 0 and severe == 0 and len(values) == 7 * 24 * 6 and not missing
ok &= set(values) <= {-1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 7.0, 8.0, 9.0}

idf = IDF(model)
hand = idf.newidfobject(ems_chain.TO_VARIABLE)
hand.Name = 'HandInput'
hand.FMU_Variable_Name = 'HandInput_FMU'
hand.Initial_Value = 1
program = idf.newidfobject('EnergyManagementSystem:Program')
program.Name = 'UsesHand'
program.Program_Line_1 = 'SET Dummy = HandInput'
case2 = os.path.join(folder, 'with_hand.idf')
idf.saveas(case2)
try:
    direct_run.build_run_idf(case2, os.path.join(folder, 'run2.idf'), period, 'case')
    print('hand-declared input NOT refused')
    ok = False
except ValueError as exc:
    print('refused:', exc)

print('OK' if ok else 'FAIL')
sys.exit(0 if ok else 1)
