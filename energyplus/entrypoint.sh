#!/usr/bin/env bash
set -euo pipefail

#
# entrypoint.sh para EnergyPlus 9.6.0
#
# Uso:
#   docker run --rm \
#     -v /ruta/host/uploads:/workspace/uploads \
#     -v /ruta/host/simulation_outputs:/workspace/simulation_outputs \
#     energyplus:9.6.0 \
#     <archivo.idf> <archivo.epw>
#
# Esto generará los archivos de salida en /workspace/simulation_outputs.
#

# 1) Validar que reciba exactamente 2 argumentos
if [ "$#" -ne 2 ]; then
  echo "Uso: $0 <archivo.idf> <archivo.epw>"
  echo "Ejemplo:"
  echo "  docker run --rm \\"
  echo "    -v /mi/proyecto/backend/uploads:/workspace/uploads \\"
  echo "    -v /mi/proyecto/backend/simulation_outputs:/workspace/simulation_outputs \\"
  echo "    energyplus:9.6.0 mi_modelo.idf weather.epw"
  exit 1
fi

IDF_NAME=$(basename "$1")
EPW_NAME=$(basename "$2")

IDF_PATH="/workspace/uploads/$IDF_NAME"
EPW_PATH="/workspace/uploads/$EPW_NAME"   # vamos a montar ambos archivos en uploads

# 2) Verificar que existan los archivos dentro del contenedor
if [ ! -f "$IDF_PATH" ]; then
  echo "ERROR: No existe '$IDF_PATH' (asegúrate de montar /workspace/uploads)."
  exit 2
fi
if [ ! -f "$EPW_PATH" ]; then
  echo "ERROR: No existe '$EPW_PATH' (asegúrate de montar /workspace/uploads)."
  exit 3
fi

# 3) Crear carpeta de outputs si no existe
mkdir -p /workspace/simulation_outputs

# 4) Ejecutar la simulación EnergyPlus
#    -r   : run and keep output (incluye .err, .csv, etc.)
#    -d   : directorio donde vuelca outputs
#    -w   : ruta al archivo epw
#    <idf>: ruta al archivo idf
energyplus -r -d /workspace/simulation_outputs -w "$EPW_PATH" "$IDF_PATH"

echo "Simulación completada. Archivos en /workspace/simulation_outputs"
