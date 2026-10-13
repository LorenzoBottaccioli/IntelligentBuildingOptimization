"""EMS fidelity: the same model, run for one week, (a) as EnergyPlus reads the original text and (b) through bdopt.

Runs in jupyter:smartbuilding-surrogate (python 3.11, bdopt 0.2.0, EnergyPlus 9.6).

usage: python ems_fidelity.py MODEL.idf EPW WORKDIR TAG BEGIN_MONTH BEGIN_DAY END_MONTH END_DAY [variant]

 1. WORKDIR/TAG/week.idf = MODEL with its RunPeriod set to the given dates (text edit of the RunPeriod object only).
 2. (a) energyplus CLI on week.idf + "Output:SQLite, SimpleAndTabular;" appended (nothing else touched) -> eplusout.sql.
 3. (b) bdopt: bdopt.load_idf(week.idf); copy without Output:Variable (what the platform's cell does, unless variant
    is 'keep_variables'); one Parameter writing the value the file already has (first Material's Thickness);
    EnergyPlusEvaluator(..., keep_dirs=True, cache=False); evaluate the single base-design row.
 4. Prints Electricity:Facility and DistrictHeating:Facility from (a) (sum of the timestep/hourly meter rows),
    from (a) Run Period row, from (b) bdopt result and from (b)'s own run directory; and an object-level diff of the
    IDF EnergyPlus received in (b) against week.idf (parsed with bdopt's parser on both sides).
"""
import glob, json, os, re, shutil, sqlite3, subprocess, sys, time
import pandas as pd
import bdopt
from bdopt import (CategoryParameter, EnergyPlusEvaluator, FieldSelector, MeterReader, Parameter, Problem,
                   RangeParameter)

model, epw, work, tag, bm, bd, em, ed = sys.argv[1:9]
variant = sys.argv[9] if len(sys.argv) > 9 else ''
root = os.path.join(work, tag)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
METERS = ('Electricity:Facility', 'DistrictHeating:Facility', 'DistrictCooling:Facility')

text = open(model, encoding='latin-1').read()
m = re.search(r'^[ \t]*RunPeriod,.*?;', text, re.S | re.M | re.I)
assert m, 'no RunPeriod'
block = m.group(0)
vals = re.split(r',', re.sub(r'!.*', '', block))
# fields 2..5 are begin month, begin day, <begin year>, end month, end day  (name is field 1)
lines = block.split('\n')
def setline(idx_field, value):
    n = 0
    for i, l in enumerate(lines):
        if i == 0:
            continue
        n += 1
        if n == idx_field:
            lines[i] = re.sub(r'^(\s*)[^,;!]*([,;])', lambda mm: mm.group(1) + str(value) + mm.group(2), l, count=1)
            return
setline(2, bm); setline(3, bd); setline(5, em); setline(6, ed)
new_block = '\n'.join(lines)
week_text = text.replace(block, new_block)
print('RunPeriod now:\n' + new_block.split('Use Weather')[0])
week = os.path.join(root, 'week.idf')
open(week, 'w', encoding='latin-1', newline='').write(week_text)


def sums(sql):
    con = sqlite3.connect(sql)
    out = {}
    for mname in METERS:
        rows = con.execute('select d.ReportingFrequency, count(*), sum(r.Value) from ReportData r join ReportDataDictionary d '
                           'on r.ReportDataDictionaryIndex=d.ReportDataDictionaryIndex where d.Name=? and d.IsMeter=1 '
                           'group by d.ReportingFrequency', (mname,)).fetchall()
        out[mname] = {f: (n, s) for f, n, s in rows}
    errs = con.execute('select ErrorType, count(*) from Errors group by ErrorType').fetchall()
    con.close()
    return out, errs

