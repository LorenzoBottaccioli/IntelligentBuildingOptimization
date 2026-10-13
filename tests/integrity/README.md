# Model integrity checks for the bdopt migration (phase 5)

Measured 2026-10-09. Nothing here modifies a model: the models are copied to a scratch folder and every run happens
there. Logs and reports of the runs described below are in `results/`.

Images: `jupyter:smartbuilding-surrogate` (image B: python 3.11, EnergyPlus 9.6, bdopt 0.2.0) and `backend:latest`
(python 3.9, eppy 0.5.63, IDD 9.6 at `/app/EnergyPlus-9-6-0/Energy+.idd`: the stack of the Model Editor).
Every container is started with `--memory=1g` and `--entrypoint timeout <seconds> python ...`, so it ends by itself.

## 1. Does a bdopt round trip keep the model?  Yes: 0 differences in 16 models

Models (16): the seven `Surrogate modeling examples/Test N` models, `tests/fixtures/platform/E1_RES1.idf`,
`tests/fixtures/platform/lab_optimal_mutated.idf`, `backend/originals/lab_optimal.idf` and the six models of
`Simulation examples` (there are six: Test 4 has no IDF of its own). Every one declares `Version,9.6`.

Procedure: copy the models into one folder (prefixes `surr_tN__`, `sim_tN__`, `orig__`), then

1. `roundtrip_save.py` (image B): `bdopt.load_idf(model).save(saved/model)`. All 16 load and save in 0.1-0.2 s each.
2. `roundtrip_compare.py` (`backend:latest`, eppy 0.5.63): load the original and the saved file the way
   `idf_session.py` does (`IDF.setiddname`, `IDF(path)`), compare the object count of every class and every field of
   every object, objects paired by position inside the class (strings equal after strip, or equal as floats; trailing
   empty fields ignored). It covers every class, not only the ones the Model Editor edits; classes the editor touches
   are flagged `editor` in the report.
3. `raw_text_compare.py` (any python, no eppy, no bdopt): the same comparison on a plain tokenizer
   (strip `!` comments, split on `;` and `,`). It cannot be fooled by a class that eppy would drop.

Result (`results/roundtrip_eppy_report.json`, `results/roundtrip_raw_text.txt`):

| | |
|---|---|
| models | 16 |
| objects compared (eppy) | 10 498 (E1_RES1 1 297, the others 387-1 002) |
| fields compared (eppy) | 146 099 |
| class-count differences | 0 |
| objects with a differing field | 0 (editor classes: 0) |
| classes whose objects only changed order | 0 |
| raw-text comparison | same object counts per class and same fields in all 16 |

Comments are lost by `save` (expected) and nothing else: no object added, dropped or reordered, no number reformatted.
The comparison is sensitive: a control with one Material thickness changed from the saved file to 9.99 is reported
(`objects with field diffs 1`).

Caveats:
- `bdopt` object counts printed by the first version of `roundtrip_save.py` (1 423 for E1_RES1) were wrong: the script
  summed `by_class(c)` over `classes()`, which counts a class twice when the file spells it in two cases. It now
  prints `len(idf.objects)`. The counts that matter are those of the two comparisons above, which agree.
- The full eppy comparison was run with the first version of `roundtrip_compare.py`, which kept the two eppy models
  in memory at once. Under the 1 GB cap it swapped (about 34 minutes of wall clock, `load_s` 10-248 s per file; on an
  uncapped machine it is minutes). It now loads one model at a time and flushes its output; that version was run on one
  model (Test 4 of Surrogate modeling: 0 differences, 14 s) and not on all 16.

Re-run (Git Bash, with `S` = a folder holding `models/` and `saved/`, `T` = this folder):

    MSYS_NO_PATHCONV=1 docker run --rm --memory=1g -v $S:/work -v $T:/t:ro --entrypoint timeout \
        jupyter:smartbuilding-surrogate 600 python /t/roundtrip_save.py /work/models /work/saved
    MSYS_NO_PATHCONV=1 docker run --rm --memory=1g -v $S:/work -v $T:/t:ro --entrypoint timeout \
        backend:latest 3000 python -u /t/roundtrip_compare.py /work/models /work/saved /work/report.json
    python raw_text_compare.py $S/models $S/saved

