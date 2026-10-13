#!/usr/bin/env bash
set -euo pipefail

# entrypoint.sh (ubicado en /opt/EnergyPlusToFMU/entrypoint.sh dentro del contenedor)

# 1) Validar que haya dos argumentos (idf + epw)
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <archivo.idf> <archivo.epw>"
    echo ""
    echo "Ejemplo:"
    echo "  docker run --rm \\"
    echo "    -v /ruta/local/backend/uploads:/workspace/uploads \\"
    echo "    -v /ruta/local/backend/user_files:/workspace/user_files \\"
    echo "    eptofmu:3.1.0 <modelo.idf> <weather.epw>"
    exit 1
fi

IDF_BASENAME="$1"
EPW_BASENAME="$2"

IDF_PATH="/workspace/uploads/${IDF_BASENAME}"
EPW_PATH="/workspace/user_files/${EPW_BASENAME}"

# 2) Validar que existan los archivos en sus ubicaciones de volumen
if [ ! -f "${IDF_PATH}" ]; then
    echo "ERROR: No se encontró el archivo IDF en ${IDF_PATH}"
    exit 1
fi
if [ ! -f "${EPW_PATH}" ]; then
    echo "ERROR: No se encontró el archivo EPW en ${EPW_PATH}"
    exit 1
fi

# 3) Verificar que IDD_PATH esté definido y exista
if [ -z "${IDD_PATH:-}" ]; then
    echo "ERROR: La variable IDD_PATH no está definida"
    exit 1
fi
if [ ! -f "${IDD_PATH}" ]; then
    echo "ERROR: No se encontró el IDD en '${IDD_PATH}'. Asegúrate de haber montado el contenedor energyplus."
    exit 1
fi

# 4) Cambiar al directorio donde queremos que aparezca el FMU
cd /workspace/user_files

# 5) Ejecutar conversión a FMU
python3 "/opt/EnergyPlusToFMU/Scripts/EnergyPlusToFMU.py" \
    -i "${IDD_PATH}" \
    -w "${EPW_PATH}" \
    "${IDF_PATH}"

# Si llegamos aquí, la conversión fue exitosa. El FMU se generará como /workspace/user_files/<idf_basename>.fmu
exit 0

