"""Regenerate tests/runtime/compose_runtime.diff: the proposed change of docker-compose.yml that moves bms_services and
controller to image A (jupyter:smartbuilding-runtime). docker-compose.yml itself is NOT edited.

HISTORICAL (10 Oct 2026): docker-compose.yml has since dropped jupyter_env_builder and the x-jupyter anchor, so the
text this script replaces no longer exists and it would fail; compose_runtime.diff is the record of the 9 Oct proposal.

    python tests/runtime/make_compose_diff.py

The file uses CRLF line endings; the edit and the diff keep them, so the diff applies with `git apply` / `patch -p1` as it is.
jupyter_surrogate keeps the anchor image (jupyter:smartbuilding): without docker-compose.bdopt.yml it is the BESOS fallback,
and the runtime image has no BESOS.
"""
import difflib
import os

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
src = open(os.path.join(root, "docker-compose.yml"), newline="", encoding="utf-8").read()
new = src
NL = "\r\n"


def rep(old, repl, count=1):
    global new
    old, repl = old.replace("\n", NL), repl.replace("\n", NL)
    assert new.count(old) == count, (old, new.count(old))
    new = new.replace(old, repl)


# 1. the builder of image A, next to the one of image B (build-only: the profile keeps it out of `up`)
rep("""  ### --------------------------
  ### IMAGE B: bdopt (surrogate)""", """  ### --------------------------
  ### IMAGE A: runtime (bms_services, controller)
  ### --------------------------
  # pyfmi + EnergyPlus 9.6 + stable-baselines3 on CPU torch; no BESOS, Harlow, TensorFlow. Build-only (profile):
  #   docker compose build runtime_image_builder
  runtime_image_builder:
    profiles: ["build"]
    build:
      context: ./conda-environment
      dockerfile: Dockerfile.runtime
    image: jupyter:smartbuilding-runtime

  ### --------------------------
  ### IMAGE B: bdopt (surrogate)""")

# 2. bms_services and controller: image A. A key written in the service wins over the one merged from *jupyter.
rep("""    container_name: bms_services
""", """    container_name: bms_services
    image: jupyter:smartbuilding-runtime
""")
rep("""    container_name: controller
""", """    container_name: controller
    image: jupyter:smartbuilding-runtime
""")

# 3. the controller no longer waits for the builder of the old image (it would start a Jupyter of the old image next to it)
rep("""      - ./conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro
      - ./gateway:/opt/gateway:ro
      - ./Workspace:/home/jovyan/notebooks
      - ./Field:/home/jovyan/field:ro
      - ./backend/uploads:/home/jovyan/uploads:ro
      - energyplus_data:/usr/local/EnergyPlus-9-6-0-4b123cf80f-Linux-Ubuntu20.04-x86_64:ro
    depends_on:
      - jupyter_env_builder
      - mosquitto
""", """      - ./conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro
      - ./gateway:/opt/gateway:ro
      - ./Workspace:/home/jovyan/notebooks
      - ./Field:/home/jovyan/field:ro
      - ./backend/uploads:/home/jovyan/uploads:ro
      - energyplus_data:/usr/local/EnergyPlus-9-6-0-4b123cf80f-Linux-Ubuntu20.04-x86_64:ro
    depends_on:
      - mosquitto
""")

# 4. comment of the anchor: it is now the image of the BESOS fallback only
rep("""# Shared by every Jupyter service: they run the same image and differ only in
# which notebook directory they mount.""", """# Shared by the Jupyter services. The image here is the legacy one (jupyter_surrogate in the BESOS fallback);
# bms_services and controller set their own image (jupyter:smartbuilding-runtime, image A).""")

a = src.splitlines(keepends=True)
b = new.splitlines(keepends=True)
diff = "".join(difflib.unified_diff(a, b, "a/docker-compose.yml", "b/docker-compose.yml", n=3))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compose_runtime.diff"), "w", newline="", encoding="utf-8").write(diff)
import sys
if len(sys.argv) > 1:       # also write the patched compose file there (to check it, never over docker-compose.yml)
    open(sys.argv[1], "w", newline="", encoding="utf-8").write(new)
print(diff.replace("\r", ""))
