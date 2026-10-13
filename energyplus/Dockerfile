###################################
# Contenedor para EnergyPlus 9.6.0
###################################
FROM ubuntu:20.04

# Evitar prompts durante apt-get
ENV DEBIAN_FRONTEND=noninteractive

# 1) Actualizar e instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    libxerces-c3.2 \
    libicu66 \
    libz-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 2) Variables de entorno para EnergyPlus
ENV EP_VERSION=9-6-0
ENV EP_DIR=/opt/energyplus
ENV PATH="${EP_DIR}/EnergyPlus-${EP_VERSION}/bin:$PATH"

# 3) Descargar y extraer EnergyPlus 9.6.0 (Linux x86_64)
RUN mkdir -p /tmp/energyplus-download && \
    cd /tmp/energyplus-download && \
    wget -q https://github.com/NREL/EnergyPlus/releases/download/v${EP_VERSION}/EnergyPlus-${EP_VERSION}-Linux-x86_64.tar.gz -O energyplus.tar.gz && \
    mkdir -p ${EP_DIR} && \
    tar -xzf energyplus.tar.gz -C ${EP_DIR} && \
    rm -rf /tmp/energyplus-download

# 4) Copiar el script entrypoint para lanzar simulaciones
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# 5) Definir punto de entrada
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
