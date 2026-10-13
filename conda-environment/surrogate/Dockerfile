# Image B: the students' surrogate-modelling / optimisation Jupyter, on bdopt.
#
# It replaces the surrogate part of the 11.5 GB jupyter:smartbuilding image (BESOS, Harlow,
# TensorFlow, CUDA torch). It contains only EnergyPlus 9.6, Python 3.11, the scientific stack bdopt
# needs and Jupyter. The FMU / RL runtime (pyfmi, fmi_mlc, stable-baselines3) stays in image A.
#
#   docker build -t jupyter:smartbuilding-surrogate conda-environment/surrogate
#   docker build --target test -t bdopt-test conda-environment/surrogate && docker run --rm bdopt-test
#
# bdopt comes from the public repository, pinned to a commit (v0.2.0 = e895ae5; no token, no git needed in the build).
# Build args:  BDOPT_REF  commit or tag;   EXTRAS  bdopt extras (add "torch" for TorchMLP).

# EnergyPlus 9.6.0: the same build the energyplus sidecar runs (nrel/energyplus:9.6.0).
FROM nrel/energyplus:9.6.0 AS eplus

FROM python:3.11-slim AS runtime

ARG BDOPT_REF=e895ae5092bc0ab800f584f50b438d3a4ff9bbaf
ARG EXTRAS=viz,yaml
ARG NOTEBOOK_VERSION=7.4.5

# One BLAS thread per process. bdopt runs EnergyPlus in parallel and the students' containers share a machine:
# with the default (one thread per core) a Gaussian-process fit was measured 40-100x slower on a busy host
# (160 s vs 4 s; 498 s vs 21 s). Students can raise it in a notebook before importing numpy.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# EnergyPlus is a binary built for Ubuntu 20.04: besides its own libpython it needs libgomp, libX11 and
# libexpat from the system. Debian 12 (this base) has a newer glibc, so it runs unchanged.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libx11-6 libgomp1 libexpat1 \
 && rm -rf /var/lib/apt/lists/*

# Same path the other containers mount the energyplus sidecar volume on, so the mount (if present)
# and the copy are interchangeable.
ENV EPLUS_HOME=/usr/local/EnergyPlus-9-6-0-4b123cf80f-Linux-Ubuntu20.04-x86_64
COPY --from=eplus /EnergyPlus-9.6.0-4b123cf80f-Linux-Ubuntu20.04-x86_64 ${EPLUS_HOME}
ENV EPLUS_PATH=${EPLUS_HOME}/energyplus \
    PATH=${EPLUS_HOME}:${PATH}

# constraints.txt = `pip freeze` of the image that passed bdopt's tests and the Test 1 check: the build
# gives the same environment next year. To upgrade, regenerate it and re-test:
#   docker run --rm --entrypoint pip <image> freeze --exclude bdopt > constraints.txt
COPY constraints.txt /tmp/constraints.txt
# plotly: the interactive (brushable) parallel-coordinates plot of the tutorials, as in the original course notebooks.
RUN pip install -c /tmp/constraints.txt "notebook==${NOTEBOOK_VERSION}" ipykernel ipywidgets tqdm plotly \
 && pip install -c /tmp/constraints.txt \
      "bdopt[${EXTRAS}] @ https://github.com/LorenzoBottaccioli/bdopt/archive/${BDOPT_REF}.zip" \
 && rm /tmp/constraints.txt

# Same working directory, port and server settings as the current image: the platform embeds
# this server in an iframe, which needs the empty token and the CSP header.
RUN mkdir -p /home/jovyan/notebooks
WORKDIR /home/jovyan/notebooks
EXPOSE 8888
ENTRYPOINT ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
            "--NotebookApp.token=", "--NotebookApp.password=", \
            "--NotebookApp.notebook_dir=/home/jovyan/notebooks", \
            "--NotebookApp.tornado_settings={'headers':{'Content-Security-Policy':'frame-ancestors *'}}"]


# bdopt's own test-suite against this image (EnergyPlus included). Not part of the runtime image.
FROM runtime AS test
ARG BDOPT_REF=e895ae5092bc0ab800f584f50b438d3a4ff9bbaf
ADD https://github.com/LorenzoBottaccioli/bdopt/archive/${BDOPT_REF}.tar.gz /tmp/bdopt-src.tar.gz
RUN mkdir /src && tar -xzf /tmp/bdopt-src.tar.gz -C /src --strip-components=1 && rm /tmp/bdopt-src.tar.gz \
 && pip install pytest nbformat \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu
WORKDIR /src
ENTRYPOINT ["python", "-m", "pytest", "-q", "-x"]
CMD ["-m", "not eplus"]


# Last stage = default target: a plain `docker build` gives the runtime image, not the test one.
FROM runtime AS final
