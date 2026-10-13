#!/usr/bin/env bash
# usage: jupyter_startup.sh <image-tag> <outfile>
# Starts the image's OWN entrypoint (the Jupyter classic server, exactly the command of the Dockerfile) in a throwaway container
# with no network, waits for it, asks it (from inside the container) for the kernelspecs, the CSP header and the tree, and checks
# that a kernel of the notebooks (conda_environment) starts through the REST API. The container ends by itself (timeout 60).
set -u
export MSYS_NO_PATHCONV=1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
timeout 120 docker run --rm --network none --memory=1g --memory-swap=1g --cpus=2 \
  --entrypoint /bin/bash \
  -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
  -v "$R/gateway:/opt/gateway:ro" -v "$R/Field:/home/jovyan/field:ro" \
  -v "$R/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro" \
  -v "$R/tests/runtime/jupyter_probe.py:/probe.py:ro" \
  "jupyter:$1" -c '
( timeout 60 /opt/conda/envs/conda_environment/bin/jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
   --NotebookApp.token= --NotebookApp.password= --NotebookApp.notebook_dir=/home/jovyan/notebooks \
   --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors *\"}}" > /tmp/jupyter.log 2>&1 & )
for i in $(seq 1 40); do /opt/conda/envs/conda_environment/bin/python -c "import urllib.request;urllib.request.urlopen(\"http://127.0.0.1:8888/api\")" 2>/dev/null && break; sleep 1; done
/opt/conda/envs/conda_environment/bin/python /probe.py
echo "--- jupyter.log tail"; tail -5 /tmp/jupyter.log
' > "$2" 2>&1
echo "exit=$?" >> "$2"
