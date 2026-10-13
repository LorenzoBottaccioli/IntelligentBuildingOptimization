# Phase 2 results: bdopt extended in its own repository

Repository `LorenzoBottaccioli/bdopt` (public), `main` = `e895ae5`, tag **`v0.2.0`**. Image B
(`conda-environment/surrogate/Dockerfile`) is pinned to that commit. All of this was run, not inferred.

## What was added to bdopt

| | |
|---|---|
| `MultiSelector` | One design variable that writes the same value in several objects, classes and fields (one column in the design table). `MultiSelector.from_targets(...)` builds it from object names or mappings and merges consecutive targets with the same class and field. |
| Object-name lists | `FieldSelector("FenestrationSurface:Detailed", ["Win A", "Win B"], "Construction Name")` and `IDF.find(class, [names])`. Every listed name must exist: a typo is an error naming the missing objects, not a smaller selection. |
| YAML / JSON | `object:` may be a list, and a parameter may have `targets:` (names, or mappings with their own `class` / `object` / `field` / `field_index`). `selector_from_spec` is the single place that reads it. |
| Cache key of `FunctionReader` | New `Objective.cache_token()`: a fingerprint of the function (source, or bytecode and constants, plus defaults, plus `functools.partial` arguments). Meters and variables return `""`, so their keys and existing caches do not change. Closure and global values are NOT tracked (documented). |
| Docs | guide, API page, YAML page, changelog; version 0.2.0 (pyproject, `__version__`, `CITATION.cff`). |

## Checks (all passed)

- 20 new tests (`tests/test_multi_target.py`); one of them found a real bug in my first version of the fingerprint
  (`__module__` is `None` for `exec()`'d functions) which is fixed.
- Full unit suite: 168 passed, 2 skipped (lightgbm, xgboost are optional extras); `ruff` clean.
- 48 more tests including the runnable documentation snippets, the end-to-end study and the CLI with real EnergyPlus runs
  (18 min): all passed.
- **Real platform problem** (`tests/fixtures/platform/problem_demo_E1_RES1_multitarget.json`, E1_RES1): the 4 variables
  become 4 columns writing 103 individual targets (64 walls, 13 windows, 10 schedules, 16 lights), all validated against the
  model. The IDF written with `MultiSelector` is identical to the IDF written target by target, and 103 of 103 targets
  hold the chosen value (17 walls already held it, hence 86 objects changed). Two annual runs of that problem: 116-161 s.
- On the rebuilt image B (bdopt 0.2.0 installed from commit e895ae5, dependencies identical to `constraints.txt`): the unit suite again gives
  168 passed, 2 skipped (`tests/baseline/bdopt_0.2.0_unit_tests.txt`, the summary line is hidden by a double `-q`; counted from the dots); the
  real E1_RES1 problem above runs from the installed package; Test 1 against the platform's stored results = 7.73e-08, as with 0.1.0.

## Decisions and findings

- **Output constraints: not implemented.** The only place the course uses them is cell 20 of `Optimization.ipynb`
  (`constraints=["CO2:Facility"]`, `<=800`), present in 6 copies under `python_envs`; the cell after it runs
  `NSGAII(evaluator, ...)` with `evaluator`, not `evaluator_costrain`, so the constraint is defined and never used.
  Supporting them in bdopt would need extra non-objective output columns in the evaluator, surrogates and optimizer, with no user.
  Revisit if a real use appears.
- **`MeterReader(missing=...)` default left at `'zero'`.** The plan proposed `'error'`, but the platform's tests include
  `DistrictCooling:Facility`, which does not exist in a building without cooling; `'error'` would reject valid models.
- **eppy-style field names** (`Construction_Name`, `Watts_per_Zone_Floor_Area`, `Field_4`) are not accepted by bdopt. Phase 3's
  adapter maps them (underscores to spaces; `Schedule:Compact` `Field_N` to `field_index = N + 1`, checked on the demo
  problem) or uses the exact index computed with the backend's eppy.
- `wwr`, `expand_plist`: not added (the platform does not call them; the course Lab is decided in phase 4).

## Not done / not verified

- bdopt with 4 processes; the optional `torch` extra; Windows/macOS EnergyPlus runs.
- The 19 EnergyPlus tests of bdopt that need `ExampleFiles/` (not present in `nrel/energyplus`).
- The pip install of 0.2.0 from outside this machine was checked for the tag archive (HTTP 200) and the image build, not on a clean machine.
