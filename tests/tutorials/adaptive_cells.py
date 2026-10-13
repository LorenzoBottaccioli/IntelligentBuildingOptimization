"""The cells of 4_adaptive_sampling.ipynb. Imported by make_tutorials.py (``md`` and ``code`` are passed in).

Built from the course notebook AdaptiveSampling_besos_example.ipynb (LOLA-Voronoi, one objective) and from its bdopt port
(course_notebooks_bdopt/AdaptiveSampling_besos_example.ipynb), moved to the model of the series (test.idf, the five
variables of notebook 2) and extended with a second part with the three objectives together.
"""


def cells(md, code, header):
    return [
        header(
            4, "Adaptive sampling",
            "Let the sampler choose which simulations to run: start from a few designs, add the ones that teach the "
            "surrogate most, and see how the error falls. First with one objective, then with three.",
            "Notebooks 1 and 2. The 50 simulations of notebook 2 (`surrogate_simple_simulation.csv`) are reused as the "
            "starting designs, as the test designs and for the comparison; the only new simulations are the ones the "
            "sampler asks for.",
            "about 3 minutes (2 runs of 16 new simulations each, two at a time)."),
        md("""## Why adaptive sampling?

In notebook 2 the designs were chosen all at once (a Latin hypercube) and the learning curve told us, *afterwards*, whether
that was enough. Adaptive sampling chooses them a batch at a time: it **explores** the parts of the design space that are
still empty and **exploits** what the simulations done so far have shown (where the response bends, more designs are
needed). It stops when the surrogate is accurate enough, so the number of simulations is not decided in advance.

This notebook uses LOLA-Voronoi sampling [[1]]. It works with any surrogate model; here it is applied with the Gaussian
process of notebook 2.

[1]: https://doi.org/10.1137/090761811 (Crombecq, K., Gorissen, D., Deschrijver, D., Dhaene, T. (2011). A novel hybrid sequential design strategy for global surrogate modeling of computer experiments. SIAM Journal on Scientific Computing 33(4), 1948-1974.)"""),
        md("""![The LOLA-Voronoi scheme](image/LOLA-Voronoi.jpg)

The scheme: after the surrogate has been fitted and its accuracy checked, every simulated design gets a **score** (next
section); the best-scoring Voronoi cell is where the next design is generated, which is simulated and added to the data;
and the loop starts again."""),
        code("""%matplotlib inline
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from bdopt import (EnergyPlusEvaluator, FieldSelector, IntegerParameter, Parameter, Problem, RangeParameter,
                   load_idf, sampling, viz)
from bdopt.adaptive import METHODS, AdaptiveSampler
from bdopt.surrogate import GPSurrogate
from window_to_wall import wwr      # the window-to-wall ratio as a design variable: see 1_bdopt_overview.ipynb
import explore                      # explore.py, next to this notebook"""),
        md("""## The problem of notebook 2

The same model and the same five design variables, and the same three objectives."""),
        code("""idf = load_idf('test.idf')
epw_file = 'ITA_Torino.160590_IWEC.epw'

parameters = [
    Parameter(FieldSelector('Material', 'XPS Extruded Polystyrene  - CO2 Blowing_0041', 'Thickness'),
              RangeParameter(0.01, 0.45), name='Insulation Thickness'),
    Parameter(FieldSelector('WindowMaterial:Glazing', '3', 'Conductivity'),
              RangeParameter(0.1, 1), name='Glazing conductivity'),
    Parameter(FieldSelector('WindowMaterial:Glazing', '3', 'Solar Transmittance at Normal Incidence'),
              RangeParameter(0.01, 0.8), name='Glazing solar transmittance'),
    wwr(0.1, 0.8),
    Parameter(FieldSelector('Lights', '*', 'Watts per Zone Floor Area'), IntegerParameter(8, 12), name='Lights Watts/Area'),
]
objectives = ['Electricity:Facility', 'DistrictHeating:Facility', 'DistrictCooling:Facility']   # EnergyPlus meters [J]
problem = Problem(parameters, objectives)"""),
        md("""## The simulations we already have

Notebook 2 simulated 50 designs (a Latin hypercube). Nothing is simulated twice in this notebook: they are used as follows.

| | designs | used for |
|---|---|---|
| `initial` | the first 10 | the starting point of the adaptive sampler |
| `test` | the last 15 | measuring *every* surrogate of this notebook: no surrogate is ever trained on them |
| `lhs_pool` | the first 35 | the comparison: a surrogate trained on the first *k* of them is what "choosing all designs at once" gives for *k* simulations |

(The first *k* designs of a Latin hypercube of 50 are not a Latin hypercube of *k*, but they are spread over the space in the
same way: a fair, free comparison.)"""),
        code("""try:
    stored = pd.read_csv('surrogate_simple_simulation.csv', index_col=0)
except FileNotFoundError:
    raise FileNotFoundError("surrogate_simple_simulation.csv is written by 2_surrogate_modelling.ipynb: run that notebook first "
                            "(it is also stored in this folder in the demo session)")
assert list(stored.columns) == problem.names(), "the stored simulations are for another problem: run notebook 2 again"

initial, test, lhs_pool = stored.iloc[:10], stored.iloc[35:], stored.iloc[:35]
len(initial), len(test), len(lhs_pool)"""),
        md("""## Sampler settings"""),
        code("""N_ITER = 4      # iterations of the sampler
BATCH = 4       # designs added per iteration: 4 x 4 = 16 new simulations in each of the two runs below"""),
        md("""# Part 1 · One objective: the heating demand

With one objective the sampler looks for the parts of the design space where *that* response is least linear. We take the
heating demand: it depends on the window-to-wall ratio, on the glazing and on the insulation in a non-trivial way, while the
electricity depends only on the lighting power (notebook 2), so there would be nothing for the sampler to find."""),
        code("""objective = 'DistrictHeating:Facility'
problem1 = Problem(parameters, [objective])
evaluator1 = EnergyPlusEvaluator(problem1, idf, epw_file,
                                 out_dir='/tmp/bdopt_runs',   # work files go to the container's own disk (the shared folder is much slower)
                                 err_dir='outputdir',         # runs that fail are kept here, with the EnergyPlus error file
                                 processes=2)                 # EnergyPlus runs in parallel
columns1 = problem1.parameter_names + problem1.objective_names     # the table the sampler wants: parameters + objectives

sampler1 = AdaptiveSampler(problem1, evaluator1, method='flola_voronoi', surrogate=GPSurrogate(), seed=0)"""),
        md("""## LOLA-Voronoi sampling

`flola_voronoi` is the *fuzzy* version of LOLA-Voronoi of van der Herten et al. (2015); plain `'lola_voronoi'` and many other
criteria are available (`bdopt.adaptive.METHODS`: see *Your turn* at the end). New designs are generated in the Voronoi cell
of the already simulated designs with the highest hybrid score $H$:

$$H = V + E$$

$V$ (exploration) is the size of the Voronoi cell, which approximates how sparse the samples are around that design;
$E$ (exploitation) is how far the response in the neighbourhood of the design is from a plane (a local linear fit), which
says where the response bends.

The sampler starts from `initial` (no new simulation), fits the surrogate, measures it on `test`, and repeats `N_ITER`
times: score the designs, generate `BATCH` new ones, simulate them, refit. `tol=0` turns off the "accurate enough" stop so
that the whole curve is drawn (below, how to use it)."""),
        code("""result1 = sampler1.run(initial_data=initial[columns1], test_data=test[columns1],
                       max_iter=N_ITER, batch=BATCH, tol=0, verbose=False)
print(result1)
print(evaluator1.stats())"""),
        md("""`result1.data` holds every design used for training (first the 10 initial ones, then the ones the sampler added, in
order), `result1.test` the held-out ones, `result1.history` one row per iteration and `result1.surrogate` is the last
surrogate. `r2:...` is the $R^2$ on the test designs; `scaled_rmse` the RMSE on them in units of the standard deviation of
the objective."""),
        code("result1.history[['iteration', 'n_train', 'n_evaluations', 'scaled_rmse', 'r2:' + objective]]"),
        md("""### Is it better than choosing all the designs at once?

The question is fair only on the same test designs and with the same number of simulations. For each size reached by the
sampler, a surrogate trained on that many designs of `lhs_pool`:"""),
        code("""def lhs_score(problem_, sizes):
    \"\"\"R2 and RMSE (% of the mean) on `test` of a surrogate trained on the first k designs of lhs_pool, for each k.\"\"\"
    cols = problem_.parameter_names + problem_.objective_names
    rows = {}
    for k in sizes:
        score = GPSurrogate().fit(lhs_pool[cols].iloc[:k], problem_).score(test[cols])
        rows[k] = score[['r2', 'rmse_pct']].stack()
    return pd.DataFrame(rows).T


lhs1 = lhs_score(problem1, result1.history['n_train'])
fig, ax = plt.subplots(figsize=(6.4, 3.6))
ax.plot(result1.history['n_train'], result1.history['r2:' + objective], 'o-', label='adaptive (LOLA-Voronoi)')
ax.plot(lhs1.index, lhs1[(objective, 'r2')], 's--', color='grey', label='all designs at once (Latin hypercube)')
ax.set_xlabel('simulated designs used for training')
ax.set_ylabel('R$^2$ on the 15 test designs')
ax.set_title(objective)
ax.legend()
plt.show()"""),
        md("""Read the two curves before reading on. When this notebook was run (`seed=0`) neither of them fell steadily. The
adaptive error went **up** after the first iteration: the sampler puts the new designs where the surrogate knew least, far
from the ten it had, and with them the fitted surrogate changes. The Latin hypercube curve is not monotone either: a
Gaussian process fitted on few designs is sensitive to which designs it is given. So adaptive sampling does **not** promise
a better surrogate for the same number of simulations. What it gives is a way to **measure, at every step, whether you have
enough** (see the stopping rules below) and, on a harder problem, designs where the response bends."""),
        md("""### Where did the sampler look?

On the plane of the two parameters that matter most for the heating demand (notebook 2): the designs of `initial` (grey),
and the ones added by the sampler, numbered in the order they were simulated."""),
        code("""x, y = 'Window-to-wall ratio', 'Glazing solar transmittance'
new1 = result1.data.iloc[len(initial):]
fig, ax = plt.subplots(figsize=(5.6, 4.6))
ax.scatter(initial[x], initial[y], color='grey', label='initial designs')
ax.scatter(new1[x], new1[y], color='red', label='added by the sampler')
for i, (a, b) in enumerate(zip(new1[x], new1[y]), 1):
    ax.annotate(str(i), (a, b), textcoords='offset points', xytext=(4, 4), fontsize=7)
ax.set_xlabel(x)
ax.set_ylabel(y)
ax.legend(fontsize=8, loc='upper left', bbox_to_anchor=(1.02, 1))
plt.show()"""),
        md("""The same designs with all five variables, reduced to two dimensions by multi-dimensional scaling (MDS): points that are
close here are close in the design space."""),
        code("""from sklearn.manifold import MDS
from sklearn.preprocessing import StandardScaler

P = problem1.encode(result1.data)                  # every training design in the unit cube; the initial ones first
mds = MDS(n_components=2, init='random', random_state=1).fit_transform(StandardScaler().fit_transform(P))
n0 = len(initial)
plt.scatter(mds[:n0, 0], mds[:n0, 1], color='grey')
plt.scatter(mds[n0:, 0], mds[n0:, 1], color='r')
plt.axis('equal')
plt.show()"""),
        md("""The map of the explorer of notebook 2, now on the surrogate that the sampler built: the white dots are the designs it
trained on."""),
        code("""ex1 = explore.ParameterExplorer(result1.surrogate, problem1, training=result1.data)
ex1.widget"""),
        md("""**Your turn.** *Map* tab: x = window-to-wall ratio, y = glazing solar transmittance. Do the designs added by the
sampler (they are among the white dots) sit where the colours change fast, or where the dots were few? Which of the two
ideas of the score, exploration or exploitation, do you see? And why might the error of the sampler's surrogate *rise* after the
first iteration (look at the curve above and at where the first new designs went)?"""),
        md("""# Part 2 · Several objectives

The design problem of notebook 3 has three objectives, so the surrogate must be good for all of them. What changes in the
sampler, in `bdopt.adaptive` (nothing changes in how you call it):

- `GPSurrogate` fits **one Gaussian process per objective**;
- before the LOLA-Voronoi score is computed, every objective is scaled to the same spread, and the deviation of the response
  from a plane is **summed over the objectives**: a region is interesting if *any* of them bends there, and the objective
  that happens to be in the largest unit does not dominate;
- the stopping error, `scaled_rmse`, is the test RMSE in units of the standard deviation of each objective, **averaged over the
  objectives**; `history` keeps the $R^2$ of each one."""),
        code("""evaluator3 = EnergyPlusEvaluator(problem, idf, epw_file, out_dir='/tmp/bdopt_runs', err_dir='outputdir', processes=2)
sampler3 = AdaptiveSampler(problem, evaluator3, method='flola_voronoi', surrogate=GPSurrogate(), seed=0)
result3 = sampler3.run(initial_data=initial, test_data=test, max_iter=N_ITER, batch=BATCH, tol=0, verbose=False)
print(result3)
print(evaluator3.stats())
result3.history[['iteration', 'n_train', 'scaled_rmse'] + ['r2:' + o for o in objectives]]"""),
        md("""One panel per objective, the adaptive run against the Latin hypercube of the same size (the same GP, the same test
designs):"""),
        code("""lhs3 = lhs_score(problem, result3.history['n_train'])
fig, axes = plt.subplots(1, 3, figsize=(13, 3.4), sharey=True)
for ax, o in zip(axes, objectives):
    ax.plot(result3.history['n_train'], result3.history['r2:' + o], 'o-', label='adaptive')
    ax.plot(lhs3.index, lhs3[(o, 'r2')], 's--', color='grey', label='Latin hypercube')
    ax.set_title(o.replace(':Facility', ''))
    ax.set_xlabel('simulated designs')
axes[0].set_ylabel('R$^2$ on the test designs')
axes[0].legend()
plt.show()"""),
        code("""final = len(result3.data)
pd.DataFrame({
    'adaptive, 3 objectives': result3.surrogate.score(test[problem.parameter_names + objectives])['rmse_pct'],
    'Latin hypercube': lhs3.loc[final].xs('rmse_pct', level=1),
}).round(2)         # RMSE on the test designs, % of the mean of each objective"""),
        md("""Does the choice of the objectives change where the sampler looks? The designs added in part 1 (heating only) and in
part 2 (the three together), on the same plane:"""),
        code("""new3 = result3.data.iloc[len(initial):]
fig, ax = plt.subplots(figsize=(5.6, 4.6))
ax.scatter(initial[x], initial[y], color='grey', label='initial designs')
ax.scatter(new1[x], new1[y], color='red', label='part 1: heating only')
ax.scatter(new3[x], new3[y], color='blue', marker='^', label='part 2: three objectives')
ax.set_xlabel(x)
ax.set_ylabel(y)
ax.legend(fontsize=8, loc='upper left', bbox_to_anchor=(1.02, 1))
plt.show()"""),
        md("""**Your turn.**
- Why is the electricity's $R^2$ already 1.0 with the 10 initial designs, whatever the sampler does afterwards? (Think of what it depends on: notebook 2.)
- The sampler added designs in the same regions in the two runs, or not? Which objective do you think pulled the choice?
- Re-run part 2 with `seed=1`: how different are the curves? What does it say about comparing two methods on one run?"""),
        md("""## When to stop, and other methods

`run` stops when any of these is reached (the `stop_reason` of the result says which):

- `tol`: the test `scaled_rmse` is small enough (here switched off with `tol=0`; the default is 0.05);
- `max_iter` iterations, or `max_evaluations` simulations;
- `patience=k`: the best error has not improved by more than `min_improvement` (2 % by default) over the last `k` iterations;
- `max_std=eps`: the surrogate's own uncertainty over the whole design space is below `eps` (needs a surrogate with
  uncertainty, like the Gaussian process).

All the others the sampler knows are in `METHODS`:"""),
        code("METHODS"),
        md("""**Your turn.** Repeat part 1 with `method='voronoi'` (pure exploration: no exploitation term), with `'gp_variance'`
(the design where the Gaussian process is least sure) or with `'random'` (the baseline), keeping `seed`, `N_ITER` and `BATCH`:
which curve is best at the end? Then add `patience=2` and `tol=0.2` to `run`: how many simulations does the sampler spend
before it decides that it is enough? (Designs already simulated are taken from the cache, not simulated again.)"""),
        md("""## Summary
- **Adaptive sampling** chooses the next simulations from what the previous ones showed: **exploration** (empty parts of
  the design space) and **exploitation** (where the response bends).
- The error is measured at every step on designs the surrogate has never seen, so the loop can **stop when it is enough**.
- With **several objectives** the sampler scales them to the same spread and looks where *any* of them bends.
- It does not always beat a Latin hypercube of the same size: compare them on the same test designs, and do not trust a single
  run.
- `result3.surrogate` is an ordinary bdopt surrogate: it can go into `nsga2` exactly as in notebook 3.

That completes the series. The laboratory notebooks of the course use the same tools on a larger model."""),
    ]
