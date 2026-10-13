"""What bdopt 0.2.0 does with a model that declares an EnergyPlus version other than 9.6.

Runs in jupyter:smartbuilding-surrogate. usage: python other_versions.py DIR EPW
For every *.idf in DIR: load_idf (does it load? which version?), build an EnergyPlusEvaluator with one Parameter that
writes a value the file already has, and call evaluate() on that one row. Prints the exception class and text at each step.
Nothing is run by EnergyPlus when the version is refused (the check happens before the simulation).
"""
import glob, os, sys, traceback
import pandas as pd
import bdopt
from bdopt import EnergyPlusEvaluator, FieldSelector, MeterReader, Parameter, Problem, RangeParameter

d, epw = sys.argv[1], sys.argv[2]
for p in sorted(glob.glob(os.path.join(d, '*.idf'))):
    print('==', os.path.basename(p))
    try:
        idf = bdopt.load_idf(p)
        print('  load_idf: ok, version', idf.version, '| objects', len(idf.objects))
    except Exception as e:
        print('  load_idf: %s: %s' % (type(e).__name__, e)); continue
    try:
        mat = idf.by_class('Material')[0]
        name, base = mat.get(0), mat.get(2)
        prob = Problem([Parameter(FieldSelector('Material', name, 'Thickness'), RangeParameter(float(base) * .5, float(base) * 1.5), name='thk')],
                       [MeterReader('Electricity:Facility')])
        ev = EnergyPlusEvaluator(prob, idf, epw, out_dir='/tmp/ov_runs', cache=False, on_error='raise', timeout=180)
        print('  EnergyPlusEvaluator(...): ok (no exception yet)')
    except Exception as e:
        print('  EnergyPlusEvaluator(...): %s: %s' % (type(e).__name__, e)); continue
    try:
        r = ev.evaluate(pd.DataFrame({'thk': [float(base)]}))
        print('  evaluate: ok', r.to_dict('records'))
    except Exception as e:
        print('  evaluate: %s: %s' % (type(e).__name__, str(e)[:600]))

# the same with auto_upgrade=True, which the message above recommends: image B ships no IDFVersionUpdater
print('--- with auto_upgrade=True')
for p in sorted(glob.glob(os.path.join(d, '*.idf'))):
    idf = bdopt.load_idf(p)
    mat = idf.by_class('Material')[0]
    base = mat.get(2)
    prob = Problem([Parameter(FieldSelector('Material', mat.get(0), 'Thickness'), RangeParameter(float(base) * .5, float(base) * 1.5), name='thk')],
                   [MeterReader('Electricity:Facility')])
    try:
        ev = EnergyPlusEvaluator(prob, idf, epw, out_dir='/tmp/ov_runs2', cache=False, on_error='raise', timeout=180, auto_upgrade=True)
        print(os.path.basename(p), 'constructor ok')
        ev.evaluate(pd.DataFrame({'thk': [float(base)]}))
        print(os.path.basename(p), 'evaluate ok')
    except Exception as e:
        print(os.path.basename(p), '%s: %s' % (type(e).__name__, str(e)[:500]))
