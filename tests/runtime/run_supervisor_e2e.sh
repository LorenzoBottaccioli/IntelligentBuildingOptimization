#!/usr/bin/env bash
# usage: run_supervisor_e2e.sh <image-tag> <writable-workspace-copy> <outfile> [with-ep-volume]
# supervisor_e2e.py in one throwaway container: --network none, --memory=1g, mounts as the bms_services service of docker-compose.yml
# (gateway, Field ro, fmi_mlc ro, Workspace COPY at /home/jovyan/work). With the 4th argument the live named volume
# energyplus_data is mounted READ-ONLY at the path the compose file uses (a read-only mount of the volume, nothing is written to it).
set -u
export MSYS_NO_PATHCONV=1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
EXTRA=()
if [ "${4:-}" = "with-ep-volume" ]; then
  EXTRA=(-v "smart_builing_educational_platform_dockers-main_energyplus_data:/usr/local/EnergyPlus-9-6-0-4b123cf80f-Linux-Ubuntu20.04-x86_64:ro")
fi
NAME="rt_sup_$$"
docker run --rm --name "$NAME" --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --memory-swap=1g --cpus=2 \
  --entrypoint /opt/conda/envs/conda_environment/bin/python \
  -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
  -v "$R/gateway:/opt/gateway:ro" -v "$R/Field:/home/jovyan/field:ro" \
  -v "$R/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro" \
  -v "$2:/home/jovyan/work" -v "$R/tests/runtime/supervisor_e2e.py:/e2e.py:ro" "${EXTRA[@]}" \
  "jupyter:$1" /e2e.py > "$3" 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do
  docker stats --no-stream --format '{{.MemUsage}} {{.CPUPerc}}' "$NAME" 2>/dev/null >> "$3.mem"
  sleep 3
done
wait $PID
echo "exit=$?" >> "$3"
