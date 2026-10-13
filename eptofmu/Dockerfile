############################################
# Dockerfile para EnergyPlusToFMU v3.1.0   #
############################################

# 1) Extraer el IDD desde la imagen oficial de EnergyPlus
FROM nrel/energyplus:9.6.0 AS energyplus_stage

# 2) Base de eptofmu
FROM ubuntu:20.04

# 3) Variables de entorno
ENV EPTOFMU_DIR=/opt/EnergyPlusToFMU
ENV EPTOFMU_VENV=/opt/eptofmu-venv
ENV IDD_PATH=/opt/energyplus/EnergyPlus-9-6-0/PreProcess/Energy+.idd

# 4) Copiar el IDD desde la etapa anterior
RUN mkdir -p "$(dirname "${IDD_PATH}")"
COPY --from=energyplus_stage /EnergyPlus-9.6.0-*/Energy+.idd "${IDD_PATH}"

# 5) Instalamos dependencias básicas + build-essential (g++, make, etc.)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      python3 python3-venv python3-pip git wget unzip && \
    rm -rf /var/lib/apt/lists/*

# 6) Creamos un virtualenv e instalamos paquetes Python
RUN python3 -m venv "${EPTOFMU_VENV}" && \
    "${EPTOFMU_VENV}/bin/pip" install --upgrade pip && \
    "${EPTOFMU_VENV}/bin/pip" install \
      fmpy \
      numpy \
      pandas \
      lxml

# 7) Clonamos el repositorio oficial v3.1.0
RUN git clone --branch v3.1.0 https://github.com/lbl-srg/EnergyPlusToFMU.git "${EPTOFMU_DIR}"

# 8) Copiamos entrypoint.sh
COPY entrypoint.sh "${EPTOFMU_DIR}/entrypoint.sh"

# 9) Damos permisos de ejecución
RUN chmod +x "${EPTOFMU_DIR}/entrypoint.sh" && \
    chmod +x "${EPTOFMU_DIR}/Scripts/EnergyPlusToFMU.py" && \
    chmod +x "${EPTOFMU_DIR}/Scripts/makeFMULib.py"

# 10) El contenedor arrancará con `tail -f /dev/null` en docker-compose
WORKDIR "${EPTOFMU_DIR}"
