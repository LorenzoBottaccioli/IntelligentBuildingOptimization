FROM python:3.9-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

FROM nrel/energyplus:9.6.0 AS eplus

FROM python:3.9-slim
WORKDIR /app

# 1) Instala Docker CLI
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

# 2) Copia dependencias y código
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /app /app

# 3) Copia el IDD
COPY --from=eplus /EnergyPlus-9.6.0-4b123cf80f-Linux-Ubuntu20.04-x86_64/Energy+.idd /app/EnergyPlus-9-6-0/Energy+.idd
ENV IDD_PATH="/app/EnergyPlus-9-6-0/Energy+.idd"

EXPOSE 5000
CMD ["python", "main.py"]