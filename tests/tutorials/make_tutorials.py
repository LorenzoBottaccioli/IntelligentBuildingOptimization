"""Builds the three tutorial notebooks of the demo session from the bdopt ports in course_notebooks_bdopt/.

    python tests/tutorials/make_tutorials.py

Writes tutorials/{1_bdopt_overview,2_surrogate_modelling,3_optimization}.ipynb and copies the
data they need next to them (test.idf, the Turin EPW, window_to_wall.py, image/). It never touches the source notebooks
and never deletes anything: an existing file of the same name is overwritten, nothing else.

tutorials/ is the source of the course material. It is not inside backend/surrogate_notebooks/ on purpose: that folder is the
students' working state, which opening or resetting a session empties. The demo session (backend/seed_sessions/bdopt-demo)
carries a copy of tutorials/ in state/surrogate_notebooks/tutorials, which is what the Tutorials page opens.

Each edit names the cell it changes by index AND by the first characters of its source, so a change of the source notebook
makes the script stop instead of patching the wrong cell.
"""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "course_notebooks_bdopt"
DST = ROOT / "tutorials"
BESOS = Path(r"C:\Users\Lorenzo\Documents\python_envs\virtual_BMS_simulator\data\notebooks\besos")


def _lines(text):
    parts = text.strip("\n").split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": _lines(text)}


def src(cell):
    return "".join(cell["source"])


def patch(name, replace=None, before=None, after=None):
    """replace/before/after: {index: (expected_prefix, cell | [cells] | None)}; before/after: {index: (prefix, [cells])}."""
    nb = json.loads((SRC / name).read_text(encoding="utf8"))
    cells = nb["cells"]
    replace, before, after = replace or {}, before or {}, after or {}
    for table in (replace, before, after):
        for i, (prefix, _) in table.items():
            assert src(cells[i]).startswith(prefix), (name, i, prefix, src(cells[i])[:60])
    out = []
    for i, c in enumerate(cells):
        out += before.get(i, (None, []))[1]
        if i in replace:
            new = replace[i][1]
            out += [] if new is None else (new if isinstance(new, list) else [new])
        else:
            out.append(c)
        out += after.get(i, (None, []))[1]
    for k, c in enumerate(out):                     # no stored outputs in the repo copies
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
        c["id"] = hashlib.md5(f"{name}-{k}".encode()).hexdigest()[:8]     # nbformat 4.5 wants an id; stable between runs
    nb["nbformat"], nb["nbformat_minor"] = 4, 5
    nb["cells"] = out
    nb["metadata"].setdefault("kernelspec", {"display_name": "Python 3", "language": "python", "name": "python3"})
    return nb


def save(nb, name):
    (DST / name).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf8")


GLOSSARY = """### Words used in this course

| Term | Meaning in bdopt |
|---|---|
| **Selector** | says *where* in the building model a value is written (a field of one or more objects, or a function that edits the model) |
| **Descriptor** | says *which values* are allowed: `RangeParameter` (an interval), `IntegerParameter` (whole numbers), `CategoryParameter` (a list) |
| **Parameter** (design variable) | a selector plus a descriptor, with a name: one column of the table of designs |
| **Objective** | a quantity read from the simulation results, for example an energy meter |
| **Problem** | parameters + objectives |
| **Evaluator** | turns a table of designs into a table of objectives: by simulating (`EnergyPlusEvaluator`) or with a Python function (`FunctionEvaluator`) |
| **Sample** | one design (one row); *sampling* means choosing many designs to evaluate |
| **Surrogate** | a fast statistical model trained on simulated samples, used in place of the simulator |
| **Pareto front** | the designs that no other design beats on every objective at once |
"""

NEXT_STEPS = {
    1: "Next: **2_surrogate_modelling.ipynb** trains surrogate models on simulated samples.",
    2: "Next: **3_optimization.ipynb** uses the surrogate to search for the best designs.",
    3: "Next: **4_adaptive_sampling.ipynb** lets the sampler choose which simulations to run.",
}


def header(n, title, goal, needs, time):
    return md(f"""# {n} · {title}

**What you will do.** {goal}

**You need.** {needs}

**Run time.** {time}

The four notebooks of this series use the same building model (`test.idf`, a small house) and the same weather file
(Turin). Work in order: 1 *bdopt overview* → 2 *surrogate modelling* → 3 *optimization* → 4 *adaptive sampling*. Cells
marked **Your turn** are exercises: change something and observe what happens.""")


