# Candidate: one image for A (runtime) and B (surrogate) — `jupyter:smartbuilding-unified`

Built and tested 10 Oct 2026. Nothing of the live stack was touched (no container recreated, compose files unchanged).
Recipe: `conda-environment/Dockerfile.unified` + `environment.unified.yml` = image A's recipe on **Python 3.10** (was 3.9), with
bdopt (pinned to e895ae5 = v0.2.0), pymoo, plotly and ipywidgets installed on top by pip under a pin file that keeps numpy 1.26.4,
scipy 1.13.1, pandas 2.3.1, scikit-learn 1.6.1, matplotlib 3.9.4, torch 1.13.1+cpu. `EPLUS_HOME` added next to `ENERGYPLUS_HOME`.

| | A | B | unified |
|---|---|---|---|
| Size (sum of `docker history` layers) | 1.80 GB | 1.24 GB | **1.92 GB** (A+B = 3.04 GB) |
| Python / numpy / pandas / scikit-learn | 3.9 / 1.26.4 / 2.3.1 / 1.6.1 | 3.11 / 2.4.6 / 3.0.6 / 1.9.1 | 3.10 / 1.26.4 / 2.3.1 / 1.6.1 |

`pip check`: no broken requirements.

## Runtime side (scripts of this folder; Field/ of the repo is empty now, so the session's `field/` copy was mounted)
- `building_smoke.py` 24 steps: output **identical** to image A's (same FMU, same run), last-step Electricity_Facility 19575.92161265211.
- PPO 2000 steps, seed 1: weights sha256 `e9374dfd43fd5778`, predictions and episode returns (-314.3768 twice), env trace: **identical** to A.
  Times (15 s vs 97 s on 9 Oct) are NOT comparable: the 9 Oct runs were on a busy machine.
- `AgentTraining.ipynb` 300 steps: no failed cell, return -314.38 over 1008 steps, cgroup peak 650 MB.
- supervisor end to end: building finished 1008 steps, 1689 messages, supervisor exit 0 on SIGTERM. Offline notebooks: only the intended TODO errors.
- Jupyter: server answers, kernels `conda_environment` and `python3` start.
- Not done: the compose mounts of fmi_mlc still point to `lib/python3.9/...` (harmless here: the image carries the current fmi_mlc, the run used that).

## bdopt side
- bdopt unit tests (`-m "not eplus"`): 167 passed, 2 skipped (lightgbm, xgboost), **1 failed**:
  `test_new_sklearn_surrogates_learn_the_response[lasso_polynomial]` — `ElasticNetCV(alphas=60)` needs scikit-learn >= 1.7
  (1.6.1 wants an array); bdopt declares `scikit-learn>=1.2`, so this is a bdopt bug exposed by the older pin.
- Platform tests vs stored results (`platform_tests.py --check`), max relative difference, unified (image B in brackets):
  T1 7.73e-08 (7.73e-08), T2 2.35e-08 (2.35e-08), T3 1.91e-04 (1.63e-04), T4 4.15e-05 (4.67e-05), T5 6.11e-05 (9.34e-05),
  T6 1.07e-04 (3.53e-04), T7 2.79e-07 (2.79e-07). T3-T6 moved slightly; those gaps were already unexplained in B.

Raw outputs: `results/*_unified*`, `results/building_smoke_smartbuilding-*.json`.
