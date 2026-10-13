"""Execute a notebook headless on the kernel `conda_environment`, cell by cell, and report time, CPU, memory and errors.

    docker run --rm --network none --memory=1g --entrypoint /opt/conda/envs/conda_environment/bin/python \
        -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
        -v <repo>/gateway:/opt/gateway:ro -v <repo>/Field:/home/jovyan/field:ro \
        -v <repo>/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro \
        -v <writable copy of Workspace>:/home/jovyan/notebooks \
        -v <repo>/tests/runtime/run_notebook.py:/run_notebook.py:ro  <image>  /run_notebook.py <notebook> [skip-cell-index ...]

The notebook is executed IN PLACE, so always pass a COPY of the Workspace (never the real one). Environment variables
reach the kernel (the notebook reads TOTAL_TIMESTEPS). Cells listed after the notebook path are replaced by `pass`.
Cells that raise do not stop the run (allow_errors); the last line is a JSON summary with the cells that failed.
"""
import json
import os
import resource
import sys
import time

import nbformat
from nbclient import NotebookClient

path = sys.argv[1]
skip = {int(x) for x in sys.argv[2:]}
nb = nbformat.read(path, as_version=4)
for i in skip:
    nb.cells[i].source = "pass"

t0 = time.time()
client = NotebookClient(nb, kernel_name="conda_environment", timeout=1500, allow_errors=True,
                        resources={"metadata": {"path": os.path.dirname(os.path.abspath(path))}})
client.execute()
wall = time.time() - t0

ru = resource.getrusage(resource.RUSAGE_CHILDREN)
cg = {}
for f in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
    try:
        cg[f] = int(open(f).read())
    except OSError:
        pass

failed, outputs = [], {}
for i, c in enumerate(nb.cells):
    if c.cell_type != "code":
        continue
    txt = []
    for o in c.get("outputs", []):
        if o.output_type == "error":
            failed.append({"cell": i, "error": f"{o.ename}: {o.evalue}"})
        elif o.output_type == "stream":
            txt.append(o.text)
        elif o.output_type in ("execute_result", "display_data"):
            txt.append(str(o.get("data", {}).get("text/plain", ""))[:500])
    outputs[i] = "".join(txt)[-1500:]

nbformat.write(nb, path.replace(".ipynb", ".executed.ipynb"))
print("=" * 30, "OUTPUTS (tail of each code cell)")
for i, t in outputs.items():
    print(f"--- cell {i}\n{t}")
print("=" * 30)
print(json.dumps({"wall_s": round(wall, 1), "children_cpu_user_s": round(ru.ru_utime, 1),
                  "children_cpu_sys_s": round(ru.ru_stime, 1), "children_maxrss_mb": round(ru.ru_maxrss / 1024, 1),
                  "cgroup_peak_bytes": cg, "failed_cells": failed}))