def build_overview():
    r = {}
    b = {}
    a = {}
    b[0] = ("%matplotlib inline", [header(
        1, "bdopt overview",
        "Read an EnergyPlus model, say which of its values you want to vary, say what you want to measure, simulate a "
        "few designs and look at how the inputs relate to the results.",
        "Nothing else: this is the first notebook. `test.idf`, the weather file and `window_to_wall.py` are in this folder.",
        "about 4 minutes (it runs 12 one-year EnergyPlus simulations, two at a time).")])
    a[3] = ("![Image]", [md(GLOSSARY)])
    r[4] = ("# bdopt Tutorial Analysis", md(
        "## What this notebook does\n"
        "It performs a parametric analysis of a building design with EnergyPlus and bdopt. We load the model "
        "`test.idf`, define the parameters to vary and the objectives to measure, run the model for a single design and "
        "then for a set of samples, and plot the results."))
    r[18] = ("# Evaluators", md(
        "# Evaluators\n\n"
        "An *evaluator* turns a table of designs (one column per parameter) into a table of results (one column per "
        "objective). `bdopt` provides:\n"
        "- the EnergyPlus evaluator (`EnergyPlusEvaluator`): simulates every design\n"
        "- the function evaluator (`FunctionEvaluator`): computes the objectives with a Python function (a formula, a "
        "surrogate model, another simulator)"))
    a[51] = ("for key, value in values.items()", [
        md("""**Your turn.** Evaluate the model with an insulation thickness of 0.05 m and of 1.0 m and compare the three objectives.
Which one changes most? Does more insulation always reduce the total energy? Think about what insulation does in summer."""),
        code("# your code here: evaluator([...])")])
    r[64] = ("### Several fields of an object", md(
        "### Several fields of an object, several objects\n\n"
        "bdopt has no short-cut that builds many parameters from a dictionary: you write one `Parameter` per variable, "
        "with the class of the object. This also avoids the ambiguity of an object name that exists in two classes.\n\n"
        "The glazing material `3` of this model has a `Conductivity` and a `Solar Transmittance at Normal Incidence`:"))
    r[69] = ("### Parameter scripts using a Generic Selector", md(
        "### Parameter scripts using a Generic Selector\n\n"
        "A parameter can also be defined by a function that takes the model and a value and edits the model. These "
        "functions are specific to the format of a model and can perform any transformation. In bdopt this is a "
        "`GenericSelector(setter)`: `setter(idf, value)` is called, on a copy of the model, with the value of the "
        "parameter.\n\n"
        "A window-to-wall ratio changes the geometry, not a single field, so it is written as a `GenericSelector`. The "
        "course provides it in a small file next to this notebook, `window_to_wall.py`: it scales the windows of every "
        "outdoor wall about their own centre until the windows of that wall add up to the requested fraction of the "
        "wall. It creates and deletes nothing. It is meant for models whose windows can grow in place: on `test.idf` "
        "every ratio up to 0.83 fits. For a ratio that the windows cannot reach without leaving their wall or "
        "overlapping another window or a door, the setter raises a `ValueError` instead of writing a wrong model. "
        "The limits are at the top of the file (cell below).\n\n"
        "Two things to keep in mind. The ratio is imposed wall by wall on the walls that already have windows, so the "
        "ratio of the whole building is lower when some wall has none. And EnergyPlus' own report of the window-to-wall "
        "ratio counts the window frame: asking 0.5 on `test.idf` gives 52.4 % in its `EnvelopeSummary` table. It is a "
        "tool for the models of this course, not a general one."))
    r[93] = ("### Correlation heat map", md(r"""### Correlation heat map
Another way to analyse the impact of the inputs on the outputs is by analysing the correlation.
A common metric is the Pearson correlation coefficient:

$$ r = \frac{N\sum XY - \sum X \sum Y}{\sqrt{\left[N\sum X^2 - \left(\sum X\right)^2\right]\left[N\sum Y^2 - \left(\sum Y\right)^2\right]}} $$

where $N$ is the number of samples, $X$ is the vector of observations of variable 1 (e.g. the insulation thickness) and $Y$ is
the vector of observations of variable 2 (e.g. the heating demand).
The closer $r$ is to one the stronger the correlation, and similarly for negative one and negative correlation.

To visualize the correlation coefficients of all inputs and outputs, we can plot a heatmap:"""))
    a[80] = ("samples = sampling.lhs(problem, 10, seed=0)", [
        md("""### Which designs to simulate?

A one-year simulation of this small house takes about 14 seconds, a large building minutes, and a study needs hundreds of them: we want few designs that still *cover* the design space.
- **Full factorial** tries every combination of a few levels per variable: simple, but the number of designs grows as `levels ** variables`.
- **Latin hypercube (`lhs`)** divides the range of every variable in `n` slices and uses each slice exactly once: `n` designs for any number of variables.
- **Sobol** and **Halton** are low-discrepancy sequences: they fill the space evenly and can be extended with more points.

Below, 16 designs chosen by each method, seen on two of the variables. Random points (grey) leave gaps and clusters."""),
        code("""fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharex=True, sharey=True)
x_name, y_name = problem.parameter_names[0], problem.parameter_names[3]
x_range, y_range = problem.parameters[0].value_descriptor, problem.parameters[3].value_descriptor
rng = np.random.default_rng(0)
axes[0].scatter(rng.uniform(x_range.min, x_range.max, 16), rng.uniform(y_range.min, y_range.max, 16), color='grey')
axes[0].set_title('random')
for ax, (label, function) in zip(axes[1:], {'lhs': sampling.lhs, 'sobol': sampling.sobol, 'halton': sampling.halton}.items()):
    s = function(problem, 16, seed=0)
    ax.scatter(s[x_name], s[y_name])
    ax.set_title(label)
for ax in axes:
    ax.set_xlabel(x_name)
axes[0].set_ylabel(y_name)
plt.show()"""),
        md("The simulated designs below use `lhs`.")])
    a[96] = ("viz.correlation_heatmap", [md("""**Your turn.** Which input has the strongest effect on the heating demand, and on the cooling demand? Does it agree with what you expect from physics?
With only 10 samples, how much do you trust a correlation of 0.3? Repeat the study with `sampling.lhs(problem, 10, seed=1)` and see whether the answer changes."""),
        md("""## Summary
- A **model** is read with `load_idf`; its fields are named by the EnergyPlus IDD.
- A **parameter** = selector (where) + descriptor (which values); a **problem** = parameters + objectives.
- An **evaluator** = problem + building + weather; `EnergyPlusEvaluator` simulates, `FunctionEvaluator` computes.
- **Sampling** chooses the designs to evaluate; plots and correlations show which inputs matter.

""" + NEXT_STEPS[1])])
    return patch("Besos_overview.ipynb", replace=r, before=b, after=a)


