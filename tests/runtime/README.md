# Can `controller` and `bms_services` move to image A (`jupyter:smartbuilding-runtime`)?

> **Historical (10 Oct 2026).** This is the study that justified the move; its measurements stand. The proposal was applied and then
> went further: `docker-compose.yml` no longer has `jupyter_env_builder`, the `x-jupyter` anchor or any reference to the old
> `jupyter:smartbuilding` (17.8 GB), and `docker-compose.bdopt.yml` was merged into it (`jupyter_surrogate` runs image B,
> `SURROGATE_ENGINE=bdopt`). Read "Compose changes" below as what was proposed then, not as the current file. The old image, and
> its `-legacy` tag used by the comparisons in this folder, may no longer exist on the machine: those runs cannot be repeated as written.

Measured 2026-10-09. Every run below was a throwaway `docker run --rm` container with `--network none`, `--memory=1g`, `--cpus=2`, one at a
time, the Workspace always a **copy** (the real `Workspace/` was never written; `Field/`, `gateway/` and `fmi_mlc` were mounted read-only).
Nothing touched the live platform. Raw results are in `results/`.

**Answer: yes.** Everything the two containers run executes on image A and gives the same numbers as on the old image. What changes for the
students is listed under "Differences" and "Risks". The compose change was `compose_runtime.diff` (applied since, see the note above).

## One thing about the test method (not about the images)

With `--network none` the container's own host name is not in `/etc/hosts`, and the FMU fails in `fmiInitializeSlave` with
`Get host by name failed` (it resolves the host name to open its socket to EnergyPlus). My first run failed for that reason on image A and
would on the old image. The scripts pass `--hostname rtbox --add-host rtbox:127.0.0.1`. On the compose network the name resolves, as it does today.

## What was run and what came out

| # | Test (script) | Image A runtime | Old `jupyter:smartbuilding` |
|---|---|---|---|
| 1 | Import census, re-derived with `ast` over `Workspace/{ai,iot,devices}`, `gateway/`, `conda-environment/fmi_mlc`, plus `reference/` and `Simulation examples/` (`import_census.py`, `results/census_*.json`): 36 third-party dotted names, each imported for real | all import, except `config`, `config.parameter` | the same two |
| | `config` is a local file of the old `Simulation examples/` notebooks, not run by these containers. Third-party packages used by the run scope: numpy, pandas, matplotlib, sklearn, paho, pyfmi, yaml, gym, gymnasium, stable_baselines3, fmi_mlc | | |
| 2 | `Workspace/ai/AgentTraining.ipynb` executed headless on kernel `conda_environment`, `TOTAL_TIMESTEPS=300`, all 12 cells, against `Field/lab_optimal.fmu` (`run_notebook.py`, `run_nb_container.sh`) | **no cell failed**; saves `ai/models/my_agent.zip`; evaluation of 2 episodes of 1008 steps: trained agent return -314.38; wall 253 s, RSS of the kernel 332 MB, cgroup peak 690 MB (includes page cache) | not run |
| 3 | `iot/data_access`, `iot/energy_signature`, `ai/forecasting` against a fake InfluxDB on localhost, plus one appended cell that does what a solution does (pivot/resample, Ridge, GradientBoosting, MAE/RMSE, matplotlib Agg, polyfit) (`notebooks_offline.py`) | all cells run; the only errors are the 8 `NotImplementedError` of the TODO cells, on purpose; appended cells OK | identical result, pandas 2.3.2 instead of 2.3.1 |
| 4 | `gateway/supervisor.py` end to end in one container with a tiny MQTT broker inside it (`supervisor_e2e.py`, `run_supervisor_e2e.sh`): retained status of the services, start/finish of `ai/controller.py`, building through `emergency_gateway.py --once` on `lab_optimal_baseline.fmu` for the full week (1008 steps), stop, SIGTERM. The live `energyplus_data` volume mounted read-only as in compose | all ok: building `finished`, exit 0, 18.9 s, 1692 messages on 5 topics, supervisor exit 0 on SIGTERM; peak 287 MB | all ok: 11.6 s, 1694 messages on the same 5 topics |
| 5 | Jupyter server of the image (the entrypoint command, login shell) answers `/tree` with `frame-ancestors *`, kernels `conda_environment` and `python3` start (`jupyter_startup.sh`) | ok, Jupyter Server 2.18.2 | ok, 2.17.0 |
| 6 | PPO 2000 steps, same seed (1), the environment and `PPO(...)` of the notebook cells, default torch threads (6), 1 GB (`ppo_compare.py`, `run_ppo_compare.sh`) | `learn()` 97.6 s, CPU 127.8 s, RSS 319 MB, peak 467 MB | `learn()` 94.9 s, CPU 115.2 s, RSS 428 MB, peak 514 MB |
| | **Numbers**: env trace of 12 random steps, trained weights (sha256), deterministic predictions, episode returns | identical to the last digit in both images (sha256 `e9374dfd43fd5778`, returns -314.3768 twice, predictions all 12.0) | identical |

Notes on 6: the time difference (2.8 s) is inside the noise of a machine shared with other agents; CPU time was 11 % higher on image A in
this single run, which I did not repeat. Memory is lower on image A (no CUDA runtime). After 2000 steps PPO has learned only to saturate the
action at `action_min` (12 degC) in both images: this is the notebook's default budget, not an image effect.

## Differences between the images (docker inspect / docker run)

