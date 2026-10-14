# Intelligent Building Optimization

A virtual lab where EnergyPlus stands in for a real building. You optimise a design, choose the sensors and actuators of the
model, and then build the digital chain of a smart building yourself (device gateway, MQTT/database integration, data analysis
and, optionally, a controller or an RL agent), running it from a BMS control room and comparing it with a baseline run driven
by EnergyPlus' own native control.

## Quick start

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), [Git](https://git-scm.com/) and
[Python 3](https://www.python.org/downloads/), then run in a terminal:

```bash
git clone https://github.com/LorenzoBottaccioli/IntelligentBuildingOptimization.git
cd IntelligentBuildingOptimization
cp .env.example .env
python tests/tutorials/fetch_iwec.py
docker compose build jupyter_image_builder
docker compose up --build -d
```

Wait about two minutes, then open <http://localhost>. The first time, the platform opens the **Demo** session by itself.

What the steps do:

- `cp .env.example .env` creates the file Compose reads the InfluxDB and Grafana passwords from. Without it those two do not start.
- `fetch_iwec.py` downloads the Turin weather file of the Demo and the tutorials. It is not in git (ASHRAE licence, see `NOTICE.md`).
  Without it the Demo has no weather and the tutorials cannot simulate.
- `docker compose build jupyter_image_builder` builds the Jupyter image you work in. `up` never builds it, and without it `up`
  stops with `pull access denied for jupyter`.
- `docker compose up --build -d` builds the other images and starts the 12 containers.

You need about 11 GB of disk, an internet connection for the first build, Docker given at least about 8 GB of memory (tested with
7.6 GB; the minimum was not measured), and these ports free: 80, 1883, 3000, 5000, 8080, 8086, 8123, 8443, 8889 and 8892.

Measured on a clean clone (12 CPUs, no build cache, base images already pulled): the Jupyter, backend, eptofmu and frontend images
build in 3 min 48 s together; the containers start in 13 s and the backend answers after about a minute. openHAB can take about
five minutes to report healthy on its first start. Pulling the base images the first time is extra (Home Assistant alone is 3.5 GB).

## Services

| Service | URL | Purpose |
| --- | --- | --- |
| Frontend | <http://localhost> | The platform UI |
| Backend API | <http://localhost:5000> | Flask: IDF editing, FMU export, `/bms` (Control room) |
| Surrogate notebook (`jupyter_surrogate`) | <http://localhost:8889> | Design-space exploration |
| Workspace notebook (`controller`) | <http://localhost:8892> | The students' Jupyter, root = `Workspace/` |
| `bms_services` | (no port) | Supervisor that runs the students' scripts and the building, only on request from the Control room |
| MQTT broker (`mosquitto`) | `localhost:1883` | Messages between the students' scripts |
| InfluxDB | <http://localhost:8086> | Time-series storage (1.x) |
| Grafana | <http://localhost:3000> | Dashboards (also in the UI: BMS > Dashboards) |
| openHAB | <http://localhost:8080> | HMI (also in the UI: BMS > Operator panel) |
| Home Assistant | <http://localhost:8123> | Second HMI, the same points as openHAB (also in the UI: BMS > Operator panel) |
| `energyplus`, `eptofmu` | (no port) | Idle sidecars driven by the backend with `docker exec` |

## Folder layout

| Folder | Content |
| --- | --- |
| `Workspace/` | The students' code, mounted in `controller` and `bms_services`: `devices/` (gateway), `iot/` (subscriber, data notebooks), `ai/` (controller, agent training, forecasting, `models/`), `logs/`. Filled from `backend/notebook_templates/workspace/` on a session reset |
| `Field/` | FMUs and `parameters.py` written by the FMU export, plus `points.yaml` (emergency gateway only) |
| `gateway/` | Platform code, read-only in the containers: `building.py` (library the students use in `devices/gateway.py`), `supervisor.py`, `emergency_gateway.py`. See `gateway/README.md` |
| `backend/`, `frontend/` | Flask API and React UI |
| `conda-environment/` | Python environment of the Jupyter image and `fmi_mlc` |
| `eptofmu/`, `energyplus/`, `grafana/`, `influxdb1/`, `mosquitto/`, `openhab/` | Service configuration |
| `tutorials/` | Source of the four tutorial notebooks of the demo session (bdopt overview, surrogate modelling, optimization, adaptive sampling) with their model, weather file and stored results. Built by `tests/tutorials/make_tutorials.py` |

## The student workflow

The menu follows the order of the work. Code is **written** in sections 2-4
(each page opens its file in the Workspace Jupyter) and **run** only from
BMS > Control room; nothing starts by itself.

1. **Surrogate Design Optimization** — *Problem definition* (upload an IDF + EPW; a
   one-day probe simulation discovers the report variables `.rdd`, meters `.mdd` and
   actuators `.edd`), then *Surrogate modelling* (notebook) to explore envelope variants.
2. **Building & devices** — *Model editor* (edit the IDF: comfort models, indoor CO2, which
   report variables and meters are written, any class; *Check model* runs a day), *Sensors & actuators* (what to monitor and control: choose a
   type, then which one, then where, and add a whole selection at once; roles and action bounds),
   *EMS programs*, and *Gateway*: the students write `devices/gateway.py` with
   `building.py`, choosing the MQTT topics and payloads (the prefix `platform/` is
   reserved).
3. **Weather** — two pages. *Explore weather* looks inside an EPW file without changing it (the place, annual
   figures, curves of the year, month by month, every hour with zoom). *Create & edit weather* holds the weather
   library (any file can become the session weather), the ways to make a file (one place, chosen once, and four
   sources: an annual EPW for each year the student chooses from the Open-Meteo archive; a typical year from the
   EnergyPlus weather list, 3000+ stations, searched by name or nearest to the place; a typical year from PVGIS;
   links and an uploader for anything else) and the editor of a file (the place, or the temperature, humidity, wind,
   radiation or pressure, for the year or some months, with a preview; an edit is saved as a new file).
4. **IoT & data** — *Subscriber* (`iot/subscriber.py`: subscribe to their topics and
   store in InfluxDB) and *Data notebooks* (`data_access.ipynb`, `energy_signature.ipynb`).
5. **AI (optional)** — *Controller* (`ai/controller.py`, from IF-THEN rules to RL),
   *Agent training* (`AgentTraining.ipynb`), *Forecasting* (`forecasting.ipynb`).
6. **BMS** — *Control room* (start/stop the services and the baseline or controlled
   building, read logs; set the simulated period; export the FMU (writes the FMUs and
   `parameters.py` to `Field/`; says when the FMU is out of date with your choices); run the model in
   EnergyPlus alone over that period, up to a year, which stores everything the FMU would carry in the
   `direct_building` InfluxDB database without any FMU or student code), *Operator panel* (openHAB and Home Assistant) and
   *Dashboards* (Grafana, datasource "InfluxDB Direct" for that run).

The student-facing description of the Workspace is in
`backend/notebook_templates/workspace/README.md`.

## The demo session

A fresh platform (no session saved, no model uploaded) opens **Demo - bdopt tutorial** by itself the first
time the backend starts; on any other instance it is simply listed in the Sessions menu. It holds
`test.idf` (a small house) with the Turin weather file, its design problem (insulation, glazing, lighting
power against annual electricity, heating and cooling) and the four tutorial notebooks, opened from
Surrogate Design Optimization > *Tutorials*: **1** bdopt overview, **2** surrogate modelling, **3** optimization, **4** adaptive sampling.
The notebooks can be used in class and left to the students as material.

The demo is also a complete, working smart building, so it can be shown without any set-up. Its Workspace holds a
gateway, a subscriber and a controller that are already written; `Field/` holds the two FMUs exported from the model;
openHAB (its Overview, Floor plan and Controls pages), Home Assistant (a dashboard with the plan of the building, the
rooms, the energy and the history) and Grafana (*Demo building*, its home dashboard) are set up, and InfluxDB holds a recorded
run, so the dashboards are not empty. Press **Play** in BMS > Control room: start the subscriber and the controller, then the
building (the demo was made with *controlled* and *scaled*). The controller of the demo is a plain time program: it is there to
show the system, not to save energy.

**The Lab** (*Lab*) is a second shipped session. It has no model: the student uploads
`lab_building.idf` from the bar at the top, which is part of what the Lab teaches. Its surrogate notebook
holds the text of the laboratory (the course's `Laboratory.ipynb`, written for bdopt) with empty cells to write the code in.
It is listed in the Sessions menu and **never opens by itself**: a new instance always starts on the demo. Every other
session starts from nothing.

The weather file of the demo and of the tutorials (`ITA_Torino.160590_IWEC.epw`) is not in git (see `NOTICE.md`): run
`python tests/tutorials/fetch_iwec.py` once after cloning, before building the backend image. Without it the platform starts,
the demo and the Lab open, and Play works (the FMU carries its own copy), but the surrogate notebook and the tutorials have
no weather file to simulate with.

- The notebooks run in about 4, 3 (stored simulations), 8 and 3 minutes. The 50 simulations of notebook 2 are stored
  in `surrogate_simple_simulation.csv`; `RESIMULATE = True` runs them (about 12 minutes). Notebook 3 has
  `FULL_STUDY = True` for a larger EnergyPlus-based study.
- The tutorials belong to the session, so a student's changes are saved with it. They are *not* in
  `backend/surrogate_notebooks/` in the repository: that folder is the working state and opening or resetting a
  session empties it. The source is `tutorials/`; the copy that ships is inside the seed.
- **Looking inside the surrogate.** `tutorials/explore.py` (next to the notebooks, plain Python) holds the tools of part 3
  of notebook 2, of the end of notebook 3 and of notebook 4: `ParameterExplorer` (a slider per parameter, with tabs for the prediction and
  its uncertainty, sections, a map of two parameters, and a comparison of two saved designs), `tornado` and `sobol_indices`
  (which parameters matter), `learning_curve` (does the surrogate need more simulations), `parallel_coordinates` (the
  brushable plot of the original course notebooks, in plotly) and `ParetoExplorer` (weights on the objectives choose a design
  of the Pareto front, with a button that simulates it). They need the widgets of Jupyter Notebook 7 and plotly, which image B
  now contains (`conda-environment/surrogate/`, +90 MB). Widgets do not appear in a static export (HTML, PDF) unless the
  widget state is saved: for handouts export from a session where the notebook has been run with the state saved.
- **Adaptive sampling** (notebook 4): `bdopt.adaptive.AdaptiveSampler` with LOLA-Voronoi, first with one objective (the heating
  demand) and then with the three objectives together, against a Latin hypercube of the same size. It reuses the 50
  simulations of notebook 2 as the starting designs, the test designs and the comparison; the only new simulations are the
  two runs of 16 designs that the sampler asks for.
- **How it ships.** `backend/seed_sessions/bdopt-demo/` has the layout of a saved session and is baked into the
  backend image. At start, `sessions.seed_sessions_if_missing()` copies each seed into `sessions/` once (never over
  an existing session, and not again after a teacher deletes it: `sessions/.seeded.json`), and
  `sessions.open_demo_if_empty()` opens the demo (and only the demo) when there is no current session and no model in
  `uploads/`. It waits up to 90 s for InfluxDB and Grafana and restores the demo's data and dashboards over them only if they
  are empty (`session_stores.pristine()`); otherwise they are left as they are and the log says so.
  What a session carries of openHAB and Home Assistant includes the plan of the building (`html/floorplan/*.svg`,
  `www/floorplan/*.svg`), and of Grafana its home dashboard (`grafana/preferences.json`).
- **Rebuild the seed** after changing the notebooks: run `python tests/tutorials/make_tutorials.py`, then follow
  `tests/tutorials/README.md` (a throwaway backend with its own EnergyPlus container, never the live stack).
- The surrogate notebook of a seed is written for bdopt; with `SURROGATE_ENGINE=BESOS` opening it replaces it with the
  BESOS template and keeps the original beside it.

## Architecture notes

### Exporting a quantity always goes through EMS

`ExternalInterface:...From:Variable` can only reference an `Output:Variable` — never
a meter and never an actuator directly. So every observable quantity is wired
through the same chain, built automatically by `backend/ems_chain.py`:

```
source (report variable | meter | actuator)
  -> EnergyManagementSystem:Sensor           (skipped for actuators)
  -> EnergyManagementSystem:OutputVariable
  -> Output:Variable, EMS, <name>
  -> ExternalInterface:...From:Variable, key "EMS"
```

This is why District Heating / District Cooling / Electricity need no special
handling by the student: they are meters, and the chain absorbs the difference.

**The EMS subsystem must actually run.** `EnergyManagementSystem:OutputVariable`
stays silent unless at least one EMS program is invoked, so
`methods.ensure_ems_runtime()` injects a no-op program named `donothing` with a
calling manager at `BeginTimestepBeforePredictor`. It is idempotent and runs after
every model mutation.

### The uploaded IDF is never edited in place

`backend/idf_session.py` holds the parsed model in memory and flushes it to
`backend/uploads/<name>.idf`, while a pristine copy of the upload is archived in
`backend/originals/`. "Ripristina originale" restores it without a re-upload.

The working copy stays in `uploads/` because the rest of the stack addresses it
there: the eptofmu container only looks in `/workspace/uploads/<basename>` and names
the FMU after it, `inject_data.py` globs `uploads/`, and the export bundle ships
that same file.

### The idle sidecars are deliberate

`energyplus` and `eptofmu` run `tail -f /dev/null` on purpose. The backend drives
them with `docker exec` (`methods.py::run_energyplus_simulation` and
`::run_conversion`), which is also why the backend mounts `/var/run/docker.sock`.
Neither is dead configuration.

### Telemetry

There is no platform bridge to the database: the topics and the storage schema are
designed by the students. Their `devices/gateway.py` publishes to MQTT, their
`iot/subscriber.py` subscribes and writes to InfluxDB (`base_building` for the
baseline run, `controlled_building` for the controlled run). The prefix `platform/`
is reserved for the platform (for example `platform/building/status`).

MQTT is for telemetry and commands between the students' scripts; the building
itself runs in-process in the gateway through the FMU (`gateway/building.py`).

## Credits and licences

What the platform is built on, under which terms and how to credit it is in [`NOTICE.md`](NOTICE.md) (summary in the UI, page
*Credits & licences*); the licence texts that must accompany redistributed files are in [`licenses/`](licenses/) and the open points
(the IWEC and Meteonorm weather files, which are not in git: `tests/tutorials/fetch_iwec.py` fetches the IWEC one; material adapted from BESOS, which is GPL-3.0) are in
[`docs/licence_audit.md`](docs/licence_audit.md). The licence of the platform's own code has not been declared yet.

## Known risks

- **InfluxDB 1.x is end-of-life.** The stack pins `influxdb:1.11.8` and the v1
  Python client. Migrating to 2.x/3.x means a different query language, client
  library and Grafana datasource configuration — a separate project, deliberately
  out of scope.
- **Single-tenant by design.** One Compose stack serves one student group; there is
  no per-user isolation of files, notebooks or databases.
- **`.env` is required.** Without it Compose substitutes empty credentials and
  InfluxDB and Grafana fail to start.

## For the teacher

- **Emergency gateway.** If a group is stuck on its own `devices/gateway.py`, enable the
  platform's ready-made gateway (`gateway/emergency_gateway.py`, driven by
  `Field/points.yaml`) with a flag file; the Control room then starts it instead of the
  students' gateway:

  ```bash
  docker exec bms_services touch /home/jovyan/work/.emergency   # enable
  docker exec bms_services rm /home/jovyan/work/.emergency      # disable
  ```

  Details and the MQTT contract: `gateway/README.md`.
- **Docker Desktop must not suspend during lessons.** Turn off the resource saver
  (Settings > General) and keep the machine awake, otherwise running simulations and
  services stop.
- Logs of the students' scripts are in `Workspace/logs/<folder>_<file>.log`.
