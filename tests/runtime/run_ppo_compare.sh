#!/usr/bin/env bash
# usage: run_ppo_compare.sh <image-tag> <outfile> [steps] [threads]
# ppo_compare.py in one throwaway container (--network none, --memory=1g, --cpus=2). Peak memory from outside in <outfile>.mem.
set -u
export MSYS_NO_PATHCONV=1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
NAME="rt_ppo_$$"
docker run --rm --name "$NAME" --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --memory-swap=1g --cpus=2 \
  --entrypoint /opt/conda/envs/conda_environment/bin/python \
  -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
  -v "$R/Field:/home/jovyan/field:ro" \
  -v "$R/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro" \
  -v "$R/Workspace/ai/AgentTraining.ipynb:/nb.ipynb:ro" -v "$R/tests/runtime/ppo_compare.py:/ppo.py:ro" \
  "jupyter:$1" /ppo.py "${3:-2000}" "${4:-0}" > "$2" 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do
  docker stats --no-stream --format '{{.MemUsage}} {{.CPUPerc}}' "$NAME" 2>/dev/null >> "$2.mem"
  sleep 3
done
wait $PID
echo "exit=$?" >> "$2"
