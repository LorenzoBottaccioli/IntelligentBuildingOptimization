# Phase 1 results: image B (bdopt) next to image A (BESOS)

Measured on 2026-10-08, Docker Desktop 27.3.1 (VM 7.6 GB), bdopt `552b9089d8bea2f7a634456241725d01f9f7bbef`
(public repo `LorenzoBottaccioli/bdopt`, `main`). Everything below was run, not inferred.

## Image `jupyter:smartbuilding-surrogate` (`conda-environment/surrogate/Dockerfile`)

| | Image A today | Image B |
|---|---|---|
| Size (sum of `docker history` layers) | 11.54 GB | **1.17 GB** |
| Python / numpy / pandas / scikit-learn | 3.9 / 1.26.4 / 2.3.2 / 1.6.1 | 3.11 / 2.4.6 / 3.0.6 / 1.9.1 |
| EnergyPlus | 9.6.0 (base image) | 9.6.0 (copied from `nrel/energyplus:9.6.0`, 227 MB) |
| BESOS, Harlow, TensorFlow, torch | yes (torch 1.13.1 with CUDA 11) | none |

`docker images` shows 1.49 GB for B and 17.8 GB for A; the sum of layers is the agreed metric.
Versions are frozen in `conda-environment/surrogate/constraints.txt` (118 packages); a rebuild gives an
identical `pip freeze` (checked).

## Checks (all passed)

- EnergyPlus runs in B: `ldd` on the binary and on `libenergyplusapi.so` shows no missing library; `energyplus --version` = 9.6.0-4b123cf80f.
  Needed from the system: libx11-6, libgomp1, libexpat1.
- bdopt finds EnergyPlus through `EPLUS_PATH`; `bdopt eplus list` = 9.6.0.
- bdopt's own tests in B (`--target test`): 150 pass, 2 skipped (lightgbm and xgboost are optional extras).
  The 19 tests marked `eplus` could not run: they look for `ExampleFiles/5ZoneDDCycOnAny.idf` and
  `WeatherData/` inside the EnergyPlus install, which `nrel/energyplus` does not contain. Not a bdopt or image defect;
  the platform's own models (below) replace them.
- Jupyter in B: same entrypoint settings as A; `Content-Security-Policy: frame-ancestors *` present, no token,
  kernel `python3`, `/tree`, `/lab`, `/api/contents`, `/api/status` all HTTP 200, identical to the running legacy service.
  A notebook executed by the kernel imports bdopt 0.1.0 and runs `energyplus --version`.
- **bdopt vs the platform's stored results** (`platform_tests.py --check`, re-simulating the 5 stored test points of
  each test with EnergyPlus 9.6 in B), max relative difference:
  T1 7.73e-08, T2 2.35e-08, T3 1.63e-04, T4 4.67e-05, T5 9.34e-05, T6 3.53e-04, T7 2.79e-07.
  Same values as bdopt's README claims. The 1e-4 gaps on T3-T6 are NOT explained (candidates: BESOS version
  2.1.3, Windows vs Linux EnergyPlus build, object order); to be investigated in phase 5.
- E1_RES1 (916 KB IDF, 141 Output:Variable): bdopt loads it in 0.06 s, copies it in 0.01 s (eppy 0.6.7 took 130 s to save it).
  Its serialised text is 0.33 MB vs 0.92 MB for the file: comments are not kept (check that the Model Editor reloads it, phase 5).
  Two annual runs, 2 processes: 85-100 s; **peak container memory 522 MiB** (sampled every ~2 s; 4 processes not measured);
  more lighting gave more electricity and less heating, as expected.
- Run directory location: `out_dir` on the Windows bind mount is **3.0x slower** than on the container's `/tmp`
  (105 s vs 35 s for 2 Test 1 runs, order swapped and repeated, identical results). The cell generated in phase 3 must use `/tmp`.

## What is NOT done / not verified in phase 1

- jupyter_surrogate was not switched to B: the running legacy service still serves the BESOS cell, which cannot run in B.
  `docker compose -f docker-compose.yml -f docker-compose.bdopt.yml config` resolves as intended (image B, 2 volumes,
  `depends_on: backend`); `up` with the override was not run on the live platform.
  (10 Oct 2026: `docker-compose.bdopt.yml` no longer exists, it was merged into `docker-compose.yml`.)
- The default `docker compose up --build` is unchanged: `surrogate_image_builder` only exists under `--profile build`.
- Not committed. The 19 `eplus` tests of bdopt, bdopt with 4 processes, and the TorchMLP extra were not exercised.
