# Instrumentation: research and tests (Sensors & actuators)

Numbers and checks behind the redesign of *Sensors & actuators* (11 Oct 2026). Nothing here is imported by the platform.

## The corpus

`generate_dictionaries.py` runs every example of EnergyPlus 9.6 (`C:\EnergyPlusV9-6-0\ExampleFiles`, 685 models) for
design days only, with `Output:VariableDictionary` and the verbose EMS dictionaries, and reads the `.rdd`, `.mdd` and
`.edd`. 628 give dictionaries (the other 57 read files next to the model, or are parametric templates). About 4 GB of work
files: delete them afterwards. `tests/fixtures/dictionaries/sample.json.gz` (84 models, 0.9 MB) is what the tests use and
reproduces the numbers of the whole corpus.

```
python tests/instrumentation/generate_dictionaries.py --eplus C:\EnergyPlusV9-6-0 --work %TEMP%\dicts --out tests\fixtures\dictionaries\sample.json.gz --every 8
python tests/instrumentation/measure_dictionaries.py tests/fixtures/dictionaries/sample.json.gz
```

## The rules, as functions

`frontend/src/instrumentGroups.js` (units to quantity, Rate/Energy pairs, prefix split above 40 items, meter parts,
actuator kind, zone defaults). Checked against the fixture:

```
node --test tests/instrumentation/instrument_groups.test.mjs
```

## The backend

`backend/instrument.py` (zones with geometry and owners, proposed ranges, writes in a block), `instrument_kits.py`,
`fmu_state.py`, `idf_session.try_get`. Run where eppy 0.5.63 and Flask are installed, with EnergyPlus 9.6 on the machine
(it runs once, for design days, to read the geometry):

```
python -m unittest tests.backend.test_instrument
```

## What the research found (628 models)

* Sensors: 50 unit strings, all classified. Quantity shares: power and energy 58.9 %, no unit 11.0 %, temperature 8.3 %,
  time and angle 7.3 %, flow and speed 6.0 %, mass/volume/pressure 4.2 %, humidity and CO2 1.8 %, coefficients 1.6 %, light 0.9 %.
* "Rate" is also the suffix of flows: only W, J and W/m2 pair. 21.6 % of the rows are W+J pairs.
* The longest list with quantity + first two words as subject has median 38 and maximum 67 (74 % of the models have one
  above 25). A prefix split with limit 40 gives a median of 69 lists per model, none above 40, at most 3 header levels.
* Actuators: 25 unit strings in the EDD; 12 (type, control) combinations have a blank or unknown unit and are told
  apart by the control type. In the sample 5 of 178 action kinds remain in "Other". The component list of one action has
  median 74, p90 130 and maximum 2 607.
* Meters: median 98 per model, maximum 1 502. 88.4 % have a resource token of the IDD, 63.0 % an end-use token; the rest
  are emissions, PlantLoop...Demand, Carbon Equivalent and meters of the user.
* IDD fields as a source of range: for 178 action kinds a field is found for 7 and bounds for 6. Thin: the model, then the
  unit, then a default do most of the work.
* eppy 0.5.63 (file only): demo 469 objects 0.12 s per save, ten saves 1.4 s against 0.15 s in one; a 4.2 MB hospital
  3.4 s per save, ten saves 41 s against 3.5 s in one.

## Clicks, the scenario of the canvas (5 temperatures, outdoor, one meter, 5 setpoints, export)

Counted from the interface on the demo (4 zones), not timed.

| | before | now |
|---|---|---|
| by hand | about 56 clicks and 10 typed values | 13 clicks, no typed value (type filter and tick for sensors, add; tab, tick, add for the meter; tab, filter, tick, add for the setpoints, whose range is proposed; Control room, Export) |
| with kits | n/a | 4 clicks: *Comfort control* (1), *Energy* (1), Control room, Export |

## Not covered

* Export duration and the Docker build were not measured: the Docker engine did not answer during the work.
* The unit tests replace `idf_session.mutate` (they write with the real `ems_chain` and eppy 0.5.63); the page was
  exercised against a stand-in server that runs the real modules, `mutate` and `ensure_ems_runtime` included, on a copy
  of the demo. Neither ran inside the `backend` container image, which was not rebuilt.
* "Via program" actuators (the EMS program mode) went through the batch only in the unit test, not in the page.