# ---- (a) energyplus CLI on the original text
a_dir = os.path.join(root, 'a'); os.makedirs(a_dir)
a_idf = os.path.join(a_dir, 'in.idf')
open(a_idf, 'w', encoding='latin-1', newline='').write(week_text + '\n\nOutput:SQLite,\n  SimpleAndTabular;\n')
exe = shutil.which('energyplus') or glob.glob('/usr/local/EnergyPlus-*/energyplus')[0]
t = time.time()
r = subprocess.run([exe, '-w', epw, '-d', a_dir, a_idf], capture_output=True, text=True)
print('(a) energyplus exit', r.returncode, '%.0fs' % (time.time() - t), r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '')
a_sum, a_err = sums(os.path.join(a_dir, 'eplusout.sql'))
print('(a) errors', a_err)

# ---- (b) bdopt
idf = bdopt.load_idf(week)
mat = idf.by_class('Material')[0]
name, base = mat.get(0), mat.get(2)
print('(b) parameter writes Material "%s" Thickness = %s (what the file already has)' % (name, base))
param = Parameter(FieldSelector('Material', name, 'Thickness'), RangeParameter(float(base) * 0.5, float(base) * 1.5), name='thk')
problem = Problem([param], [MeterReader(m_) for m_ in METERS])
sim = idf.copy()
if variant != 'keep_variables':
    sim.remove(sim.by_class('Output:Variable'))
b_out = os.path.join(root, 'b')
ev = EnergyPlusEvaluator(problem, sim, epw, out_dir=b_out, processes=1, cache=False, keep_dirs=True)
t = time.time()
res = ev.evaluate(pd.DataFrame({'thk': [float(base)]}))
print('(b) bdopt %.0fs' % (time.time() - t)); print(res.to_string())
sqls = glob.glob(os.path.join(b_out, '**', '*.sql'), recursive=True)
print('(b) run dirs', [os.path.dirname(p) for p in sqls])
b_sum, b_err = sums(sqls[0])
print('(b) errors', b_err)
b_in = glob.glob(os.path.join(os.path.dirname(sqls[0]), '*.idf'))
print('(b) idf files in run dir', b_in)

summary = {'a_cli': a_sum, 'b_runperiod_dir': b_sum, 'bdopt_result': res.iloc[0].to_dict(), 'param': [name, base]}
for mname in METERS:
    # E+ writes the same energy at every frequency it was asked for (and the aggregates of the finer ones), so the
    # frequencies are NOT added up: the run-period row is the number bdopt reads, the finest row is its cross-check.
    rp = a_sum[mname].get('Run Period', (0, 0.0))[1]
    fine = max(a_sum[mname].items(), key=lambda kv: kv[1][0])[1][1] if a_sum[mname] else 0.0
    bd_ = res.iloc[0][mname]
    rel = (bd_ - rp) / rp if rp else float('nan')
    print('%-24s (a) Run Period row = %.6f J | (a) finest-frequency sum = %.6f J | (b) bdopt = %.6f J | b-a = %.3e J (rel %.2e)'
          % (mname, rp, fine, bd_, bd_ - rp, rel))
    summary[mname] = {'a_run_period': rp, 'a_finest_sum': fine, 'b_bdopt': bd_, 'rel_diff': rel}
# object diff of the IDF energyplus received in (b) vs week.idf
src = bdopt.load_idf(b_in[0]) if b_in else None
def objs(i):
    return [(o.class_name.lower(), tuple(str(f).strip() for f in o.fields)) for o in i.objects]
if src is not None:
    A, B = objs(idf), objs(src)
    from collections import Counter
    ca, cb = Counter(A), Counter(B)
    only_a, only_b = ca - cb, cb - ca
    print('(b) objects in week.idf not in the IDF EnergyPlus ran: %d ; objects added: %d' % (sum(only_a.values()), sum(only_b.values())))
    for k in list(only_a)[:10]: print('   removed/changed:', k[0], k[1][:3])
    for k in list(only_b)[:10]: print('   added/changed  :', k[0], k[1][:3])
    summary['removed'] = [k[0] + ' ' + str(k[1][:3]) for k in only_a]
    summary['added'] = [k[0] + ' ' + str(k[1][:3]) for k in only_b]
json.dump(summary, open(os.path.join(root, 'summary.json'), 'w'), indent=1, default=str)
