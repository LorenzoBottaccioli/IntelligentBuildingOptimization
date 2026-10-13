# "Define the problem": the Lab's cells and the panel's cell

The platform's panel (`backend/bdopt_cell.py`, engine `bdopt`) writes **one** cell that defines the design problem. The
Laboratory (`Laboratory_solution.ipynb`, bdopt version) builds the same objects in several cells, one idea per cell.
This page puts the two side by side, next to what the shared contract says, and lists every difference so that the
main thread can reconcile them.

## How the texts were obtained

* **The Lab's code** is copied by a script from the code cells of `Laboratory_solution.ipynb` of this folder (section
  "Define The Problem" and the first cells of "Generate the Dataset"), in the order in which they run. Nothing is
  retyped; the cell numbers are the notebook's.
* **The panel's cell** is the output of the platform's own function `notebook_cell` (`backend/bdopt_cell.py`, read only,
  sha256 `fba6d251`, 16494 bytes; another agent was editing it while I worked, and an earlier version, `d4110688`, 16036 bytes, gives the identical text for this problem), run on a `problem.json` definition that I wrote by hand to mirror the Lab:
  `lab_problem_for_panel.json` in this folder (schema 2; seven variables with the Lab's names, ranges and fields, the
  glazing as one variable over the 9 windows (`Surface Type = Window`) of `lab_building.idf`, the Lab's three meters). The real panel
  names the variables from the student's choices (for instance "External walls thickness EPS ..."); in my definition I gave them the Lab's names.
  To regenerate: `bdopt_cell.notebook_cell(d["variables"], d["objectives"])` with
  `d = json.load(open("lab_problem_for_panel.json"))`. If `bdopt_cell.py` changes, the text below is out of date.
* Both were then **run** (construct only, no simulation) in image `jupyter:smartbuilding-surrogate` against the real
  `lab_building.idf` and `ITA_Torino.160590_IWEC.epw`, and compared: see "Checks" at the end.

## What the shared contract says, and what the emitter writes

**Contract** (the brief of the migration). For engine `bdopt` the cell defines, in this order: the imports it needs from
bdopt, `parameters` (a list of `Parameter`), `problem`, `evaluator` (an `EnergyPlusEvaluator` built from `idf` and `epw_file`),
`samples` (a DataFrame of 20 Latin hypercube rows). It *uses* two names that an earlier injected cell defines: `idf`
(`bdopt.load_idf("../uploads/<model>.idf")`) and `epw_file` (the path of the weather file). Evaluator settings:
`out_dir="/tmp/bdopt_runs"`, `err_dir="outputdir"`, `processes=2`.

**Emitter** (`backend/bdopt_cell.py` as it is now). Same, with these differences from the contract text:

| | Contract | Emitter |
|---|---|---|
| names defined | `parameters`, `problem`, `evaluator`, `samples` | those four **plus `objectives` and `sim_idf`** (and `<slug>_sel`, `<slug>_options` per variable) |
| model given to the evaluator | `idf` | **`sim_idf`**, a copy of `idf` without its `Output:Variable` objects (a RAM guard); `idf` stays the model to save |
| imports | "the imports it needs from bdopt" | `from bdopt import (...)` and a second line `from bdopt.sampling import lhs` |
| `samples` | 20 LHS rows | `lhs(problem, 20)`, no seed (a comment says how to seed) |
| blinds | not mentioned | when a variable carries `shading`, a block before `parameters` rewrites `WindowShadingControl` **in `idf` itself** (not in the copy) |

Everything else (`out_dir`, `err_dir`, `processes=2`, one `Parameter` = one column, IDD field names with spaces, keyword
names) is as in the contract. The Lab agrees with the emitter on every row of this table except the number of samples.

## The Lab, verbatim

Defined before it: `idf = load_idf('lab_building.idf')` (cell 6) and, in the same notebook, `epw_file` (cell 11).

```python
# --- Laboratory_solution.ipynb, cell 1 ---
import time
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.exceptions import ConvergenceWarning

from bdopt import (CategoryParameter, EnergyPlus, EnergyPlusEvaluator, FieldSelector, FunctionEvaluator,
                   MultiSelector, Parameter, Problem, RangeParameter, load_idf, sampling, viz)
from bdopt.optimize import nsga2
from bdopt.surrogate import GPSurrogate, MLPSurrogate

warnings.filterwarnings('ignore', category=ConvergenceWarning)   # the small neural networks below do not always "converge" on a handful of samples

# --- Laboratory_solution.ipynb, cell 6 ---
# Open the IDF file
idf = load_idf('lab_building.idf')
print(idf)
print(len(idf.by_class('Zone')), 'zones,', len(idf.by_class('BuildingSurface:Detailed')), 'opaque surfaces,',
      len(idf.by_class('FenestrationSurface:Detailed')), 'windows and doors')

# --- Laboratory_solution.ipynb, cell 11 (only its first line) ---
epw_file = 'ITA_Torino.160590_IWEC.epw'

# --- Laboratory_solution.ipynb, cell 14 ---
idd = EnergyPlus.find().idd          # field names of every EnergyPlus class

def fields_of(obj):
    """An IDF object as {field name: value}."""
    return dict(zip(idd.fields(obj.class_name), obj.fields))

pd.DataFrame([fields_of(m) for m in idf.by_class('Material')])[['Name', 'Thickness', 'Conductivity']]

# --- Laboratory_solution.ipynb, cell 15 ---
roof_ins = FieldSelector(class_name='Material',
                         object_name='MW Glass Wool (rolls)_.1445',
                         field_name='Thickness')
wall_ins = FieldSelector(class_name='Material',
                         object_name='EPS Expanded Polystyrene (Heavyweight)_.1',
                         field_name='Thickness')

# --- Laboratory_solution.ipynb, cell 16 ---
wall_range = RangeParameter(min_val=0.1, max_val=0.5)
roof_range = RangeParameter(min_val=0.1, max_val=0.8)

# --- Laboratory_solution.ipynb, cell 18 ---
insulation_param = [Parameter(selector=wall_ins,
                              value_descriptor=wall_range,
                              name='Wall Insulation'),
                    Parameter(selector=roof_ins,
                              value_descriptor=roof_range,
                              name='Roof Insulation')]
print(insulation_param)

# --- Laboratory_solution.ipynb, cell 20 ---
# the windows of the model: Surface Type = Window (the others are doors)
window_names = [o.name for o in idf.by_class('FenestrationSurface:Detailed') if fields_of(o)['Surface Type'] == 'Window']
print(len(window_names), 'windows')
window_names

# --- Laboratory_solution.ipynb, cell 21 ---
windows = MultiSelector.from_targets(window_names,
                                     class_name='FenestrationSurface:Detailed',
                                     field_name='Construction Name')
windows

# --- Laboratory_solution.ipynb, cell 23 ---
# selection of windows parameters: the glazing is one of three constructions of the model
win_arr = ['single_glazing', 'double_glazing', 'triple_glazing']
windows_types = CategoryParameter(win_arr)
windows_param = Parameter(selector=windows, value_descriptor=windows_types, name='Windows types')
windows_param

# --- Laboratory_solution.ipynb, cell 24 ---
# ACH parameters selection
vent_ach_range = RangeParameter(min_val=0.0, max_val=6.0)
vent_ach_sel = FieldSelector(class_name='ZoneVentilation:DesignFlowRate',
                             object_name='*',
                             field_name='Air Changes per Hour')
ventilation_ach_param = Parameter(selector=vent_ach_sel, value_descriptor=vent_ach_range, name='Ventilation ACH')
ventilation_ach_param

# --- Laboratory_solution.ipynb, cell 25 ---
lights_selector = FieldSelector(class_name='Lights', object_name='*', field_name='Watts per Zone Floor Area')
lights_range = RangeParameter(min_val=8, max_val=20)
lights_param = Parameter(lights_selector, value_descriptor=lights_range, name='Lights Watts/Area')
lights_param

# --- Laboratory_solution.ipynb, cell 27 ---
temp_shading_range = RangeParameter(min_val=18, max_val=30)
rad_shading_range = RangeParameter(min_val=80, max_val=300)

shade_setpoint_sel = FieldSelector(class_name='WindowShadingControl', object_name='*', field_name='Setpoint')
shade_setpoint2_sel = FieldSelector(class_name='WindowShadingControl', object_name='*', field_name='Setpoint 2')
setpoint_params = [
    Parameter(selector=shade_setpoint_sel, value_descriptor=temp_shading_range, name='Temp Setpoint shading'),
    Parameter(selector=shade_setpoint2_sel, value_descriptor=rad_shading_range, name='Rad Setpoint shading'),
]

# --- Laboratory_solution.ipynb, cell 28 ---
parameters = insulation_param + [windows_param, lights_param, ventilation_ach_param] + setpoint_params
parameters

# --- Laboratory_solution.ipynb, cell 29 ---
objectives = ['Electricity:Facility', 'DistrictHeating:Facility', 'DistrictCooling:Facility']   # EnergyPlus meters, summed over the run period [J]

problem = Problem(parameters, objectives)    # problem = parameters + objectives

# --- Laboratory_solution.ipynb, cell 32 ---
samples = sampling.lhs(problem, 10, seed=0)     # Latin hypercube; the seed makes the table reproducible
samples

# --- Laboratory_solution.ipynb, cell 33 ---
# EnergyPlus writes every Output:Variable the model asks for into its results database, and this model asks for 38
# of them at every time step. The objectives are meters, which the evaluator requests by itself, so those variables are not
# needed: they are removed from the copy that is simulated (`idf` itself is left as it is, it is the model we will save).
sim_idf = idf.copy()
sim_idf.remove(sim_idf.by_class('Output:Variable'))

evaluator = EnergyPlusEvaluator(problem, sim_idf, epw_file,
                                out_dir='/tmp/bdopt_runs',   # work files go to the container's own disk (the shared folder is much slower)
                                err_dir='outputdir',         # runs that fail are kept here, with the EnergyPlus error file
                                processes=2)                 # EnergyPlus runs in parallel
print(evaluator.eplus)
```

## The panel's cell for the same problem, verbatim (output of `bdopt_cell.notebook_cell`)

```python
# Define the problem: what to vary (parameters), what to improve (objectives), how EnergyPlus is run.
# Written by the platform from the problem you defined; change it as you like.
# It needs two names from the cell above: idf (the model, bdopt.load_idf) and epw_file (the weather file).
# Every selector is checked against the model when the evaluator is created, with suggestions for a typo.
from bdopt import (
    CategoryParameter, EnergyPlusEvaluator, FieldSelector, MultiSelector, Parameter, Problem,
    RangeParameter,
)
from bdopt.sampling import lhs

# 7 parameters = 7 columns of `samples`, however many objects each one writes.
parameters = []

# Wall Insulation
#   writes 1 Material object, field "Thickness"
wall_insulation_sel = FieldSelector(
    class_name="Material",
    object_name="EPS Expanded Polystyrene (Heavyweight)_.1",
    field_name="Thickness",
)
parameters.append(Parameter(
    selector=wall_insulation_sel,
    value_descriptor=RangeParameter(0.1, 0.5),
    name="Wall Insulation",
))

# Roof Insulation
#   writes 1 Material object, field "Thickness"
roof_insulation_sel = FieldSelector(
    class_name="Material",
    object_name="MW Glass Wool (rolls)_.1445",
    field_name="Thickness",
)
parameters.append(Parameter(
    selector=roof_insulation_sel,
    value_descriptor=RangeParameter(0.1, 0.8),
    name="Roof Insulation",
))

# Windows types
#   writes 9 FenestrationSurface:Detailed objects, field "Construction Name"
#   The column holds the option itself; problem.json numbered the options:
#     1 = single_glazing, 2 = double_glazing, 3 = triple_glazing
windows_types_sel = MultiSelector.from_targets(
    [
        "Block1B:Kitchen_Wall_5_0_0_0_0_0_Win", "Block1B:Bathroom1_Wall_6_0_0_0_0_0_Win",
        "Block1B:Room1_Wall_2_0_0_0_0_0_Win", "Block1B:Room1_Wall_6_0_0_0_0_0_Win",
        "Block1B:Bathroom_Wall_2_0_0_0_0_0_Win", "Block1B:Livingroom_Wall_4_0_0_0_0_1_Win",
        "Block1B:Livingroom_Wall_4_0_0_1_0_0_Win", "Block1B:Room_Wall_2_0_0_0_0_0_Win",
        "Block1B:Room_Wall_3_0_0_0_0_0_Win",
    ],
    class_name="FenestrationSurface:Detailed", field_name="Construction Name",
)
windows_types_options = CategoryParameter([
    "single_glazing", "double_glazing", "triple_glazing",
])
parameters.append(Parameter(
    selector=windows_types_sel,
    value_descriptor=windows_types_options,
    name="Windows types",
))

# Lights Watts/Area
#   writes every Lights object, field "Watts per Zone Floor Area"
lights_watts_area_sel = FieldSelector(
    class_name="Lights",
    object_name="*",
    field_name="Watts per Zone Floor Area",
)
parameters.append(Parameter(
    selector=lights_watts_area_sel,
    value_descriptor=RangeParameter(8, 20),
    name="Lights Watts/Area",
))

# Ventilation ACH
#   writes every ZoneVentilation:DesignFlowRate object, field "Air Changes per Hour"
ventilation_ach_sel = FieldSelector(
    class_name="ZoneVentilation:DesignFlowRate",
    object_name="*",
    field_name="Air Changes per Hour",
)
parameters.append(Parameter(
    selector=ventilation_ach_sel,
    value_descriptor=RangeParameter(0, 6),
    name="Ventilation ACH",
))

# Temp Setpoint shading
#   writes every WindowShadingControl object, field "Setpoint"
temp_setpoint_shading_sel = FieldSelector(
    class_name="WindowShadingControl",
    object_name="*",
    field_name="Setpoint",
)
parameters.append(Parameter(
    selector=temp_setpoint_shading_sel,
    value_descriptor=RangeParameter(18, 30),
    name="Temp Setpoint shading",
))

# Rad Setpoint shading
#   writes every WindowShadingControl object, field "Setpoint 2"
rad_setpoint_shading_sel = FieldSelector(
    class_name="WindowShadingControl",
    object_name="*",
    field_name="Setpoint 2",
)
parameters.append(Parameter(
    selector=rad_setpoint_shading_sel,
    value_descriptor=RangeParameter(80, 300),
    name="Rad Setpoint shading",
))

# Objectives: meters, summed over the run period, in joules.
# A plain name is minimised; MeterReader(name, direction="max") maximises.
objectives = [
    "Electricity:Facility",
    "DistrictHeating:Facility",
    "DistrictCooling:Facility",
]
problem = Problem(parameters, objectives)

# EnergyPlus writes every Output:Variable the model asks for into its results database, and a detailed model
# asks for hundreds. The objectives are meters, which the evaluator requests by itself, so none of those
# variables is needed: they are removed from the copy that is simulated (idf itself is left as it is).
# An objective that reads a variable, e.g. VariableReader, makes the evaluator request that variable itself.
sim_idf = idf.copy()
sim_idf.remove(sim_idf.by_class("Output:Variable"))
evaluator = EnergyPlusEvaluator(
    problem, sim_idf, epw_file,
    out_dir="/tmp/bdopt_runs",  # run folders on the container's own disk: much faster than a shared folder
    err_dir="outputdir",        # a run that fails is kept here, with EnergyPlus' error file
    processes=2,                # EnergyPlus runs in parallel
)

samples = lhs(problem, 20)  # 20 Latin hypercube samples: a row per design, a column per parameter
# lhs(problem, 20, seed=1) gives the same samples every time, and runs already done are not repeated.
```

## Every difference

Same in both (checked, see the end): the objects used (`FieldSelector`, `MultiSelector.from_targets`, `Parameter`,
`RangeParameter`, `CategoryParameter`, `Problem`, `EnergyPlusEvaluator`), the keyword names (`class_name`, `object_name`,
`field_name`, `selector`, `value_descriptor`, `name`), IDD field names with spaces, `"*"` for "every object of the class",
one `Parameter` = one column, the same three meters (all minimised), `sim_idf` without `Output:Variable`,
`out_dir="/tmp/bdopt_runs"`, `err_dir="outputdir"`, `processes=2`, the names `idf` and `epw_file`.

| # | Lab | Panel | Consequence / suggestion |
|---|---|---|---|
| 1 | Several cells in two sections (selectors, descriptors, parameters, problem; later samples and evaluator) with prose between them | One cell with everything | Intended: the panel writes the finished definition, the Lab teaches it step by step. Nothing to reconcile. |
| 2 | One import cell at the top of the notebook with everything the notebook needs (also `sampling`, `viz`, `load_idf`, `EnergyPlus`, `FunctionEvaluator`, `nsga2`, the surrogates) and `sampling.lhs(...)` | Imports inside the cell, only what it uses, sorted; `from bdopt.sampling import lhs` and `lhs(...)` | Cosmetic. The platform's own template (`Surrogate_template_bdopt.ipynb`) also imports `lhs` directly. If a student pastes the panel's cell into the Lab nothing breaks, but `sampling` is not defined by the panel's cell. Choose one spelling for both if you want the texts identical (`from bdopt.sampling import lhs` is the one the template uses). |
| 3 | Variables named after their role (`roof_ins`, `wall_ins`, `windows`, `lights_selector`, `shade_setpoint_sel`) and descriptors in separate variables (`wall_range`); `Parameter` objects put in lists and added with `+` | `<slug>_sel` for every selector, the descriptor inline (`RangeParameter(0.1, 0.5)`) or `<slug>_options`; `parameters = []` and `parameters.append(Parameter(...))` | Cosmetic. The panel's is the more regular. |
| 4 | `RangeParameter(min_val=.., max_val=..)` keywords, numbers as typed (`0.0`, `6.0`) | `RangeParameter(0.1, 0.5)` positional, numbers printed with at most 12 significant digits (`RangeParameter(0, 6)`, not `6.0`) | Cosmetic; both valid. |
| 5 | Parameter names chosen by the student: `Wall Insulation`, `Roof Insulation`, `Windows types`, `Lights Watts/Area`, `Ventilation ACH`, `Temp Setpoint shading`, `Rad Setpoint shading` (the columns of the stored `simulation_sample_*.pkl` tables) | Names of the variables in `problem.json` (long, generated, e.g. "External walls thickness EPS Expanded Polystyrene (Heavyweight)_.1"; in my rendering I gave the Lab's names) | **The one that matters for students.** The Lab's surrogate cells refer to the column `'Windows types'` by name (the glazing coding `glazing_code`), and `features = list(samples.columns)` follows the problem for everything else. A student who defines the Lab's problem in the panel gets other column names. Decision: let the panel offer a name field (the emitter already uses `v['name']`), or make the Lab's glazing cells find the categorical column from `problem` (`[p.name for p in problem.parameters if p.kind == "categorical"]`). |
| 6 | The windows come from a list the code computes from the model (`window_names`: Surface Type = Window) and are given to `MultiSelector.from_targets(window_names, class_name=, field_name=)` | The same call with the names written out literally (a snapshot of the model when the problem was defined) | Same construct. The Lab's list follows the model if it changes. The notebook mentions the other way, `FieldSelector(..., '*', 'Construction Name', where={'Surface Type': 'Window'})`, which the panel cannot write: `problem.json` has no `where`. |
| 7 | The options in the order the student wrote them (single, double, triple); the 1, 2, 3 coding that the scikit-learn models need is built by the student (`glazing_code`) | The options in the order of `problem.json`, with a comment "problem.json numbered the options: 1 = ..." | The coding is only used by models that need numbers; bdopt's surrogates and `nsga2` use the option itself. If the Lab should reuse the panel's numbering the option order must be the same. |
| 8 | `objectives` = three meter names (plain strings) | The same (a maximised objective would be `MeterReader(name, direction="max")`) | None. |
| 9 | `sampling.lhs(problem, 10, seed=0)`: 10 rows, seeded (the Lab then asks for 20 and 40) | `lhs(problem, 20)`: 20 rows, no seed; a comment shows `seed=1` | Number of rows differs on purpose (10 rows first because they take minutes). The panel could write `seed=` in the cell instead of a comment if reproducible samples are wanted. |
| 10 | `idf = load_idf('lab_building.idf')`, `epw_file = 'ITA_Torino.160590_IWEC.epw'` (same folder as the notebook); `idd = EnergyPlus.find().idd` and `fields_of(...)` to print objects | `idf = load_idf(r"../uploads/<model>.idf")`, `epw_file = r"../uploads/<weather>.epw"` injected by an earlier cell (`backend/inject_data.py`) | Same names, other paths. **`idd` is not defined by the panel or by the template** (neither imports `EnergyPlus`). The Lab's last step, `problem.apply(optimal, params, idd)`, needs it: a student who comes from the panel can use `idd = evaluator.eplus.idd` (the evaluator's cell defines `evaluator`). The Lab could use that spelling in its last step so that the tail of the notebook also runs after the panel's cell. |
| 11 | Comments teach (what a selector is, why the windows are one column) | Comments report (writes N objects, field "...", the option numbering, why `sim_idf`) | Prose, not code. |
| 12 | No blind rewrite: the Lab model's six `WindowShadingControl` objects use the shading device material `blind_20001`, not a shaded construction | When a variable's definition carries `shading` the panel writes a block that rewrites the blinds | Not exercised by the Lab (the panel's text for the Lab problem has no such block). The block writes into `idf`, the Lab never edits `idf` before `sim_idf = idf.copy()`. |
| 13 | The tutorials (`Besos_overview`, `Surrogate_Modelling`, `Optimization`, `AdaptiveSampling_besos_example`) also vary the window-to-wall ratio with `window_to_wall.wwr(low, high)`, a `GenericSelector` | The panel has no geometry variable and cannot write one | Consistent with "geometry is given". The Lab itself does not use it. Nothing to reconcile unless the panel gets a wwr option; then it would have to emit the same setter (or import `window_to_wall`). |
| 14 | After the cell the Lab writes the chosen design with `problem.apply(idf.copy(), design, idd)` and `.save(...)` | Not part of the cell | A later cell of the student. |

## What a student who defined the problem in the panel sees in the Lab's later cells (checked 9 October)

Which cells of `Laboratory_solution.ipynb` need a name that only the Lab's own "Define the problem" cells create. Method: the notebook was run on EnergyPlus (a) as it is, (b) with the parameter renamed
(`name='Windows types'` -> another name), (c) the *old* text of the cells below with that renamed parameter, and (d) as a panel student would work: the panel's cell for the Lab problem (the golden
`tests/backend/golden/bdopt_lab_optimal.py.txt`, with its objectives list replaced by the Lab's three meters), then `sim_samples = evaluator.evaluate(samples, keep_input=True)`, then the Lab's cells from "Setup the dataset for the Surrogate Model" to the end.

What the panel writes differs from the Lab in three ways that reach the later cells: the glazing is **one column per window** (`Windows construction Block1B:Kitchen_Wall_5_0_0_0_0_0_Win`, ...; 9 columns, not one called `Windows types`), the option order is the
panel's (`triple_glazing`, `double_glazing`, `single_glazing`), and the panel's cell does not define `idd`, `win_arr`, `window_names` or `windows`.

| Cell (code) | Old text | What the student saw | Now |
|---|---|---|---|
| 55 | `inputs['Windows types'] = inputs['Windows types'].map(glazing_code)` with `glazing_code` from `win_arr` | `NameError: win_arr` (if cell 23 was skipped), else `KeyError: 'Windows types'` (confirmed by running (c)) | `glazing_code` is built from the problem: every parameter with `kind == 'categorical'`, its options in the problem's order, whatever its name. A new function `encode_options(table)` applies it |
| 85 | `X['Windows types'] = X['Windows types'].map(glazing_code)` inside `surrogate_func` | the same `KeyError`, when the surrogate is called (cell 86) | `surrogate_func` calls `encode_options(designs)` |
| 102 | `problem.apply(optimal, optimal_params, idd)` | `NameError: idd` if cell 14 (the exploration of the Material objects) was not run | `evaluator.eplus.idd`, which the panel's evaluator also has |
| 50 | `viz.correlation_heatmap(sim_samples, problem)` | works: bdopt codes the options itself | unchanged |
| 53, 81, 91-100, 104, 106 | use `features = list(samples.columns)`, `problem`, `evaluator`, `objectives`, bdopt's own surrogates | work with any names | unchanged |

Results: (a), (b) with the new text and (d) ran to the last cell (114 s, 117 s and 178 s, 10 or 20 simulations of `lab_building.idf`); (c), the old text with the renamed parameter, stopped at cell 55 with
`KeyError: 'Windows types'`. Two limits of (d): the panel's golden problem has **one** objective; the Lab's hand-built scikit-learn cells (GP: `scaler_out.inverse_transform(best_gp.predict(...))`) assume at least two, because
scikit-learn's Gaussian process returns a 1-D array for a single output; with the golden text unchanged the Lab stopped at cell 67 (`Expected 2D array, got 1D array`). The Lab asks for three meters, so a student who follows it
does not meet this. And the Lab has one column for the glazing of the nine windows while the panel writes nine; the networks then have more inputs, and their errors are not comparable with the Lab's.

Row 5 of the table above is therefore settled on the Lab's side (the cells find the categorical columns from the problem); the panel can name the variables as it likes. Row 10 is settled too (`evaluator.eplus.idd`).

## Checks (what I ran)

In image `jupyter:smartbuilding-surrogate` (`--memory=2g`), construct only: no `evaluate()`, no `run()`, no EnergyPlus run.
One script (a) executed the code cells of `Laboratory_solution.ipynb` from the top to the cell that builds the evaluator
(cell 33), (b) executed the full text of the panel's cell above after `idf = load_idf("lab_building.idf")` and
`epw_file = "ITA_Torino.160590_IWEC.epw"` (the two names the platform injects), and compared the two. Every line passed:

* both define `problem` (7 parameters, 3 objectives) and an `EnergyPlusEvaluator`; constructing the evaluator validates every
  selector against the IDD of EnergyPlus 9.6;
* the Lab's `samples` has 10 rows, the panel's 20; **the same 7 columns in the same order**;
* same parameter names, same objective names, same value descriptors (`repr` equal), same kinds;
* every parameter writes the same number of objects in both: 1, 1, 9 (windows), 7 (`Lights`), 7
  (`ZoneVentilation:DesignFlowRate`), 6 and 6 (`WindowShadingControl`);
* the same three random designs (the same unit-cube points decoded by each problem) written with `Problem.apply` into copies of the
  model give **identical IDF text** in both cases, and differ from the original model;
* both evaluators simulate a copy of the model with no `Output:Variable` (the model has 38, and keeps them in `idf`),
  with `out_dir=/tmp/bdopt_runs`, `err_dir=outputdir`, `processes=2`;
* the `fieldIndex` values of `lab_problem_for_panel.json` (written by hand, schema 2) equal the position of the field in the IDD of
  EnergyPlus 9.6 (`Material` Thickness 2, `FenestrationSurface:Detailed` Construction Name 2, `Lights` Watts per Zone Floor Area 5);
  for the variables that do not carry one, the IDD positions are 7 (`Air Changes per Hour`), 7 (`Setpoint`) and 13 (`Setpoint 2`);
* `evaluator.eplus.idd` exists on the evaluator the panel's cell builds (row 10 above).

Not done: no simulation of either cell (so the equality of results is implied by the equal IDF text, not measured), and the
panel's text for a problem that needs the blind rewrite or `Schedule:Compact` positions was not exercised (the Lab has neither).
Also not run: the Lab's tail (`problem.apply(optimal, params, evaluator.eplus.idd)`) after the panel's cell.
