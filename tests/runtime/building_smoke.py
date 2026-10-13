"""Smoke test of the runtime image (image A): drive the real FMU through the platform's own gateway/building.py.

    docker run --rm --memory=2g --entrypoint /opt/conda/envs/conda_environment/bin/python \
        -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
        -v <repo>/gateway:/opt/gateway:ro -v <repo>/Field:/home/jovyan/field:ro \
        -v <repo>/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro \
        -v <repo>/tests/runtime/building_smoke.py:/smoke.py:ro  <image>  /smoke.py [steps] [baseline|controlled]

Prints one JSON line with the outputs of the first and the last step. Running it in jupyter:smartbuilding-legacy and in
the slim image and comparing the two lines is the equivalence test of the FMU stack (pyfmi, assimulo, EnergyPlus child process).
(10 Oct 2026: the legacy image was removed from the stack and may be gone from the machine; the comparison was done on 9 Oct,
the script itself runs on any image with the runtime conda env, e.g. jupyter:smartbuilding-runtime.)
"""
import json
import sys

from building import Building

steps = int(sys.argv[1]) if len(sys.argv) > 1 else 24
run = sys.argv[2] if len(sys.argv) > 2 else "baseline"

b = Building(run=run, field_dir="/home/jovyan/field", publish_status=False)
b.start()
rows = [b.step() for _ in range(steps)]
b.close()
print(json.dumps({
    "fmu": b.fmu_path.split("/")[-1], "run": run, "steps": steps, "step_size": b.step_size,
    "outputs": list(b.outputs), "inputs": list(b.inputs),
    "first": rows[0]["values"], "last": rows[-1]["values"], "last_ts": rows[-1]["ts"],
}, sort_keys=True))
