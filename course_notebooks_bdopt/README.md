# Course tutorials and Laboratory, ported to bdopt

**Origin and licence.** These notebooks were written for BESOS (Westermann et al. 2021, GPL-3.0, <https://gitlab.com/energyincities/besos>) and
ported to bdopt in October 2026. Two of the figures (`flow_diagram.PNG`, `setting_up_the_evaluator.PNG`) come from the BESOS documentation. Which
text and code of the ports is copied from BESOS, and so falls under the GPL, has not been established: see `docs/licence_audit.md` and `NOTICE.md`.


The course notebooks (`Laboratory`, `Laboratory_solution`, `Besos_overview`, `Surrogate_Modelling`, `Optimization`,
`AdaptiveSampling_besos_example`) were written for BESOS (and, in places, TensorFlow, Platypus, seaborn and plotly).
This folder holds the same six notebooks written for **bdopt 0.2.0** and for the students' image
`jupyter:smartbuilding-surrogate` (Python 3.11, EnergyPlus 9.6, matplotlib, scikit-learn, pymoo; no BESOS, Harlow,
TensorFlow, Keras, torch, seaborn, plotly or `epw` package). Same file names, no stored outputs.

| File | What it is |
|---|---|
| `Laboratory.ipynb` | the student notebook: same 43 cells, code cells empty, plus a table of the bdopt objects of each step |
| `Laboratory_solution.ipynb` | the solution, bdopt version (teacher material: not in the public repository) |
| `Besos_overview.ipynb` | the introduction to the toolbox (file name kept; the content is about bdopt) |
| `Surrogate_Modelling.ipynb`, `Optimization.ipynb` | surrogate models; optimisation on EnergyPlus and on a surrogate |
| `AdaptiveSampling_besos_example.ipynb` | adaptive sampling with `AdaptiveSampler` (file name kept) |
| `window_to_wall.py` | NEW. The window-to-wall ratio as a design variable (`GenericSelector`), replaces BESOS' `wwr` |
| `parameter_sets.py` | the 4/7/11-parameter sets of the adaptive notebook, written for bdopt (replaces the original file of the same name) |
| `DEFINE_THE_PROBLEM.md` | the Lab's "Define the problem" next to the panel's cell, with every difference |
| `lab_problem_for_panel.json` | the hand-written `problem.json` (schema 2) of the Lab's problem, input of the panel's cell in `DEFINE_THE_PROBLEM.md` |
| `tests/check_window_to_wall.py`, `tests/eplus_wwr_smoke.py` | NOT for students. Checks of `window_to_wall.py`: geometry of the edited models, and a 3-day EnergyPlus run of them (section 6) |

To use them, copy the notebooks and the two `.py` files into the course folder
(`virtual_BMS_simulator\data\notebooks\besos\`), which already holds `lab_building.idf`, `test.idf`, `example_idf.idf`,
`ITA_Torino.160590_IWEC.epw`, `image\` and the stored `simulation_sample_*.pkl`. The data files are not copied here:
the models and the weather file are byte-identical in all seven copies (see below). The images the notebooks
use are `building_lab.png`, `setting_up_the_evaluator.PNG`, `flow_diagram.PNG`, `LOLA-Voronoi.jpg`. The BESOS figure
`besos_surrogate_overview.png` is no longer used.

## 1. Inventory of the copies (nothing was modified, moved or deleted)

Seven copies of the same six notebooks exist under `C:\Users\Lorenzo\Documents\python_envs\`:

| Key | Folder | Last edit of its notebooks |
|---|---|---|
| A | `besos` | 2022-11-24, 2024-04-08 and 2024-10-14 |
| B | `ICT4BD\besos` | 2024-11-05 to 2024-11-13 |
| C | `notebooks\besos` | 2024-11-13 to 2024-11-19 |
| D | `prova_ict\besos` | 2024-11-05 (Laboratory: 2022-11-24) |
| E | `test_docker_besos\data\notebooks\besos` | 2024-11-13 to 2024-11-19 |
| F | `test_docker_besos\notebooks\besos` | 2024-11-05 to 2024-11-13 |
| G | `virtual_BMS_simulator\data\notebooks\besos` | 2024-11-19 to 2024-11-28; `Optimization` 2025-10-28 |

Method: SHA-256 of every file, then a SHA-256 of the sequence of cell sources (type and text, outputs ignored), then a
cell-by-cell diff of every copy against G. B and F are byte-identical for all six notebooks.

### Which libraries each notebook uses (copy G, counting `import` statements)

| Notebook | besos | harlow | tensorflow / keras | platypus | seaborn | plotly | other |
|---|---|---|---|---|---|---|---|
| `AdaptiveSampling_besos_example` | 1, plus the BESOS development modules `sampling`, `problem`, `evaluator` imported by their bare names | 0 | 0 | 0 | 1 (`kdeplot`) | 0 | scikit-learn, scipy, `parameter_sets.py` |
| `Besos_overview` | 10 | 0 | 0 | 0 | 2 | 0 | |
| `Laboratory` (student) | none: the code cells are empty, the text says "BESOS" | 0 | 0 | 0 | 0 | 0 | |
| `Laboratory_solution` | 7 | 0 | 6 | 0 | 2 | 4 | `epw` package, scikit-learn |
| `Optimization` | 10 | 0 | 0 | 1 (imported, never used) | commented out, but `sns.` still called in two cells | 0 | scikit-learn |
| `Surrogate_Modelling` | 4 | 0 | 3 | 0 | 1 | 2 | scikit-learn, ipywidgets |

**Harlow is not used by any course notebook** (the word does not appear in the cell sources of any of the 42 files). The course's adaptive-sampling notebook
runs BESOS' own LOLA-Voronoi code; Harlow appears in the platform's notebooks (`backend/notebook_templates/Surrogate_template.ipynb` and the
`Surrogate modeling examples/Test N/Harlow_Example_N.ipynb`, ported by another slice), not in the course's. So the adaptive-sampling content ported here is that BESOS notebook, with `AdaptiveSampler`.

Other notebooks in the same folders, not converted because they do not use BESOS, Harlow or TensorFlow: `en_sig\Class_example`,
`en_sig\energy_sig_demo` (no matching imports), `eppy\eppy_example` (uses `eppy`) and `weather_data\Weather_files` (uses the
`epw` package). The last two will not run in the new image (neither `eppy` nor `epw` is installed there).

### Canonical copy: G, `virtual_BMS_simulator\data\notebooks\besos`

The memory note was right, and it is checked: G has the newest edit of 4 of the 6 notebooks; for the other two
(`Surrogate_Modelling` and `AdaptiveSampling_besos_example`) its cell content is identical to B, C, E and F (G and C are
byte-identical, both saved on 2024-11-19; E was saved with outputs a few minutes later the same day). Its cell content is a superset of the older copies
(table below), and it sits in the course's Docker folder (`virtual_BMS_simulator`: `docker_compose.yml` mounts `./data` into the Jupyter
container, and the notebooks are in `data\notebooks\besos`). The copies are successive snapshots, not branches: A and D are the oldest, B/F next, C/E next, G the latest.
The SHA-256 of every file and of every notebook's cell sequence are in the appendix at the end.

### How the copies differ from G (cell level)

| Notebook | Divergences |
|---|---|
| `Laboratory` | None: identical cell content in all seven (G differs only in the notebook metadata; A=D and B=C=E=F are byte-identical groups). |
| `Laboratory_solution` | G has **10** samples (`num_samples=10`, `simulation_sample_10.pkl`), `building.idfobjects['MATERIAL']` and a `lights_param` display cell (124 cells). B, C, E, F: **40** samples, the whole `building.idfobjects`, 121 cells. A (122 cells): installs `epw` with `!pip install git+https://github.com/building-energy/epw.git` and uses `from epw import EPW`; 40 samples. D (121 cells): 40 samples, `from epw import EPW`, and the cell that should read the weather file has no `meteo.read(epw_file)`. |
| `Optimization` | Same code everywhere except G: `import seaborn as sns` commented out (but `sns.pairplot` and `sns.heatmap` are still called, so G would stop with a `NameError` at that cell), stored outputs removed (25 KB against 2.4-2.8 MB), edited 2025-10-28. A and D have 51 cells, the others 52 (an empty last cell). |
| `Surrogate_Modelling` | B, C, E, F = G. A: `epw_file='/home/ict4bd/ITA_Torino.160590_IWEC.epw'` (a path of another machine) and the neural-network error computed with the mean absolute error. D: `processes=4` in the first run and the same absolute-error metric. G has the relative path and the RMSE. |
| `Besos_overview` | B, C, E, F = G (96 cells). A and D (87 cells) lack nine cells of G (six display cells, two cells that G splits in two, an empty last cell) and have a bug fixed in G (`values1` built from `result` instead of `result1`). |
| `AdaptiveSampling_besos_example` | B, C, E, F = G. A lacks two `parameters` displays (a line in one cell and one cell) and has an extra empty last cell. D also loads `ef.get_building('test.idf')` instead of BESOS' example building: its parameter sets name objects that `test.idf` does not have. |

The input files next to the notebooks (`lab_building.idf`, `test.idf`, `example_idf.idf`, `ITA_Torino.160590_IWEC.epw`,
`parameter_sets.py`, `surrogate_simple_simulation.csv`) are **byte-identical in all seven copies**. What differs are
outputs of runs: `simulation_sample_10/40.pkl`, `samples.p`, `best_surrogate`, `lab_optimal.idf`.

## 2. How BESOS names became bdopt names

| BESOS | bdopt | Notes |
|---|---|---|
| `ef.get_building('x.idf')` | `idf = load_idf('x.idf')` | reads the text; no EnergyPlus needed. `building.idfobjects[...]` becomes `idf.by_class('Class')`; field values by name through `idd = EnergyPlus.find().idd` (`idd.fields(class)`), see `fields_of` in the notebooks |
| `FieldSelector(class_name, object_name, field_name)` | same call, same keywords | `object_name` may also be a list of names; `where={'Surface Type': 'Window'}` filters; field names are the IDD ones, with spaces |
| `RangeParameter(min_val, max_val)` | same | |
| `CategoryParameter(options=range(8, 13))` | `IntegerParameter(8, 12)` | `CategoryParameter` keeps strings or numbers and needs at least two distinct options |
| `Parameter(selector, value_descriptors=..., name=)` | `Parameter(selector, value_descriptor=..., name=)` | the plural keyword is gone |
| one `Parameter` per window sharing one descriptor and one name (the Lab's windows loop) | one `Parameter` over a `MultiSelector.from_targets(names, class_name=, field_name=)` | one column, as before; two parameters with the same name are rejected |
| `EPProblem(parameters, objectives)` | `Problem(parameters, objectives)` | the objectives are meter names (as before) or `MeterReader` / `VariableReader` |
| `sampling.dist_sampler(sampling.lhs, problem, num_samples=n)` | `sampling.lhs(problem, n, seed=...)` | `sampling.full_factorial(...)` becomes `sampling.factorial(problem, levels=...)` |
| `EvaluatorEP(problem, building, epw_file=..., out_dir=, err_dir=)` + `evaluator.df_apply(samples, keep_input=True, processes=4)` | `EnergyPlusEvaluator(problem, idf, epw_file, out_dir=, err_dir=, processes=2)` + `evaluator.evaluate(samples, keep_input=True)` | `evaluator([x])` still works for one design; `keep_dirs=True` keeps the run folders; results are cached |
| `EvaluatorGeneric(function, problem)` | `FunctionEvaluator(problem, function, vectorized=True)` | `function` receives a table of designs (or one row, without `vectorized`) |
| `from besos.optimizer import NSGAII`; `NSGAII(evaluator, evaluations=, population_size=)` | `from bdopt.optimize import nsga2`; `nsga2(problem, model, pop_size=, n_gen=)` | pymoo instead of Platypus; `model` is an `EnergyPlusEvaluator`, a `FunctionEvaluator` or a surrogate |
| `results.loc[results['pareto-optimal'] == True]` | `front.df` | `front` holds only the non-dominated designs. There is no `violation` column |
| distance to the origin of the three objectives | `df['Dist']` as before, or `front.closest_to_ideal()` | the second scales each objective to 0-1 first |
| `selector.set(building, value)`; `building.saveas(...)` | `problem.apply(idf_copy, design, idd)`; `idf_copy.save(...)` | applies the whole design with the selectors that simulated it |
| scikit-learn pipelines (scaler, `GridSearchCV`, GP, `MLPRegressor`) | unchanged, or `GPSurrogate`, `MLPSurrogate`, `AutoSurrogate` | the bdopt surrogates scale inside and take the design table directly: `model.fit(table, problem)`, `model.predict(table)`, `model.score(table)` |
| TensorFlow / Keras `Sequential` | scikit-learn `MLPRegressor(hidden_layer_sizes=(32, 64, 32), solver='adam', learning_rate_init=0.001, ...)` | same architecture; `TorchMLP` exists in bdopt but needs torch, which is not in the image |
| `seaborn.pairplot`, `heatmap`, `kdeplot` | `bdopt.viz.pairplot`, `correlation_heatmap`; matplotlib and scipy (`gaussian_kde`) | |
| `plotly.express.parallel_coordinates` | `bdopt.viz.parallel_coordinates` | matplotlib, not interactive |
| `from epw import epw` | `pandas.read_csv(epw_file, skiprows=8, header=None, names=EPW_COLUMNS)` | the 35 EPW columns are named in the Lab; checked on the Torino file (ranges of temperature, humidity, pressure, radiation, wind) |
| `%matplotlib notebook` (`Surrogate_Modelling`) | `%matplotlib inline` | the `notebook` backend does not exist in Notebook 7 (the `ipywidgets` sliders were not tried in a browser) |

## 3. What cannot be done any more, and what the student does instead

| Was in the course | Now |
|---|---|
| `building.view_model()` (draws the geometry) | bdopt does not draw. The three course models already contain `Output:Surfaces:Drawing, DXF`, so every EnergyPlus run writes a DXF drawing (`eplusout.dxf`, seen in the short runs of section 6) in its run folder; `evaluate(..., keep_dirs=True)` keeps the folders and any CAD viewer opens the file. The notebooks say so; for another model `idf.add('Output:Surfaces:Drawing', 'DXF')` asks for it. The DXF was not opened in a viewer here. |
| `df_apply` | `evaluator.evaluate(table)` |
| `expand_plist({'object': {'Field': (min, max)}})` (found the class from the object name) | one `Parameter(FieldSelector(class, object, field), RangeParameter(min, max), name=...)` per variable; the class must be written. Explained in `Besos_overview`, `Surrogate_Modelling`, `Optimization`. |
| `wwr(RangeParameter(a, b))` | `window_to_wall.wwr(a, b)`, a `GenericSelector` written for the course (`window_to_wall.py`, shown in `Besos_overview`). It is the true ratio window area / wall area: it scales the windows of every outdoor wall about their own centre; it creates and deletes no window. **It refuses what does not fit:** if a scaled window would leave its wall or overlap another window, a door or a glass door it raises `ValueError` and writes nothing. Measured in steps of 0.01 (`tests/check_window_to_wall.py`): `test.idf` accepts every ratio up to 0.83; `example_idf.idf` up to 0.46 (the glass door of the south wall is in the way), `lab_building.idf` up to 0.28 (its windows are not centred), which is why the Lab does not use it. The ranges in the notebooks are 0.1 to 0.8 on `test.idf` and 0.1 to 0.45 on the small office. The setter is written for EnergyPlus 9.6 field positions and refuses another version. Short EnergyPlus runs of the edited models: section 6. **This is not what BESOS' `wwr` did**, see item 11 of the next section. |
| `EvaluatorGeneric` | `FunctionEvaluator` |
| `EvaluatorEH` (Energy Hub), named in `Besos_overview` | not available; the notebook says so |
| constraints on **outputs** (`EPProblem(..., constraints=["CO2:Facility"], constraint_bounds=["<=800"])`) | not supported by bdopt (decision of phase 2). See the next section. |
| `NSGAII(evaluator, evaluations=N, population_size=P)` | `nsga2(problem, model, pop_size=P, n_gen=G)`: the budget is `P` x `G`, there is no total-evaluations argument |
| `dest_folder` of `keep_dirs` | `keep_dirs=True`; the run folders stay in the evaluator's `out_dir` |
| BESOS' default building and weather (`ef.get_building(mode='idf')`, Golden CO weather) used by the adaptive notebook | `example_idf.idf` (the same small office, 4 outdoor walls) and the Torino weather file |
| pandas pickles from BESOS runs | still load: `simulation_sample_10/20/40.pkl` and `samples.p` were read with pandas 3.0.6 in the new image |

### The constraints cell of `Optimization.ipynb` (cell 20 of the original) is dropped

The original built `evaluator_costrain` with `constraints=["CO2:Facility"]`, `constraint_bounds=["<=800"]`, and the next
cell ran `NSGAII(evaluator, evaluations=1, population_size=10)` with `evaluator`, **not** `evaluator_costrain`, so the
constraint was defined and never used; the comparison plots after it compared two runs of the same unconstrained problem.
The cell, the run that did not use it and the plots are not in the new notebook; a markdown cell says why. bdopt cannot
constrain simulation outputs. As a replacement for the lesson (not a port) the surrogate part of the notebook shows what bdopt
does support, a constraint on the *design variables* (`Problem(..., constraints=[g])`, feasible when `g(design) <= 0`):
the insulation layer limited to 0.25 m.

## 4. Changes of behaviour you should know about

These are not vocabulary: they differ from what the originals computed.

1. **Scaler fitted on the test data.** In `Laboratory_solution`, `Surrogate_Modelling` (`test_in_scale = scaler.fit_transform(test_in)`) the
   text says "we fit the normalizer on training data only" and the code fitted it on the test inputs. Now the scaler is fitted on the training set and only applied to the test set. Errors change slightly.
2. **One error metric for the three models.** In `Laboratory_solution` the neural network was scored with the mean squared error
   (without `squared=False`) while the other two used the root. `squared=False` no longer exists in scikit-learn 1.9
   (image B); the notebooks use `root_mean_squared_error`, as a percentage of the mean, for all models.
3. **Width of the neural network.** The hyper-parameter grid used `len(parameters) * 16` neurons; in the Lab that list had one
   `Parameter` per window, so 15 x 16 = 240. Now `problem.n_var * 16` = 7 x 16 = 112.
4. **The optimum is applied as found.** The original solution wrote `triple_glazing` in every window by hand (`win_type`); now the
   window type of the chosen design is written (the optimiser may or may not choose triple glazing). `lab_optimal.idf` is written with
   `idf.save(...)`: comments of the original file are not kept and the file is Latin-1 (bdopt's own writer). A file written this way was reopened with
   the backend's eppy 0.5.63 (section 6, item 6); the Model Editor itself was not tried.
5. **Train/test split, samples and surrogates have seeds** (`random_state=0`, `seed=0`/`1`), so the numbers repeat.
6. `Surrogate_Modelling` and `Optimization` hand over a **bdopt surrogate** (`best_surrogate.pkl`, scaling included) instead of an
   scikit-learn model plus scalers refitted on all the data in the next notebook (the original refitted the scalers on all the data
   and used them with a model trained on the training split). `surrogate_simple_simulation.csv` is only reused when its columns are those of the new problem (the
   old file in the course folder has other column names, e.g. `RangeParameter [0.1, 0.9]` for the window-to-wall ratio).
7. `Optimization`: the genetic algorithm on EnergyPlus runs a population of 10 for 3 generations (about 30 simulations, each a
   full year of `test.idf`) instead of `evaluations=10, population_size=20`; on the surrogate it is 100 x 100 instead of
   `evaluations=5000, population_size=10000`.
8. `Laboratory_solution` simulates a copy of the model **without its 38 `Output:Variable` objects** (the objectives are meters), as the
   panel's cell does; the model that is saved at the end is the complete one.
9. Additions: the Lab solution checks the chosen design with one EnergyPlus run and compares it with the surrogate (the markdown
   always asked for it, the cell was missing); bdopt's own surrogates are shown next to the hand-built ones.
10. Typos and stale text fixed on the way (`Thikness`, "epJSON" as IDF, the dead link `../Evaluators/Evaluators.ipynb`, "Lab Besos Work Flow").
11. **The window-to-wall variable changes meaning.** Read from BESOS 2.1.3's source (`besos/eppy_funcs.py`, `wwr_all` / `set_wwr_single`; BESOS was not run) and replicated on the text of the models (`wwr` = 0.5): the previous `wwr` kept one subsurface per wall (`setup`, which BESOS runs when the evaluator gets its building, deleted the others, glass doors included), multiplied the width and height of that one by sqrt(value), and wrote the new corners as absolute coordinates measured from the origin. So the value was a fraction of the *existing window*, not of the wall, and on the course models the new window lands in the wrong place: on `test.idf` every window moves to 0.47-2.76 m along its wall's axis, which is outside the east and west walls (they span 7.66-22.66 m), and on `example_idf.idf` the one subsurface left on the south wall would be put at 0.27-1.56 m of a wall 27.7 m long, whatever was there. The new variable is the true ratio and keeps the windows where they are. Designs and results are therefore not comparable with the old ones (the old `wwr` default range was 0.01 to 0.99). The previous version of this README said BESOS rebuilt the windows with geomeppy; that was wrong.

## 5. Decisions for the main thread

* **File names.** `Besos_overview.ipynb` and `AdaptiveSampling_besos_example.ipynb` keep their names as agreed; a rename
  (for instance `Bdopt_overview.ipynb`) would be cosmetic and has to be done in the course folder and in anything that links to them.
* **The panel and the Lab** differ in a few places listed in `DEFINE_THE_PROBLEM.md`; the one that matters for students is the column
  names (the Lab refers to `'Windows types'` by name when it codes the glazing).
* **`window_to_wall.py` is a new piece of code** that students will read and run (192 lines with its documentation and comments). It is geometry-checked on the three course models in steps of 0.01
  and EnergyPlus accepted the edited models in 3-day runs (section 6), but it only grows windows in place and its range depends on the model.
  If you prefer, drop `wwr` from the tutorials (four of the six notebooks use it; the Lab does not). `Surrogate_Modelling` draws a map of two variables, insulation and wwr,
  so there the second variable would have to be replaced by another one (for instance the lighting power).
* **EnergyPlus version of the course models:** all course IDFs are 9.6 (checked), so no upgrade is needed. For a model of another
  version `auto_upgrade=True` would need `IDFVersionUpdater`, which is not in the EnergyPlus copy of image B (its `PreProcess` folder
  has `CalcSoilSurfTemp`, `GrndTempCalc`, `HVACCurveFitTool`, `ParametricPreprocessor` only).

## 6. What was run, and what was not

Everything below ran in image `jupyter:smartbuilding-surrogate` (EnergyPlus 9.6.0, Python 3.11, nbformat 5.11.1, pandas 3.0.6), one container at a time,
`--memory` 1 or 2 g, against the course's real models and weather file (read-only mounts; the notebooks ran in a copy inside the container, so nothing was written
into `python_envs` or into this folder). The scripts that ran are not shipped, except `tests/` (for `window_to_wall.py`).

Run, and passed:

1. **Static checks.** `nbformat.validate` on the six notebooks (format 4.5), `ast.parse` of every non-empty code cell (`%` lines replaced) and of `window_to_wall.py` and
   `parameter_sets.py`; no stored outputs or execution counts, unique cell ids, kernel `python3`, LF line endings. A scan of the code cells for the old
   names (`besos`, `harlow`, `tensorflow`, `keras`, `platypus`, `seaborn`, `plotly`, `EPProblem`, `EvaluatorEP`, `EvaluatorGeneric`, `df_apply`, `expand_plist`,
   `view_model`, `eppy`, `idfobjects`, `dist_sampler`, `NSGAII`, `get_building`): none, except that two code cells (`Surrogate_Modelling` cell 4 and `Optimization` cell 3) carry
   the comment "see Besos_overview.ipynb", the name of the file that kept its name. In text the old names appear only where a cell explains the replacement.
2. **Execution of the notebooks, cell by cell, with the EnergyPlus runs replaced by an analytic stand-in.** `EnergyPlusEvaluator.evaluate` was replaced (at class level,
   the notebooks are not touched) by a smooth function of the design. All code cells ran with no error: `Besos_overview` 58 of 58, `Surrogate_Modelling` 47 of 47,
   `Optimization` 23 of 23, `AdaptiveSampling_besos_example` 13 of 13, `Laboratory_solution` 61 of 61, `Laboratory` 4 of 4 (its other 15 code cells are empty).
   What was real: the construction of every `EnergyPlusEvaluator` (it validates every selector against the IDD), every design that reached the stand-in
   (180 in all) written into a copy of the model with `Problem.apply` and parsed back, including the window-to-wall `GenericSelector`; the real
   `AdaptiveSampler.run` loop; the scikit-learn models; `GPSurrogate` and `MLPSurrogate`; the `FunctionEvaluator` wrappers; `nsga2` on a surrogate, with and without the
   constraint on a design variable; `viz`; `problem.apply` and `idf.save`; the hand-over of `best_surrogate.pkl` and of the CSV from `Surrogate_Modelling` to `Optimization`
   (the stale `surrogate_simple_simulation.csv` of the course folder is rejected by the notebook's guard, its columns are those of the old problem). The numbers that appeared
   say nothing about the converted notebooks. About 8 minutes in all; the slowest cells: the scikit-learn network grid of the Lab 162 s, bdopt's two surrogates 117 s, the
   adaptive run 106 s. (A first execution of the same script, started while eight other containers were using the VM, had not finished after 48 minutes, I do not know in which
   notebook because its output was buffered, and I stopped it; I did not find the reason.)
3. **The panel's cell against the Lab** (details and the list of differences in `DEFINE_THE_PROBLEM.md`): constructed, no simulation. Same parameter names, objects written,
   columns of `samples`; identical IDF text for three random designs.
4. **`window_to_wall.py`, geometry** (`tests/check_window_to_wall.py`): for every ratio 0.01 to 0.99 on `test.idf`, `example_idf.idf` and `lab_building.idf`, the setter was run
   as it is and with its own fit check switched off, and the result was checked by independent code (windows add up to the ratio of the wall, stay in the plane and inside the wall,
   overlap no window or door). The setter accepts 0.01-0.83 on `test.idf`, 0.01-0.46 on `example_idf.idf`, 0.01-0.28 on `lab_building.idf`; it refused exactly the ratios at which the independent
   check finds a problem (0 disagreements out of 297); a synthetic wall 3 m high (vertex 1 at z = 3.0) gets the exact ratio. **A bug found on the way and fixed:** the first version
   found the vertices of a surface by looking for the field that equals the number of vertices, and read a wall whose first vertex has z = 3.0 as a triangle, halving the wall area
   (and the real ratio); `vertices()` now uses the field positions of the 9.6 IDD.
5. **`window_to_wall.py`, EnergyPlus** (`tests/eplus_wwr_smoke.py`, EnergyPlus called directly, 3 days of simulation, 1-3 January, **not a year**): `test.idf` unedited and at ratios 0.1, 0.5, 0.8, 0.83;
   `example_idf.idf` unedited and at 0.1, 0.3, 0.46; `lab_building.idf` unedited and at 0.1, 0.28. All 12 runs completed, 0 severe errors, and the same number of warnings as the unedited
   model (37, 5 and 23); each wrote `eplusout.dxf` (so the DXF advice of the notebooks is true). EnergyPlus 9.6 does not catch everything: with the setter's fit check switched off, `example_idf.idf` at 0.5 has windows
   overlapping the glass door and EnergyPlus printed no warning that mentions a subsurface, window or overlap (at 0.9 it printed "Base surface does not surround subsurface" for windows that left the wall);
   the independent check of item 4 is what covers the overlaps.
6. **A model written by the Lab reloads in the platform's eppy.** `lab_building.idf` with one Latin hypercube design written by `Problem.apply` + `idf.save` (what the Lab's last cells do) was
   read by the backend's eppy 0.5.63 (image `backend:latest`, IDD 9.6): same number of objects in each of the 77 classes as the original, the design values are in the fields they were
   written to, the 38 `Output:Variable` are kept, and eppy re-saves it. The Model Editor itself was not opened.
7. **Facts the text relies on:** the three models are version 9.6; the Torino weather file has 8760 rows, the 35 column names of the Lab fit it (11 of them checked against physical ranges: temperatures, humidity, pressure, radiation, illuminance, wind, sky cover);
   `lab_building.idf` (38 `Output:Variable`, at `timestep`) is byte-identical to the model in bdopt's `examples/models`; `simulation_sample_10/20/40.pkl` and `samples.p` load with pandas 3.0.6;
   the field positions of the 9.6 IDD that `window_to_wall.py` uses, read from `Energy+.idd`.
8. **The inventory** of section 1: SHA-256 of every file and cell sequence, cell-level diffs of every copy against G, scan of all notebooks of the seven folders for the libraries (appendix).

**Not run, so not known:**

* (done in section 7) annual EnergyPlus simulations of the converted notebooks. What is still not done: the converted notebooks' results have not been compared with the stored BESOS results (phase 5 of the plan; the stored tables are the reference).
* the notebooks in a browser (Jupyter Notebook 7), in particular the `ipywidgets` sliders of `Surrogate_Modelling` (the cell ran and returned, without a frontend), the look of the figures, the DXF
  in a viewer, and the Lab as a student would use it.
* `AutoSurrogate` (mentioned in the Lab, not run: in the previous pass it did not finish a cell in 25 minutes on a loaded machine).
* the Model Editor (the backend) opening a model written by bdopt, beyond the eppy reload of item 6.
* `eppy_example.ipynb` and `Weather_files.ipynb` (not converted: they need `eppy` and the `epw` package, absent from image B).

## 7. Second pass, 9 October: the notebooks run on real EnergyPlus

Image `jupyter:smartbuilding-surrogate` (EnergyPlus 9.6, Python 3.11, bdopt 0.2.0), one container at a time with `--memory=1g`, each notebook in a scratch copy of the folder (the data files
copied from `virtual_BMS_simulator\data
otebooksesos`), executed cell by cell with the time of each cell recorded. The machine was shared with other jobs, so the times are indicative.
**Real EnergyPlus runs, annual (full year, Torino weather), no stand-in.** Each notebook ran to its last cell without an exception:

| Notebook | Budget | Result | Time |
|---|---|---|---|
| `Surrogate_Modelling` | unchanged (10 + 20 simulations of `test.idf`) | all code cells ran; creates `samples.p`, `surrogate_simple_simulation.csv`, `best_surrogate.pkl` | 647 s (the 20 simulations: 415 s) |
| `Optimization`, run right after it in the same folder | unchanged (1 + 30 simulations, then the surrogate) | all code cells ran, reads the files just made | 444 s (the genetic algorithm on EnergyPlus: 394 s) |
| `Besos_overview` | unchanged (2 single runs and 10 simulations) | all code cells ran | 136 s |
| `AdaptiveSampling_besos_example` | unchanged (20 initial points, 5 iterations of 4, then 36 more simulations for the comparison) | all code cells ran; the stats line shows `energyplus_warnings: 303, severe: 0`; also a reduced run (15 initial, 3 iterations) | 112 s (reduced: 78 s) |
| `Laboratory_solution` | unchanged (10 simulations of `lab_building.idf`) | all code cells ran | 114 s |

The stdout and stderr of the notebooks had no warning. `parameter_set(4)`, `(7)` and `(11)` build and write designs into `example_idf.idf` (only the 7-parameter set is used by the notebook). `Laboratory.ipynb` (student version, empty cells) was not executed beyond what section 6 says.
Not tried: the `ipywidgets` sliders of `Surrogate_Modelling` (no browser), the figures by eye, `AutoSurrogate`.

**What was changed because of this pass**

* `Optimization.ipynb`: the cell that reads `surrogate_simple_simulation.csv` and `best_surrogate.pkl` now stops with a message that says which file is missing and what to run (before: a bare `FileNotFoundError` or a `KeyError` on a column).
  The same for a CSV with other columns (the one that came with the course has `RangeParameter [0.1, 0.9]`, `Conductivity`, ...) and for a `best_surrogate.pkl` that does not fit: `Surrogate.load` accepts **any** pickle, so the old scikit-learn
  `best_surrogate` of the course, renamed to `.pkl`, loaded without an error and predicted numbers in scaled units (about 5.7 for electricity in joules of 5.8e10). The cell now compares the surrogate with the simulations it
  was trained on (mean relative error must be below 50 %). The four situations (nothing, old CSV, old pickle, good files) were run.
* `Laboratory_solution.ipynb`, cells 55 and 85 (the glazing coding) and 102 (`idd`): see `DEFINE_THE_PROBLEM.md`, section "What a student who defined the problem in the panel sees".
* `window_to_wall.py` (docstring) and `Besos_overview.ipynb` (cell 69): the measured limits and what EnergyPlus reports.

### `window_to_wall.py` on real simulations

Annual runs of one design at a time (`Electricity` / `District heating` / `District cooling`, MWh):

| Model | Ratio | Electricity | Heating | Cooling |
|---|---|---|---|---|
| `test.idf` | 0.2 | 23.76 | 11.63 | 17.33 |
| | 0.5 | 23.76 | 12.65 | 27.80 |
| | 0.8 | 23.76 | 14.66 | 38.43 |
| `lab_building.idf` | 0.1 | 1.90 | 5.08 | 0.72 |
| | 0.2 | 1.82 | 4.82 | 1.42 |
| | 0.28 | 1.79 | 4.70 | 2.12 |
| | 0.29, 0.5 | `ValueError`, nothing simulated | | |
| `example_idf.idf` | 0.1 / 0.3 / 0.46 | 0.506 / 0.541 / 0.567 | no district heating meter in this model | no district cooling meter |

More glass gives more cooling in all three, the results move monotonically with the ratio, and nothing was simulated that EnergyPlus considered wrong (no severe errors). Whether the sign of the effect on heating is right
(it grows in `test.idf` and falls in `lab_building.idf`) was not separated into solar gain and heat loss. **Where it breaks:** on `lab_building.idf` the setter refuses 0.29 and above. The reason, measured: the smaller window of
`Block1B:Livingroom_Wall_4_0_0` spans 0.04 to 2.15 m of a wall 3 m high, so growing it about its centre (the rule of the setter) takes its bottom edge below the floor line after a 4 % growth in each direction; the
setter raises `ValueError` for the whole design. (The first agent had reported a failure "above 0.2"; the measured limit is 0.28, in steps of 0.01, 0.1 to 0.28 run on EnergyPlus.) At 0.5 the error names the kitchen window.
In my test the `ValueError` came out of `evaluator.evaluate(...)` (one design per call); I did not test what it does to a table of several designs. The notebooks keep the range of the variable inside the limit of the model.
The setter is correct where it accepts, and EnergyPlus' own `EnvelopeSummary` table agrees (run for 2 days): `test.idf` unedited 18.95 % -> 52.42 % for a request of 0.5 (the report counts the frame); `lab_building.idf`
19.9 % -> 22.3 % for 0.28 (walls with no window stay without); `example_idf.idf` 21.2 % -> 31.4 % for 0.3. It stays a tool for these three models, not a general replacement of BESOS' `wwr`; the notebooks and the docstring say so.

## Appendix: SHA-256 of the notebooks of the seven copies

First 8 hex digits. "file" is the SHA-256 of the file (outputs included); "cells" is the SHA-256 of the sequence of cell types and stripped sources (outputs and metadata ignored), with the number of cells. Same
cells hash = same cell content.

| Notebook | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| `Laboratory` file | `1231d159` | `76ad2c5b` | `76ad2c5b` | `1231d159` | `76ad2c5b` | `76ad2c5b` | `bf5eac22` |
| `Laboratory` cells (count) | `76ec0cab (43)` | `76ec0cab (43)` | `76ec0cab (43)` | `76ec0cab (43)` | `76ec0cab (43)` | `76ec0cab (43)` | `76ec0cab (43)` |
| `Laboratory_solution` file | `7006ad47` | `3a8c6804` | `5a0f7e8f` | `6f895103` | `a6e3ba70` | `3a8c6804` | `376e2532` |
| `Laboratory_solution` cells (count) | `56432aed (122)` | `201ac6af (121)` | `201ac6af (121)` | `ff368e4f (121)` | `201ac6af (121)` | `201ac6af (121)` | `fb410f7c (124)` |
| `Besos_overview` file | `de47cd21` | `048b52ad` | `e4836281` | `ca32d6d5` | `8dc79747` | `048b52ad` | `4e0b5de2` |
| `Besos_overview` cells (count) | `108a16cb (87)` | `b2bbc5c5 (96)` | `b2bbc5c5 (96)` | `108a16cb (87)` | `b2bbc5c5 (96)` | `b2bbc5c5 (96)` | `b2bbc5c5 (96)` |
| `Surrogate_Modelling` file | `0b450bf3` | `56c617ea` | `db454c44` | `40084e30` | `e4f5723d` | `56c617ea` | `db454c44` |
| `Surrogate_Modelling` cells (count) | `ace71b98 (88)` | `1c262e7c (88)` | `1c262e7c (88)` | `73967d3d (88)` | `1c262e7c (88)` | `1c262e7c (88)` | `1c262e7c (88)` |
| `Optimization` file | `c6bc33a0` | `fe01a311` | `82cfcbe9` | `f34fefdb` | `508f07c4` | `fe01a311` | `cbd1957a` |
| `Optimization` cells (count) | `fef8c013 (51)` | `84991647 (52)` | `84991647 (52)` | `fef8c013 (51)` | `84991647 (52)` | `84991647 (52)` | `575caa33 (52)` |
| `AdaptiveSampling_besos_example` file | `1c8a2cbf` | `2f17a4b2` | `4130ff62` | `c38ac18e` | `1132df63` | `2f17a4b2` | `4130ff62` |
| `AdaptiveSampling_besos_example` cells (count) | `9fa6bd55 (20)` | `7b73e426 (20)` | `7b73e426 (20)` | `5c2d71b8 (20)` | `7b73e426 (20)` | `7b73e426 (20)` | `7b73e426 (20)` |

`Laboratory_solution`: A (122 cells), D (121) and G (124) differ from each other and from B = C = E = F (121). `Besos_overview`: A = D (87 cells) against B = C = E = F = G (96). `Optimization`: A = D (51)
against B = C = E = F (52) against G. `Surrogate_Modelling` and `AdaptiveSampling_besos_example`: A and D differ from each other and from B = C = E = F = G. `Laboratory`: the same cells in all seven.