| | old | image A | consequence |
|---|---|---|---|
| USER, WORKDIR, ports, entrypoint | root, `/home/jovyan/notebooks`, 8888, same `bash -lc jupyter notebook ...` | same | none |
| `LD_LIBRARY_PATH` | not in the image (compose sets it) | baked in; compose still sets the same value | none |
| PATH of the server and of the kernels | `/usr/local/EnergyPlus-9-6-0:/opt/conda/bin:...` (the login shell puts the **base conda**, Python 3.13, first) | `/usr/local/EnergyPlus-9-6-0:/opt/conda/envs/conda_environment/bin:...` | `!python`, `!pip`, a Jupyter terminal now use the env (3.9), no more the base 3.13. No `conda` command exists in image A |
| kernelspecs | `conda_environment` in `/root/.local/share/jupyter/kernels` (display name "Python (SmartBuilding RL)"), `python3` | `conda_environment` in the env prefix (display name "Python 3.9 (E+96, SB3)"), `python3` | the notebooks store `name: conda_environment`, which matches; only the shown display name differs. To keep "Python (SmartBuilding RL)" change `--display-name` in `conda-environment/Dockerfile.runtime` (not edited) |
| Jupyter Server / nbconvert / pandas | 2.17.0 / 7.16.6 / 2.3.2 | 2.18.2 / 7.17.1 / 2.3.1 | none seen |
| torch | 1.13.1+cu117 | 1.13.1+cpu | same results (above) |
| `fmi_mlc` baked into the image | old copy without `eplus_health.py` | **current** (md5 of the 5 files equal to the repo) | the compose mount still works (verified with a real mount in every run) and is now only a convenience |
| EnergyPlus | `/EnergyPlus-9.6.0-...` + symlink `/usr/local/EnergyPlus-9-6-0` | same | the FMU works with and without the `energyplus_data` mount |

## What the students lose (packages in the old image, absent from image A)

Run scope never imports them (census above), but a student may: **tensorflow, keras, tf-keras, tensorboard, seaborn, plotly, bokeh, statsmodels,
numba, networkx, openpyxl/xlrd, pyarrow, lxml, dask, h5py, scikit-optimize, pulp/pyomo, shapely**, plus BESOS, Harlow, eppy, geomeppy, epw.
`forecasting.ipynb` suggests only sklearn (Ridge, GradientBoosting), which is there. If the forecasting space is to offer Keras/statsmodels
or seaborn plots, they have to be added to `environment.runtime.yml` first. Full list: compare `tests/baseline/legacy_pip_freeze.txt` with
`pip list` of image A.

## Compose changes as proposed on 9 Oct (`compose_runtime.diff`, generated by `make_compose_diff.py`, checked with `git apply --check`; superseded, see the note at the top)

1. `bms_services` and `controller`: `image: jupyter:smartbuilding-runtime` (a key in the service wins over the one merged from `*jupyter`;
   checked by parsing the patched file with PyYAML in image A: both services get the runtime image, `jupyter_surrogate` keeps the old one).
2. `controller`: drop `depends_on: jupyter_env_builder`. That service has a `build:` of the old 17.8 GB image and, as a dependency, would be
   started next to the controller (it runs a Jupyter of its own).
3. New build-only service `runtime_image_builder` (profile `build`, `Dockerfile.runtime`, tag `jupyter:smartbuilding-runtime`), like the one of image B.
4. The anchor comment is updated. **`jupyter_surrogate` must keep `jupyter:smartbuilding`** (it is the BESOS fallback when
   `docker-compose.bdopt.yml` is not used) and keeps `depends_on: jupyter_env_builder`; do not change the anchor.

Where else the old name or `python3.9` appear: `docker-compose.yml` lines 6, 22 (anchor and `jupyter_env_builder`: keep, the fallback needs them),
the three `.../lib/python3.9/site-packages/fmi_mlc` mounts (python 3.9 in image A: **same path, no change**; the one of `jupyter_surrogate`
disappears with the bdopt overlay), `LD_LIBRARY_PATH` lines (harmless, optional to remove), `conda-environment/Dockerfile` (the old recipe, untouched),
`backend/engine.py` (a docstring only). No other file names the image.

## Not verified

- The containers were not recreated: `docker compose up` was not run (forbidden here), so the merged compose model was checked by YAML parsing, not by `docker compose config`.
- The students' own `devices/gateway.py`, `iot/subscriber.py` and `ai/controller.py` are templates with TODO sections; their real code and `paho`
  against the real Mosquitto/InfluxDB were not run. The broker in the supervisor test is my minimal one (QoS 0/1, retained), not Mosquitto.
- The 1692 vs 1694 messages of the building in test 4 were not analysed (topic set equal, count differs by 2; log/status messages depend on timing).
  The FMU numbers themselves are the identical env trace of test 6 and `tests/baseline/runtime_smoke_*.json`.
- Run times are from a machine shared with four other agents and the live platform: the speed comparison is indicative.
- The controlled run (FMU inputs driven by MQTT commands) was not run; `AgentTraining` drives the controlled FMU directly (test 2 and 6), which covers the inputs.
- Jupyter was tested through its REST API (kernel start), not through a browser or the frontend iframe.

## Files

`import_census.py`, `run_notebook.py` + `run_nb_container.sh`, `notebooks_offline.py` + `run_offline_notebooks.sh`,
`supervisor_e2e.py` + `run_supervisor_e2e.sh`, `jupyter_startup.sh` + `jupyter_probe.py`, `ppo_compare.py` + `run_ppo_compare.sh`,
`make_compose_diff.py` -> `compose_runtime.diff`, `building_smoke.py` (earlier), `results/`.