def build_surrogate():
    r, b, a = {}, {}, {}
    b[0] = ("# Surrogate Modelling with bdopt", [header(
        2, "Surrogate modelling",
        "Simulate a set of designs, train statistical models on the results, compare them on data they have not seen, "
        "and keep the best one for the optimization.",
        "Notebook 1 (the vocabulary: parameter, problem, evaluator, sampling). The simulated samples of the second part "
        "are stored in `surrogate_simple_simulation.csv`, so you do not have to wait for them.",
        "about 3 minutes with the stored simulations. With `RESIMULATE = True` (below) it runs the 50 simulations of "
        "part 2 itself: about 16 minutes in all.")])
    r[0] = ("# Surrogate Modelling with bdopt", md("""## Why a surrogate?

Surrogate modelling or metamodelling is a way to emulate physics-based building simulation models [[1]]. A one-year
EnergyPlus simulation takes tens of seconds to minutes; a design study or an optimisation needs thousands of
evaluations. A surrogate is trained on a few hundred simulations and then answers in milliseconds.

bdopt integrates building simulation and surrogate modelling using:
+ EnergyPlus model editing and execution via evaluators (`EnergyPlusEvaluator`)
+ sampling (`bdopt.sampling`, built on [scipy](https://docs.scipy.org/doc/scipy/reference/stats.qmc.html))
+ machine learning with [scikit-learn](https://scikit-learn.org/stable/) (`bdopt.surrogate`)

[1]: https://doi.org/10.1016/j.enbuild.2019.05.057 (Westermann, P., Evins, R. (2019). Surrogate modelling for sustainable building design - a review. Energy and Buildings 198, 170-186.)"""))
    r[1] = ("## Surrogate Modelling workflow", md("""## The workflow

The figure shows the workflow of a surrogate-based design study and, next to the boxes, the parts of bdopt that
do each step. This notebook covers the first four boxes: the problem (notebook 1), the samples, the surrogate that is
fitted to them, and its validation. The last box, design optimization, is notebook 3.

The dashed arrows say that the study is not a straight line: if the surrogate is not accurate enough, or the optimiser
needs more accuracy where it is looking, you go back and simulate more designs. The grey boxes are other uses of a
validated surrogate, which these notebooks do not develop."""))
    r[2] = ("![Image]", md("![The workflow of a surrogate-based design study](image/surrogate_overview.png)"))
    r[3] = ("# Surrogate Modelling Work Flow", md("""### The steps

+ define a problem consisting of parameters to vary with ranges and an objective function
+ sample the problem space
+ define an evaluator by linking the problem to an EnergyPlus model
+ run the evaluator for the samples
+ train a surrogate model over the samples
+ explore the design space using an interactive plot that queries the surrogate model"""))
    r[4] = ("%matplotlib inline", code("""%matplotlib inline
import time
from pathlib import Path

import numpy as np
import pandas as pd
from ipywidgets import FloatSlider, interact
from matplotlib import pyplot as plt
from sklearn import linear_model, pipeline
from sklearn.preprocessing import StandardScaler

from bdopt import (EnergyPlus, EnergyPlusEvaluator, FieldSelector, FunctionEvaluator, IntegerParameter,
                   Parameter, Problem, RangeParameter, load_idf, sampling, viz)
from window_to_wall import wwr      # the window-to-wall ratio as a design variable: see 1_bdopt_overview.ipynb

N_SAMPLES = 50          # simulations of the second part of the notebook
RESIMULATE = False      # False: use the stored simulations (surrogate_simple_simulation.csv); True: run them yourself (~10 min)"""))
    r[7] = ("## Parameters and Objectives", md("""## Parameters and Objectives
We start by defining `Parameters` that govern how we would like to modify the building.
Here they are the thickness of the insulation layer and the window-to-wall ratio. The first is a field of a material,
written with a `FieldSelector`; the second is a geometry edit, written as a `GenericSelector` in `window_to_wall.py`
(see `1_bdopt_overview.ipynb`)."""))
    r[11] = ("## Sampling", md("""## Sampling

We need samples on which to train a surrogate model. The sampler uses Latin Hypercube Sampling: each variable's range
is cut in as many slices as there are samples and every slice is used once, so the designs are spread over the whole
design space. A `seed` makes the choice repeatable. We can check how well distributed they are by looking at the table."""))
    a[22] = ("viz.pairplot(train, problem, size=3)", [md("""**Your turn.** Does more insulation always lower the heating demand? What does the plot say about the window-to-wall ratio?
With only 10 samples, could you be fooled? Keep this question in mind for the second part.""")])
    r[28] = ("model = pipeline.make_pipeline", code("""model = pipeline.make_pipeline(StandardScaler(), linear_model.LinearRegression())
model.fit(train[[x, y]].values, train[obj].values)
print('R2 on the training data:', round(model.score(train[[x, y]].values, train[obj].values), 3))"""))
    r[38] = ("Let's compare now a Gaussian Process", None)       # said by the heading of part 2 just above
    b[5] = ("## Building model", [md("# Part 1 · A first surrogate, with two variables")])
    r[37] = ("# GP vs Neural Network", md("""# Part 2 · Gaussian process vs neural networks

Let's compare now a Gaussian process with a neural network and a deeper network for surrogate model creation, on a more
complex design space: five design variables and three objectives, trained on **50** simulated designs.

If a model fits the 10 designs it was trained on, that proves nothing: it may have memorised them. What matters is the
error on designs it has *never seen*, so we keep part of the simulations aside as a test set."""))
    r[46] = ("samples = sampling.lhs(problem, 20, seed=0)", code("samples = sampling.lhs(problem, N_SAMPLES, seed=0)\nsamples.head()"))
    r[47] = ("evaluator = EnergyPlusEvaluator", code("""evaluator = EnergyPlusEvaluator(problem, idf, epw_file,
                                out_dir='/tmp/bdopt_runs',   # work files go to the container's own disk (the shared folder is much slower)
                                err_dir='outputdir',         # runs that fail are kept here, with the EnergyPlus error file
                                processes=2)

saved = Path('surrogate_simple_simulation.csv')
sim_samples = None
if saved.exists() and not RESIMULATE:
    table = pd.read_csv(saved, index_col=0)
    if list(table.columns) == problem.names():          # a file written for another problem is ignored
        sim_samples = table
        print(f'Using the {len(sim_samples)} simulations stored in {saved}.')
if sim_samples is None:
    print(f'Simulating {len(samples)} designs (about 12 minutes)...')
    t1 = time.time()
    sim_samples = evaluator.evaluate(samples, keep_input=True)
    hours, mins, secs = niceformat(time.time() - t1)
    print("The total running time: {:2.0f} hours {:2.0f} min {:2.0f} seconds".format(hours, mins, secs))
    sim_samples.to_csv(saved)"""))
    a[51] = ("# remove outputs", [md("""### Which variables matter?

Before training anything, look at how each objective responds to each variable (Pearson correlation, from -1 to 1). Everything a surrogate has to learn is in this table."""),
        code("sim_samples.corr().loc[objectives, features].round(2)"),
        md("""In this model the electricity consumption depends on the lighting power alone (correlation 1.00): there is nothing to learn there, and the models will get that objective right. Heating and cooling are driven mostly by the window-to-wall ratio and by the glazing: that is where the models differ.""")])
    r[52] = ("## Train-test split", md("""## Train-test split

Next we split the data into a training set (80%, 40 designs) and a testing set (20%, 10 designs). The test designs are
never used to fit anything: they only measure how the models behave on new designs."""))
    r[55] = ("To ensure an equal weighting", md("""To ensure an equal weighting of inputs and outputs in the training of the networks, we normalise the values.
For example the window-to-wall ratio is in the range of 0 to 1 while the lighting power is in a range of 8 to 12 W/m$^2$.
Different options for normalisation exist. Here we bring every variable to zero mean and standard deviation 1.

**Fit the normaliser on the training data only, and only *apply* it to the test data.** If the test data took part in
computing the mean and standard deviation, information about the test set would leak into the model and the test error
would look better than it really is."""))
    a[75] = ("def rmse_percent", [md("""A model with an error of a few percent of the mean is usually good enough to rank designs. With 10 test designs the comparison is only indicative: change `random_state` in `train_test_split` and see whether the ranking of the models changes.

### The same models with `bdopt.surrogate`

`bdopt.surrogate` offers these models ready-made. They scale inputs and outputs inside, so the normalisation, the grid search and the split bookkeeping above disappear, and `score` gives the same percentage error."""),
        code("""from bdopt.surrogate import GPSurrogate, MLPSurrogate

train_df = pd.concat([train_in, train_out], axis=1)
test_df = pd.concat([test_in, test_out], axis=1)

bdopt_models = {'GP': GPSurrogate(), 'NN': MLPSurrogate(random_state=0)}
for model_ in bdopt_models.values():
    model_.fit(train_df, problem)

pd.DataFrame({name: m.score(test_df)['rmse_pct'] for name, m in bdopt_models.items()})"""),
        code("""# predicted against simulated, on the test designs (points on the diagonal are perfect predictions)
viz.parity(test_out, bdopt_models['GP'].predict(test_in))
plt.show()"""),
        md("**Your turn.** Which surrogate would you use? Try `make_surrogate('random_forest')` (see `help(make_surrogate)` for the other names) and compare it in the same way.")])
    r[79] = ("## Exploration", md("""## Exploration

A brushable parallel-coordinates plot, as in the original course notebooks: one line per design (500 designs answered by
the neural network), one axis per variable, coloured by the electricity use. **Drag on an axis** to keep only the designs
whose value lies in that range: select the lowest heating demand and see which values of the parameters go with it.
Drag the range to move it, click on the axis to remove it, drag the title of an axis to put it elsewhere."""))
    r[80] = ("viz.parallel_coordinates(srresults", code("""import explore       # explore.py, next to this notebook: the tools of the next part

explore.parallel_coordinates(srresults, problem, color='Electricity:Facility').show()"""))
    b[81] = ("## Save the surrogate", [
        md("""# Part 3 · Looking inside the surrogate

A surrogate is a function that answers in milliseconds, so you can ask it anything. Here are four ways of looking inside.
They are all in `explore.py` (open it from the Jupyter file list: it is plain Python). For this part we train a Gaussian
process on all 50 simulations, because it can also say **how sure it is** of each prediction."""),
        code("""from bdopt.surrogate import GPSurrogate

gp = GPSurrogate().fit(sim_samples, problem)         # all 50 simulated designs
print('Can the model say how sure it is?', gp.has_uncertainty)"""),
        md("""### 1 · Move the parameters

One slider per parameter. The tabs show, for the design you build: the **Prediction** (bars, with the model's uncertainty as
error bars, and the range of the simulated designs in grey), the **Sections** (each objective against each parameter, the
others kept where the sliders are), a **Map** of two parameters (switch to *uncertainty* to see where the model is unsure)
and a **Compare** of two saved designs."""),
        code("""ex = explore.ParameterExplorer(gp, problem, training=sim_samples)
ex.widget"""),
        md("""**Your turn.**
- Move the window-to-wall ratio. What happens to cooling? And to heating? Does it agree with the *Sections* tab?
- *Map*: x = window-to-wall ratio, y = glazing solar transmittance, objective = cooling. Then switch to *uncertainty*: where is the model least sure? (Far from the white dots, the simulated designs.) Where would you simulate next?
- Press *Save as A*, change two parameters, press *Save as B*: the *Compare* tab gives the difference in kWh and in %.
- `ex.design` is the design you have built, as a dictionary: you can hand it to `EnergyPlusEvaluator.evaluate` to check the prediction."""),
        md("""### 2 · Which parameters matter?

Two answers. The **tornado**: starting from the middle of every range, how far does each objective move when *only* one parameter goes from its minimum to its maximum? The **Sobol' indices**: the share of the variance of an objective that a parameter explains *alone* (S1) and *together with the others* (ST); an ST much larger than S1 means the parameter acts through an interaction. With the surrogate this takes seconds (about 14 000 evaluations): with EnergyPlus it would take days."""),
        code("explore.tornado(gp, problem)"),
        code("""S1, ST = explore.sobol_indices(gp, problem)
explore.sensitivity_plot(S1, ST)
pd.concat({'S1': S1, 'ST': ST}, axis=1).round(2)"""),
        md("""**Your turn.** Which parameter would you stop worrying about? Which two parameters interact (ST well above S1)? Compare with the correlation table you looked at before: what does a correlation miss?"""),
        md("""### 3 · Does the surrogate need more simulations?

Train on 10, 20, 30, 40 designs, always testing on designs that were left out, with a few random choices of the training designs for each size. If the error keeps falling, more simulations would still help; if the curve is flat, they would not."""),
        code("explore.learning_curve(lambda: GPSurrogate(), sim_samples, problem, sizes=(10, 20, 30, 40), repeats=2)"),
        md("""**Your turn.** What would you do with a budget of 20 more simulations? (The *uncertainty* map points at where; the adaptive sampler of bdopt, `bdopt.adaptive`, does it automatically: notebook 4.)""")])
    r[81] = ("## Save the surrogate", md("""## Save the surrogate

`3_optimization.ipynb` uses a surrogate stored in a file. bdopt surrogates scale their inputs and outputs inside, so the
file is all that is needed (no separate scalers). The one below is the neural network with its grid search, trained on
**all** the simulations (train and test: once the model is chosen, every simulation helps)."""))
    a[82] = ("from bdopt.surrogate import MLPSurrogate", [md("## Summary\n- Simulated samples are the expensive part; a **surrogate** trained on them answers instantly.\n- Judge a model on **data it has not seen**; fit the normaliser on the training data only.\n- With few samples the comparison between models is only indicative.\n\n" + NEXT_STEPS[2])])
    return patch("Surrogate_Modelling.ipynb", replace=r, before=b, after=a)


