# Tutorials of the demo session

| File | What it does |
| --- | --- |
| `make_tutorials.py` | Builds `tutorials/*.ipynb` from the bdopt ports in `course_notebooks_bdopt/` (text rewritten for teaching, exercises, glossary) and copies the model, the weather file, `window_to_wall.py` and `image/` next to them. Stored outputs are cleared. |
| `correct_images.py` | Writes `tutorials/image/surrogate_overview.png` and `flow_diagram.PNG`: the figures of the original course notebooks (not redrawn) with the names of the old toolbox replaced, in the same font and size, keeping the transparency. Run it in image B with the course folder and the Windows fonts mounted (see its docstring). |
| `test_explore.py` | Unit tests of `tutorials/explore.py` on functions whose answer is known (Sobol' indices of an additive and of a product function, tornado, the explorer's tabs and A/B comparison, Pareto weights, plotly figure, learning curve). Run in image B: `docker run --rm -v "$PWD:/r" -w /r -e MPLBACKEND=Agg --entrypoint python jupyter:smartbuilding-surrogate -m unittest tests.tutorials.test_explore`. |
| `build_demo_seed.py` | Rebuilds `backend/seed_sessions/bdopt-demo/` through the platform's own routes on a throwaway stack (a `demo-backend` and a `demo-energyplus` container, port 5001), then removes the two containers. Needs Docker; about 4 minutes. |

Order after changing a notebook: `make_tutorials.py`, run the four notebooks (below), `build_demo_seed.py`, rebuild the backend image.

`tutorials/surrogate_simple_simulation.csv` and `tutorials/best_surrogate.pkl` are the stored results of notebook 2 (50 simulations,
seed 0) and its saved surrogate. After changing the problem or the model of notebook 2, run it with `RESIMULATE = True` (about 12 minutes)
and copy the two files it writes into `tutorials/`; a CSV with other column names is ignored and a surrogate that does not fit is
trained again, so a stale file does not break notebook 3.

## Running a notebook headless (image B, nothing is written to the repository)

```bash
cp -r tutorials /tmp/t && cd /tmp/t
MSYS_NO_PATHCONV=1 docker run --rm --memory=1g -v "$PWD:/work" -w /work --entrypoint jupyter jupyter:smartbuilding-surrogate \
  nbconvert --to notebook --execute --ExecutePreprocessor.timeout=5200 --output executed.ipynb 2_surrogate_modelling.ipynb
```

Measured on 10 Oct 2026, 12 cores shared with other jobs: see the table in the README of the repository root (section "The demo session").
