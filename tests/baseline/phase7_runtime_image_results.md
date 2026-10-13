# Image A (runtime) rebuilt without BESOS, Harlow, TensorFlow, CUDA, wxPython: `jupyter:smartbuilding-runtime`

Recipe: `conda-environment/Dockerfile.runtime` + `conda-environment/environment.runtime.yml` (micromamba builder, finished env copied
onto `nrel/energyplus:9.6.0`, same env path `/opt/conda/envs/conda_environment`, same kernel name `conda_environment`,
same Jupyter flags). Measured 2026-10-08, nothing here is inferred.

| | legacy `jupyter:smartbuilding` | runtime `jupyter:smartbuilding-runtime` |
|---|---|---|
| Size (sum of `docker history` layers) | 11.54 GB | **1.80 GB** (the env layer alone is 1.49 GB) |
| Python | 3.9.23 | 3.9.23 |
| numpy / scipy / scikit-learn / matplotlib | 1.26.4 / 1.13.1 / 1.6.1 / 3.9.4 | 1.26.4 / 1.13.1 / 1.6.1 / 3.9.4 |
| PyFMI / Assimulo / paho-mqtt / SB3 / gymnasium | 2.18.0 / 3.7.1 / 2.1.0 / 2.4.1 / 1.0.0 | same |
| torch | 1.13.1 with CUDA 11 (3.2 GB with its nvidia libs) | 1.13.1+cpu |
| tensorflow, keras, harlow, besos, geomeppy, eppy, dask, pyomo, shapely, wxpython, lxml, nvidia | present | **absent** (import fails) |

pandas is 2.3.1 (conda) instead of 2.3.2 (pip override in the legacy image): the only version that moved.

## Checks (all passed)

- **The platform's own FMU stack, bit-identical.** `tests/runtime/building_smoke.py` drives `Field/lab_optimal_baseline.fmu` through
  `gateway/building.py` for 24 steps (EnergyPlus child process included). Outputs of the runtime image equal the legacy image's
  to the last digit (`Electricity_Facility` 19575.92161265211, `Zone_Mean_Air_Temperature_KITCHEN` 20.0, last timestamp
  2026-01-01T04:00:00). Reference and result: `runtime_smoke_legacy.json`, `runtime_smoke_runtime.json`.
- stable-baselines3 PPO trains 512 steps on CPU (`device=cpu`, torch 1.13.1+cpu, `cuda.is_available() == False`).
- `import fmi_mlc, fmi_mlc.eplus_health, fmi_mlc.fmi_gym` works; `paho.mqtt.client.Client(CallbackAPIVersion.VERSION2)` works.
- Kernels: `conda_environment` and `python3`.
- `import gym` prints Gym's own deprecation notice (the old `gym` is still installed because `fmi_mlc/fmi_gym.py` and 6 course
  notebooks import it; porting them to gymnasium is a separate decision).

## Not verified

- The Jupyter server of this image was not started (same entrypoint as the old one); the controller/bms_services containers were not recreated on it.
- `Workspace/ai/AgentTraining.ipynb` and the Control room were not run on this image.
- Peak memory of a long RL training; behaviour on the FMU with `controlled` run and inputs (only `baseline`, no inputs).
