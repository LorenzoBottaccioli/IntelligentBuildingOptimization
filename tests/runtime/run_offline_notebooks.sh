#!/usr/bin/env bash
# usage: run_offline_notebooks.sh <image-tag> <writable-workspace-copy> <outfile>
# Runs notebooks_offline.py (fake InfluxDB on localhost inside the container) on the three data notebooks. No network.
set -u
export MSYS_NO_PATHCONV=1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
docker run --rm --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --memory-swap=1g --cpus=2 \
  --entrypoint /opt/conda/envs/conda_environment/bin/python \
  -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway -e MPLBACKEND=Agg \
  -v "$R/gateway:/opt/gateway:ro" -v "$R/Field:/home/jovyan/field:ro" \
  -v "$R/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro" \
  -v "$2:/home/jovyan/notebooks" -v "$R/tests/runtime/notebooks_offline.py:/nbo.py:ro" \
  "jupyter:$1" /nbo.py > "$3" 2>&1
echo "exit=$?" >> "$3"