def build_optimization():
    r, b, a = {}, {}, {}
    b[0] = ("# Building Optimization", [header(
        3, "Optimization",
        "Search the design space for the best designs: first with EnergyPlus alone (slow), then with the surrogate "
        "(fast), and finally check the best design with a real simulation.",
        "Notebook 1 (vocabulary). Part B needs the simulations and the surrogate of notebook 2: they are stored in this "
        "folder (`surrogate_simple_simulation.csv`, `best_surrogate.pkl`); if the surrogate file is missing it is trained again.",
        "about 8 minutes in all (part A runs about 30 simulations). With `FULL_STUDY = True` part A runs 200: "
        "plan for about 45 minutes (a simulation takes about 14 seconds when two run at a time).")])
    r[0] = ("# Building Optimization", md("""## Multi-objective optimisation

Designs usually have to satisfy conflicting objectives: for example less heating demand tends to mean more cooling demand
in summer. There is no single best design but a set of **non-dominated** designs, the *Pareto front*: none of them is
better than another on every objective at once. We find it with a genetic algorithm, NSGA-II."""))
    r[1] = ("This notebook performs building design optimization", md("""**Part A** runs the optimiser directly on EnergyPlus: every design the algorithm tries is simulated.
**Part B** trains nothing new (unless the saved surrogate is missing): it loads the surrogate of notebook 2 and lets the algorithm try thousands of designs, then verifies the best one with EnergyPlus.
Part B does not depend on part A: you can start from the heading *Part B*."""))
    r[3] = ("%matplotlib inline", code("""%matplotlib inline
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from bdopt import (EnergyPlus, EnergyPlusEvaluator, FieldSelector, FunctionEvaluator, IntegerParameter,
                   Parameter, Problem, RangeParameter, load_idf, sampling, viz)
from bdopt.optimize import nsga2
from bdopt.surrogate import MLPSurrogate, Surrogate
from window_to_wall import wwr      # the window-to-wall ratio as a design variable: see 1_bdopt_overview.ipynb

FULL_STUDY = False      # False: a small population and few generations (about 30 simulations); True: 200 simulations (~45 min)"""))
    b[2] = ("### Import libraries", [md("# Part A · optimisation with EnergyPlus")])
    r[6] = ("### Define design parameters and ranges", md("""### Define design parameters and ranges
Define a parameter list, in this case the thickness of an insulation layer and the window-to-wall ratio: a field of a material (`FieldSelector`) and a geometry edit (`wwr`, a `GenericSelector` in `window_to_wall.py`)."""))
    r[14] = ("## Run the Genetic Algorithm", md("""## Run the Genetic Algorithm
`nsga2` takes the problem and *what evaluates it*: here the EnergyPlus evaluator, so every design the algorithm tries is simulated (a full year each; each generation runs `pop_size` simulations, in parallel, and a design already simulated is taken from the cache).

To keep the lecture short we use a population of 10 designs for 3 generations (about 30 simulations); a real study needs much more (`FULL_STUDY = True`). To plot every design that was tried, and not only the best ones, the evaluator is wrapped in a function that records what it computes: any Python function can play the role of an evaluator."""))
    r[16] = ("front = nsga2(problem, recording_evaluator, pop_size=10, n_gen=3, seed=0)", code("""POP_SIZE, N_GEN = (20, 10) if FULL_STUDY else (10, 3)
front = nsga2(problem, recording_evaluator, pop_size=POP_SIZE, n_gen=N_GEN, seed=0)
results = pd.concat(tried, ignore_index=True).drop_duplicates()
front.df"""))
    a[19] = ("optres = optres.sort_values", [md("""**Your turn.** Read the plot: moving along the front from the left to the right, what do you gain and what do you lose? Which design would you build, and why?""")])
    r[20] = ("### Giving constraints to the optimization", md("""### Giving constraints to the optimization

bdopt constrains the *design variables*: `Problem(parameters, objectives, constraints=[g])`, where `g(design)` receives a design (a dictionary parameter name -> value) and returns a number; the design is feasible when the number is `<= 0`. Samplers only draw feasible designs and the optimisers respect the constraint. There is an example at the end of part B."""))
    r[21] = ("## Optimization with Surrogate Model", md("""# Part B · optimisation with the surrogate

Simulating every design the algorithm tries is slow. A surrogate model trained on a few simulations answers in milliseconds, so the algorithm can try thousands of designs. Notebook 2 produced two files: the simulations (`surrogate_simple_simulation.csv`) and the trained surrogate (`best_surrogate.pkl`)."""))
    r[22] = ("# the simulations the surrogate was trained on", code("""# the simulations the surrogate was trained on (stored in this folder, written by 2_surrogate_modelling.ipynb)
import os

if not os.path.exists('surrogate_simple_simulation.csv'):
    raise FileNotFoundError(
        f"surrogate_simple_simulation.csv not found in {os.getcwd()}. It is written by 2_surrogate_modelling.ipynb: "
        "open it and run it from the top to the end, then come back here.")
samples = pd.read_csv('surrogate_simple_simulation.csv', index_col=0)
samples"""))
    r[23] = ("The problem is the one of", md("The problem is the one of `2_surrogate_modelling.ipynb`: five design variables and three objectives."))
    r[24] = ("parameters = [\n    Parameter(FieldSelector('Material'", code("""parameters = [
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
problem = Problem(parameters, objectives)

features = problem.parameter_names

# the table must have the columns of this problem
absent = [n for n in features + objectives if n not in samples.columns]
if absent:
    raise ValueError(
        f"surrogate_simple_simulation.csv has the columns {list(samples.columns)}, but this problem needs {absent} as well. "
        "The file was written for another problem: run 2_surrogate_modelling.ipynb again from the top to the end "
        "(with RESIMULATE = True), and come back here.")
inputs = samples[features]
outputs = samples[objectives]
inputs.head()"""))
    r[25] = ("Load the surrogate.", md("Load the surrogate. bdopt surrogates scale their inputs and outputs inside, so no scaler has to be rebuilt. If the file is missing, or does not match this problem, the surrogate is trained again on the stored simulations (about a minute)."))
    r[26] = ("try:\n    surrogate = Surrogate.load", code("""try:
    surrogate = Surrogate.load('best_surrogate.pkl', problem)
    predicted = surrogate.predict(inputs)
    # the surrogate was trained on these very simulations, so it must be close to them (a file from another problem, or an
    # old scikit-learn pickle, loads without complaint and gives numbers that mean nothing)
    error = np.abs((np.asarray(predicted) - outputs.to_numpy()) / outputs.to_numpy()).mean()
    if not error < 0.5:
        raise ValueError(f"on the simulations it was trained on the surrogate is off by {100 * error:.0f}% on average")
except Exception as e:
    print(f"best_surrogate.pkl could not be used ({type(e).__name__}: {e}); training the surrogate on the stored simulations instead.")
    surrogate = MLPSurrogate(random_state=0).fit(samples, problem)
surrogate.predict(inputs.head(3))       # what the surrogate says about the first three simulated designs"""))
    r[33] = ("bdopt can also pick", md("bdopt can also pick the design of the front closest to the ideal point, after scaling every objective to 0-1 over the front (so that an objective in joules does not weigh more only because of its numbers):"))
    a[34] = ("front.closest_to_ideal()", [
        md("""### Is the surrogate right? Check the chosen design with EnergyPlus

The optimiser trusted the surrogate. Before building anything, write the chosen design into the model, save it, and simulate it: the surrogate's prediction and the simulation should agree."""),
        code("""best = front.closest_to_ideal()
design = {name: float(best[name]) for name in problem.parameter_names}
design"""),
        code("""idd = EnergyPlus.find().idd
optimal = idf.copy()
problem.apply(optimal, design, idd)         # writes the design into the model, with the same selectors used to simulate
optimal.save('optimal_design.idf')"""),
        code("""check = EnergyPlusEvaluator(problem, idf, epw_file, out_dir='/tmp/bdopt_runs', err_dir='outputdir', processes=1)
simulated = check.evaluate(pd.DataFrame([design]))[objectives].iloc[0]
predicted = surrogate.predict(pd.DataFrame([design])).iloc[0]
pd.DataFrame({'surrogate [kWh]': predicted / 3.6e6, 'EnergyPlus [kWh]': simulated / 3.6e6,
              'difference [%]': 100 * (predicted - simulated) / simulated}).round(1)"""),
        md("""**Your turn.** How far is the surrogate from the simulation at the optimum? Optimisers tend to go where the surrogate is *least* accurate. What would you do to improve it (more samples near the front, a different model)?"""),
        md("""### Choose a design yourself

No design of the front is the best: it depends on how much each objective matters to *you*. Move the sliders (0 = it does not matter, 1 = it matters fully): the star marks the design that `front.closest_to_ideal(weights)` picks, in the three pairs of objectives. Under the plots: that design, and what the surrogate predicts for it. The button simulates it with EnergyPlus (about half a minute) and compares."""),
        code("""import explore       # explore.py, next to this notebook

chooser = explore.ParetoExplorer(front, problem, surrogate, evaluator=check, background=background)
chooser.widget"""),
        md("""**Your turn.** Give all the weight to the electricity: which design do you get, and what do you pay in heating and cooling? Then do the opposite. `chooser.design` is the design on the screen."""),
        md("""### Which parameter values go with the good designs?

The same brushable plot as in notebook 2, now on the designs of the front: drag on the *DistrictHeating* axis to keep the designs with the lowest heating demand and read the parameters on the left."""),
        code("explore.parallel_coordinates(front.df, problem).show()")])
    r[35] = ("### A constraint on a design variable", md("""### A constraint on a design variable

Suppose the insulation layer cannot be thicker than 0.25 m. The constraint is a function of the design: feasible when it returns a number `<= 0`."""))
    a[37] = ("plt.plot(front.df", [md("## Summary\n- A multi-objective optimisation returns a **Pareto front**, not one design: the choice among its designs is yours.\n- With a **surrogate** the algorithm can try thousands of designs; always **verify** the chosen design with a real simulation.\n- bdopt constrains **design variables**: `Problem(..., constraints=[g])`.\n\n" + NEXT_STEPS[3])])
    nb = patch("Optimization.ipynb", replace=r, before=b, after=a)
    return nb


