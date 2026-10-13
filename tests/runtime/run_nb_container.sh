#!/usr/bin/env bash
# usage: run_nb_container.sh <image-tag> <writable-workspace-copy> <notebook-relative-to-workspace> <TOTAL_TIMESTEPS> <outfile> [skip cells...]
# One throwaway container, --network none (cannot reach the platform's MQTT/InfluxDB), --memory=1g, the same mounts and env as the
# controller service of docker-compose.yml (fmi_mlc, gateway, Field read-only), the Workspace COPY mounted writable.
# --hostname/--add-host: with --network none the container's own name is not in /etc/hosts and the FMU's fmiInitializeSlave
# fails with 'Get host by name failed' (it resolves the host name for its socket to EnergyPlus). On the compose network it resolves.
# <image-tag> is the tag after "jupyter:" (smartbuilding-runtime or smartbuilding). Peak memory seen from outside
# (docker stats every 3 s) goes to <outfile>.mem.
set -u
export MSYS_NO_PATHCONV=1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
IMG="$1"; WS="$2"; NB="$3"; STEPS="$4"; OUT="$5"; shift 5
NAME="rt_nb_$$"
docker run --rm --name "$NAME" --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --memory-swap=1g --cpus=2 \
  --entrypoint /opt/conda/envs/conda_environment/bin/python \
  -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway -e TOTAL_TIMESTEPS="$STEPS" \
  -v "$R/gateway:/opt/gateway:ro" -v "$R/Field:/home/jovyan/field:ro" \
  -v "$R/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro" \
  -v "$WS:/home/jovyan/notebooks" -v "$R/tests/runtime/run_notebook.py:/run_notebook.py:ro" \
  "jupyter:$IMG" /run_notebook.py "/home/jovyan/notebooks/$NB" "$@" > "$OUT" 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do
  docker stats --no-stream --format '{{.MemUsage}} {{.CPUPerc}}' "$NAME" 2>/dev/null >> "$OUT.mem"
  sleep 3
done
wait $PID
echo "exit=$?" >> "$OUT"
