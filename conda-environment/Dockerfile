# Base con EnergyPlus 9.6.0
FROM nrel/energyplus:9.6.0

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:$PATH

# Toolchain per build di matplotlib 3.2.2 (freetype/png) e wheel native
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl ca-certificates bzip2 git \
    build-essential gcc g++ make pkg-config \
    libfreetype6-dev libpng-dev \
 && rm -rf /var/lib/apt/lists/*

# Miniconda (pin alla serie py39 collaudata)
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-py39_4.9.2-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p ${CONDA_DIR} && \
    rm /tmp/miniconda.sh && \
    conda clean -afy

# Canali e Terms of Service:
# 1) installo anaconda-tos da defaults
# 2) accetto i TOS per pkgs/main e pkgs/r
# 3) configuro i canali: conda-forge PRIMO, poi defaults (come volevi)
RUN conda config --set channel_priority strict && \
    conda install -y -n base -c defaults anaconda-tos && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda config --remove-key channels || true && \
    conda config --add channels conda-forge && \
    conda config --add channels defaults

# Copia YAML e crea l’ambiente (senza flag non supportati)
COPY conda_environment.yml /tmp/conda_environment.yml
RUN conda env create -f /tmp/conda_environment.yml && conda clean -afy

# Installa epw (richiesto nei tuoi stack)
SHELL ["/opt/conda/bin/conda", "run", "-n", "conda_environment", "/bin/bash", "-lc"]
RUN python -m pip install --no-cache-dir "git+https://github.com/building-energy/epw.git@master"

# fmi_mlc (fmi_gym, eplus_health) into the env: notebooks and the gateway import it
COPY fmi_mlc /opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc

# Registra kernel Jupyter
RUN python -m ipykernel install --user --name conda_environment --display-name "Python 3.9 (E+96, TF2.7, SB3)"

# Symlink & PATH EnergyPlus (già presente nell’immagine base, ma espongo variabili)
USER root
RUN ln -sf /EnergyPlus-9.6.0-4b123cf80f-Linux-Ubuntu20.04-x86_64 /usr/local/EnergyPlus-9-6-0
ENV ENERGYPLUS_HOME=/usr/local/EnergyPlus-9-6-0
ENV EPLUS_PATH=/usr/local/EnergyPlus-9-6-0/energyplus
ENV PATH=/usr/local/EnergyPlus-9-6-0:$PATH

# The base image is Ubuntu 20.04, whose libstdc++ has no GLIBCXX_3.4.29. Both
# pyfmi (via scipy's _highs_wrapper) and stable_baselines3 need it, so without
# this they fail to import and no simulation can run at all. Conda ships a newer
# libstdc++ inside the env; put it first on the loader path.
ENV LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib:${LD_LIBRARY_PATH}

# Workspace
RUN mkdir -p /home/jovyan/notebooks && chown -R root:root /home/jovyan
WORKDIR /home/jovyan/notebooks

EXPOSE 8888

# Avvio Jupyter classic
ENTRYPOINT ["/bin/bash", "-lc", "\
/opt/conda/envs/conda_environment/bin/jupyter notebook \
 --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
 --NotebookApp.token='' --NotebookApp.password='' \
 --NotebookApp.notebook_dir=/home/jovyan/notebooks \
 --NotebookApp.tornado_settings=\"{'headers':{'Content-Security-Policy':'frame-ancestors *'}}\" \
"]