## 2. EMS fidelity: the original text and bdopt give the same meters, bit for bit

Model: `tests/fixtures/platform/lab_optimal_mutated.idf` (what students get: EMS programs, ExternalInterface removed,
blinds AlwaysOn), weather `backend/user_files/weather.epw` (Torino IWEC), EnergyPlus 9.6 in image B. Only the RunPeriod
of the scratch copy was changed (one winter week 1-7 January, one summer week 1-7 July, with a text edit of that
object).

- (a) `energyplus -w weather.epw -d dir in.idf`, the original text plus `Output:SQLite, SimpleAndTabular;` appended;
  meters read from `eplusout.sql`.
- (b) `bdopt.load_idf` of the same text, copy without Output:Variable (as the platform's cell does), `Problem` with one
  `Parameter` writing the value the file already has (Material "Urea Formaldehyde Foam_.1327", Thickness = 0.1327),
  `EnergyPlusEvaluator(..., cache=False, keep_dirs=True)`, one row.

| week | meter | (a) CLI, Run Period row [J] | (b) bdopt [J] | difference |
|---|---|---|---|---|
| 1-7 Jan | Electricity:Facility | 161 457 797.700034 | 161 457 797.700034 | 0 |
| 1-7 Jan | DistrictHeating:Facility | 193 329 978.933151 | 193 329 978.933151 | 0 |
| 1-7 Jan | DistrictCooling:Facility | 0 | 0 | 0 |
| 1-7 Jul | Electricity:Facility | 112 601 594.510820 | 112 601 594.510820 | 0 |
| 1-7 Jul | DistrictHeating:Facility | 134 380 586.794016 | 134 380 586.794016 | 0 |
| 1-7 Jul | DistrictCooling:Facility | 923 030 389.471900 | 923 030 389.471900 | 0 |

The tables of the (b) run directory (`eplusout.sql`) equal those of (a) at every frequency (zone timestep, hourly,
daily, monthly, run period). Run times: EnergyPlus 12-14 s (CLI), 13-14 s through bdopt.

The IDF that EnergyPlus received in (b) differs from the input text in exactly 45 objects (41 removed, 4 added), none of them an
EMS object: 41 `Output:Variable` removed (by the platform's `sim_idf.remove`), `Output:SQLite` and one
`Output:Meter ..., RunPeriod` per objective added by bdopt. The only difference in the EnergyPlus error tables is one
warning in (a): the `Output:Variable` request `Key=*, VarName=ERL SHADING CONTROL STATUS` (one of the 41 removed) was
"requested but not generated". That variable is not generated in the original either, so the model's EMS blind logic
does not expose it (not investigated further).

Pitfall found in my own first version of the script: adding the meter rows of all frequencies (E+ writes the same
energy at timestep, hourly, daily, monthly and run-period level) doubled the total; compare the Run Period row, or one
frequency.

Not covered: a full year (only two one-week windows), designs other than the base one, whether the EMS programs
change anything in these two weeks (the two paths agree; whether the programs act was not checked).

Re-run: put `lab_optimal_mutated.idf` in `$S/models/` and `weather.epw` in `$S/`, then
`MSYS_NO_PATHCONV=1 sh run_ems.sh $S $REPO` (logs `$S/ems_jan_week.log`, `$S/ems_jul_week.log`, about 2 minutes).

## 3. Models that declare another EnergyPlus version

Scan (read-only) of the repository and `C:\Users\Lorenzo\Documents\python_envs` for `.idf` files: 136 files (runs/output folders included in the count; versions 9.6: 86, 9.4: 15, 9.0: 18, 9.0.1: 2, 8.1: 12, no Version: 3).

- repository: every model (also `backend/originals`, uploads, demo and backup folders, session folders) declares 9.6;
  only the three `backend/datasets/Window*.idf` fragments have no Version object. The "exercise models declare 9.4"
  of `idf_version.py` are not in the repository.
- `python_envs`: 9.4 = `fmimlc_e+_openmod/f_5Zone_Default_v94.idf` (and 2 copies), the EnergyPlusToFMU `Examples/*`
  (3 files in each of 4 trees: `Actuator`, `Schedule`, `Variable`); 8.1 = the EnergyPlusToFMU `regression-test/fmux-*` files;
  9.0 / 9.0.1 = the BESOS example models in two `.venv` folders.

What bdopt 0.2.0 does (`other_versions.py`, `results/other_versions.log`, models 9.4, 9.0, 9.0.1, 8.1):

- `bdopt.load_idf(...)`: loads without complaint and reports the declared version (`9.4.0`).
- `EnergyPlusEvaluator(problem, idf, epw, ...)` raises at construction:

      EnergyPlusNotFound: the model is for EnergyPlus 9.4 but no such version is installed (found: 9.6). Install it
      (tools/install_eplus.py), pass eplus=..., or use auto_upgrade=True to convert the model to the newest installed version.

  (same text with 8.1 and 9.0). It is not a `VersionMismatch`: that one is raised later only when an EnergyPlus of
  another version is chosen and `auto_upgrade` is off.
- with `auto_upgrade=True`:

      TransitionError: no transition available from IDF version 9.4 towards 9.6 in the installed EnergyPlus versions;
      install an EnergyPlus version that ships the missing step (e.g. a release in between)

  So neither path works in image B (no IDFVersionUpdater). The platform's check (`_engine_problems` ->
  `idf_version.check`) keeps the cell from being offered; the text a student would otherwise see recommends
  `auto_upgrade=True`, which does not work here.

Re-run: `python other_versions.py /work/other_versions /work/weather.epw` in image B, with the four models copied
from the paths above.

## Part 4 - the EnergyPlus-only run (Control room, `backend/direct_run.py`)

The run IDF the platform builds (export baseline model, shared period, FMU points requested at Timestep,
the model's own other output requests dropped) must not change the physics. Measured 10 Oct 2026 on
EnergyPlus 9.6 in the `energyplus` sidecar, weather ITA_Torino IWEC:

- `test.idf` (3 points), 7 days: dropping the model's own output requests changes nothing (max |diff| 0); the series
  equals the untouched model, and equals the exported baseline FMU run through `gateway/building.py` (5e-15).
- `test.idf`, 365 days, 52,560 steps: direct run vs baseline FMU for the same year, identical timestamps,
  max |diff| 7e-15, 0 steps above 1e-9. Time: 6.5 s of EnergyPlus for the direct run (about 20 s with the InfluxDB
  write) against 96 s of EnergyPlus through the FMU.
- `lab_optimal.idf` (EMS model, 3 points), 7 days: 0 differences against the untouched model.
- The length of the period itself matters, as EnergyPlus defines it (shadow calculation is averaged over the run
  period): the first week of a 365-day run differs from a 7-day run by up to 0.018 degC on `test.idf`. Compare runs
  of the same period, never a week against a year.
- A platform FMU input on a window the model's own EMS already drives is read from that EMS actuator (values 0 and 6 in a
  July week of `lab_optimal`); an FMU input declared by hand and read by an EMS program makes the run refuse, since
  without the FMU that Erl variable would not exist.

Re-run (inside the backend container, see each docstring): `direct_run_check.py`, `direct_run_ems_input.py`. Unit tests of
the parts that need no EnergyPlus: `tests/backend/test_run_period.py`, `tests/backend/test_direct_run.py`.

## Files

- `roundtrip_save.py`, `roundtrip_compare.py`, `raw_text_compare.py`: part 1.
- `ems_fidelity.py`, `run_ems.sh`: part 2.
- `other_versions.py`: part 3.
- `direct_run_check.py`, `direct_run_ems_input.py`: part 4.
- `results/`: logs and reports of the runs above.