def build_adaptive():
    """4_adaptive_sampling.ipynb: written for the series (see adaptive_cells.py), not patched from a port."""
    import adaptive_cells
    cells = adaptive_cells.cells(md, code, header)
    for k, c in enumerate(cells):
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
        c["id"] = hashlib.md5(f"4_adaptive_sampling.ipynb-{k}".encode()).hexdigest()[:8]
    kernel = {"display_name": "Python 3", "language": "python", "name": "python3"}
    return {"cells": cells, "metadata": {"kernelspec": kernel, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


WWR_DOC = '''"""Window-to-wall ratio as a design variable.

bdopt edits *fields* of the model, not geometry. A geometry edit is written as a ``GenericSelector``: a function
``setter(idf, value)`` that bdopt calls, on a copy of the model, with the value of the design variable. This file builds
one for the window-to-wall ratio.

What this setter does, wall by wall:

* it takes the outdoor walls (``BuildingSurface:Detailed`` with Surface Type = Wall and Outside Boundary Condition =
  Outdoors) that already carry windows (``FenestrationSurface:Detailed`` with Surface Type = Window);
* it scales every window of such a wall about its own centre, in the plane of the wall, by the same factor, so
  that the windows of the wall add up to ``ratio`` times the gross area of the wall (doors and glass doors count in
  the wall area, are not touched, and are not windows);
* it creates and deletes nothing: a wall without windows stays without windows;
* **it refuses a ratio it cannot reach**: if a scaled window would leave its wall or overlap another window, a door
  or a glass door, it raises ``ValueError`` and writes nothing. A window can only grow where there is room.

How far it goes. On ``test.idf``, the model of these tutorials, every ratio from 0.05 to 0.83 can be reached (the two
windows of its west wall meet above that), which is why the notebooks use the range 0.1 to 0.8. Another model has other
limits: ``wwr()`` takes the range as an argument, so choose it for your model, and the setter tells you when a ratio
cannot be reached. The field positions are those of EnergyPlus 9.6 (see the constants), so the model must be a 9.6 model.

Two things to know when you read the numbers (checked with EnergyPlus 9.6, ``Output:Table:SummaryReports``
``EnvelopeSummary``, "Window-Wall Ratio"):

* the ratio is imposed wall by wall, on the walls that already have windows. A wall without windows stays without, so
  the ratio of the whole building is lower than the one asked for;
* EnergyPlus reports the *opening* area, which includes the window frame: at ``ratio = 0.5`` it reports 52.4 % for
  ``test.idf`` (the glass itself is 50 % of the wall).

Simulated for a year with the Torino weather file, ``test.idf`` at 0.2 / 0.5 / 0.8 gives district cooling 17.3 / 27.8 /
38.4 MWh and district heating 11.6 / 12.7 / 14.7 MWh: in this model both grow with the glass.
"""'''


def tutorial_window_to_wall(source):
    """The helper of course_notebooks_bdopt with an introduction for the tutorials (the code is not touched).

    The original introduction compares it with the old toolbox and measures other course models that are not part of the
    demo; the notebook prints this file, so the students read what is written here.
    """
    assert source.startswith('"""Window-to-wall ratio as a bdopt design variable'), source[:80]
    end = source.index('"""', 3) + 3
    return WWR_DOC + source[end:]


# ---------------------------------------------------------------------------- credits
# Every reference below was checked against Crossref, the publisher or the project's own repository (10 Oct 2026).
REFS = {
    "energyplus": "Crawley, D.B., Lawrie, L.K., Winkelmann, F.C., Buhl, W.F., Huang, Y.J., Pedersen, C.O., Strand, R.K., Liesen, R.J., "
                  "Fisher, D.E., Witte, M.J., Glazer, J. (2001). EnergyPlus: creating a new-generation building energy simulation "
                  "program. *Energy and Buildings* 33(4), 319-331. https://doi.org/10.1016/S0378-7788(00)00114-6",
    "besos": "Westermann, P., Christiaanse, T.V., Beckett, W., Kovacs, P., Evins, R. (2021). besos: Building and Energy Simulation, "
             "Optimization and Surrogate Modelling. *Journal of Open Source Software* 6(60), 2677. https://doi.org/10.21105/joss.02677",
    "review": "Westermann, P., Evins, R. (2019). Surrogate modelling for sustainable building design - a review. "
              "*Energy and Buildings* 198, 170-186. https://doi.org/10.1016/j.enbuild.2019.05.057",
    "lhs": "McKay, M.D., Beckman, R.J., Conover, W.J. (1979). A comparison of three methods for selecting values of input variables in the "
           "analysis of output from a computer code. *Technometrics* 21(2), 239-245. https://doi.org/10.1080/00401706.1979.10489755",
    "sobol": "Sobol', I.M. (2001). Global sensitivity indices for nonlinear mathematical models and their Monte Carlo estimates. "
             "*Mathematics and Computers in Simulation* 55(1-3), 271-280. https://doi.org/10.1016/S0378-4754(00)00270-6",
    "gp": "Rasmussen, C.E., Williams, C.K.I. (2006). *Gaussian Processes for Machine Learning*. MIT Press. ISBN 0-262-18253-X. "
          "https://gaussianprocess.org/gpml/",
    "sklearn": "Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. *Journal of Machine Learning Research* 12, "
               "2825-2830. https://jmlr.org/papers/v12/pedregosa11a.html",
    "nsga2": "Deb, K., Pratap, A., Agarwal, S., Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. "
             "*IEEE Transactions on Evolutionary Computation* 6(2), 182-197. https://doi.org/10.1109/4235.996017",
    "pymoo": "Blank, J., Deb, K. (2020). pymoo: multi-objective optimization in Python. *IEEE Access* 8, 89497-89509. "
             "https://doi.org/10.1109/ACCESS.2020.2990567",
    "lola": "Crombecq, K., Gorissen, D., Deschrijver, D., Dhaene, T. (2011). A novel hybrid sequential design strategy for global "
            "surrogate modeling of computer experiments. *SIAM Journal on Scientific Computing* 33(4), 1948-1974. "
            "https://doi.org/10.1137/090761811",
    "flola": "van der Herten, J., Couckuyt, I., Deschrijver, D., Dhaene, T. (2015). A fuzzy hybrid sequential design strategy for global "
             "surrogate modeling of high-dimensional computer experiments. *SIAM Journal on Scientific Computing* 37(2), A1020-A1039. "
             "https://doi.org/10.1137/140962437",
    "lola_building": "Westermann, P., Evins, R. (2019). Adaptive sampling for building simulation surrogate model derivation using the "
                     "LOLA-Voronoi algorithm. *Proceedings of Building Simulation 2019: 16th Conference of IBPSA*. "
                     "https://doi.org/10.26868/25222708.2019.211232",
}

FIGURE_CREDITS = {
    "image/flow_diagram.PNG": "Figure adapted from the BESOS documentation (Westermann et al. 2021, GPL-3.0): the names of the toolbox were changed.",
    "image/setting_up_the_evaluator.PNG": "Figure from the BESOS documentation (Westermann et al. 2021, GPL-3.0).",
    "image/surrogate_overview.png": "Figure from the course notebooks, which were written for BESOS; the names of the toolbox were corrected.",
    "image/LOLA-Voronoi.jpg": "Figure from the course notebooks, which were written for BESOS.",
}

CREDITS = {
    1: ["energyplus", "besos", "lhs", "sobol"],
    2: ["energyplus", "review", "gp", "sklearn", "lhs", "sobol"],
    3: ["energyplus", "nsga2", "pymoo"],
    4: ["energyplus", "lola", "flola", "lola_building", "gp", "lhs"],
}


def credits_cell(n):
    refs = "\n".join(f"- {REFS[k]}" for k in CREDITS[n])
    return md(f"""## Sources and credits

**Origin of this series.** The four notebooks are adapted from the notebooks of the course, which were
written for the toolbox BESOS ({REFS['besos']}; code and examples under GPL-3.0, https://gitlab.com/energyincities/besos). They were
rewritten in October 2026 for **bdopt** (MIT licence, https://github.com/LorenzoBottaccioli/bdopt) and extended; the figures marked
above come from those notebooks or from the BESOS documentation.

**Model and weather.** `test.idf` was generated with DesignBuilder for the course. `ITA_Torino.160590_IWEC.epw`: IWEC data,
original source data (c) 2001 American Society of Heating, Refrigerating and Air-Conditioning Engineers (ASHRAE), Inc., Atlanta,
GA, USA, converted to EPW for EnergyPlus; licensed for your own use, not to be passed to third parties without ASHRAE's permission.

**Simulation.** The building is simulated with EnergyPlus version 9.6 (U.S. Department of Energy and partners, BSD-style licence).

**References for this notebook.**
{refs}

All of the platform's credits and licences are listed on the page **Credits & licences** of the platform.""")


def with_credits(nb, n, name):
    """Add the source line under each figure and the closing cell of credits."""
    for c in nb["cells"]:
        if c["cell_type"] != "markdown":
            continue
        text = "".join(c["source"])
        for fig, credit in FIGURE_CREDITS.items():
            if f"({fig})" in text and credit not in text:
                text = text.rstrip("\n") + f"\n\n*{credit}*"
                c["source"] = _lines(text)
    cell = credits_cell(n)
    cell["id"] = hashlib.md5(f"{name}-credits".encode()).hexdigest()[:8]
    nb["cells"].append(cell)
    return nb


def main():
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "image").mkdir(exist_ok=True)
    for f in ("test.idf", "ITA_Torino.160590_IWEC.epw"):
        shutil.copy2(BESOS / f, DST / f)
    (DST / "window_to_wall.py").write_text(tutorial_window_to_wall((SRC / "window_to_wall.py").read_text(encoding="utf8")),
                                           encoding="utf8", newline="\n")
    shutil.copy2(BESOS / "image" / "setting_up_the_evaluator.PNG", DST / "image" / "setting_up_the_evaluator.PNG")
    # image/flow_diagram.PNG and image/surrogate_overview.png are the figures of the original course notebooks with the names of
    # the old toolbox corrected: they are written by correct_images.py (run it first), not copied from the course folder
    save(with_credits(build_overview(), 1, "1_bdopt_overview.ipynb"), "1_bdopt_overview.ipynb")
    save(with_credits(build_surrogate(), 2, "2_surrogate_modelling.ipynb"), "2_surrogate_modelling.ipynb")
    save(with_credits(build_optimization(), 3, "3_optimization.ipynb"), "3_optimization.ipynb")
    save(with_credits(build_adaptive(), 4, "4_adaptive_sampling.ipynb"), "4_adaptive_sampling.ipynb")
    shutil.copy2(BESOS / "image" / "LOLA-Voronoi.jpg", DST / "image" / "LOLA-Voronoi.jpg")
    print("written to", DST)


if __name__ == "__main__":
    main()
