"""Rebuilds backend/seed_sessions/bdopt-demo through the platform's own routes, on a throwaway stack.

    python tests/tutorials/make_tutorials.py          # the notebooks first
    python tests/tutorials/build_demo_seed.py         # needs Docker; takes about 4 minutes

What it does, in order (nothing touches the live platform: its own containers, ports and folders):

1. builds `backend:demo-build` from backend/ and starts `demo-energyplus` (EnergyPlus 9.6 sidecar) and `demo-backend`
   (port 5001), with the working directories in a temporary folder; the backend finds its sidecar through
   ENERGYPLUS_CONTAINER, and no InfluxDB/Grafana/MQTT exist for it (their steps only warn);
2. uploads tutorials/test.idf and the Turin EPW (probe simulation, tables, notebook injection), defines the design problem
   through POST /surrogate_modeling/problem, copies tutorials/ into surrogate_notebooks/tutorials;
3. saves the session (POST /sessions/save) and copies it to backend/seed_sessions/bdopt-demo with the id, name and
   description of a shipped session;
4. stops and removes the two containers it started.

An existing seed is moved aside to the temporary folder, never deleted. Rebuild the backend image afterwards to ship it.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUTORIALS = ROOT / "tutorials"
SEED = ROOT / "backend" / "seed_sessions" / "bdopt-demo"
PORT = 5001
NAMES = ("demo-backend", "demo-energyplus")
WORKDIRS = ["uploads", "originals", "simulation_outputs", "user_files", "sessions", "simulation_notebooks",
            "surrogate_notebooks", "workspace", "field", "flask_session", "openhab_conf"]

META = {
    "id": "bdopt-demo",
    "name": "Demo - bdopt tutorial",
    "description": "A small house (test.idf, Turin weather) with its design problem and three tutorial notebooks: "
                   "bdopt overview, surrogate modelling and optimization. Modelling only: no IoT.",
}

METERS = ("Electricity:Facility", "DistrictHeating:Facility", "DistrictCooling:Facility")


def variable(name, cls, field, objects, lo, hi, unit, label):
    # `objects` names the objects written; an empty list means every object of the class
    return {"name": name, "className": cls, "field": field, "objects": objects, "label": label, "unit": unit,
            "type": "range", "min": lo, "max": hi}


PROBLEM = {
    "variables": [
        variable("Insulation Thickness", "Material", "Thickness", ["XPS Extruded Polystyrene  - CO2 Blowing_0041"],
                 0.01, 0.45, "m", "Thickness of the XPS insulation layer"),
        variable("Glazing conductivity", "WindowMaterial:Glazing", "Conductivity", ["3"], 0.1, 1.0, "W/m-K",
                 "Conductivity of the glazing"),
        variable("Glazing solar transmittance", "WindowMaterial:Glazing", "Solar_Transmittance_at_Normal_Incidence",
                 ["3"], 0.01, 0.8, "", "Solar transmittance of the glazing"),
        variable("Lights Watts/Area", "Lights", "Watts_per_Zone_Floor_Area", [], 8, 12, "W/m2", "Lighting power density"),
    ],
    "objectives": [{"name": m, "direction": "minimize"} for m in METERS],
    "notes": "Demo problem of the bdopt tutorials: the insulation, two properties of the glazing and the lighting power "
             "of the small house test.idf, against the annual electricity, heating and cooling of the building. "
             "The tutorials also vary the window-to-wall ratio, which this panel does not offer.",
}


def run(*cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def call(method, path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://localhost:{PORT}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def main():
    if not (TUTORIALS / "test.idf").exists():
        sys.exit("tutorials/ is empty: run tests/tutorials/make_tutorials.py first")
    busy = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    if any(n in busy for n in NAMES):
        sys.exit(f"a container named {' or '.join(NAMES)} exists already: stop it first (it is not touched here)")
    work = Path(tempfile.mkdtemp(prefix="demo-seed-"))
    for d in WORKDIRS:
        (work / d).mkdir()
    started = []
    try:
        run("docker", "build", "-q", "-t", "backend:demo-build", str(ROOT / "backend"))
        run("docker", "run", "-d", "--name", "demo-energyplus", "--memory=2g",
            "-v", f"{work / 'uploads'}:/workspace/uploads", "-v", f"{work / 'simulation_outputs'}:/workspace/simulation_outputs",
            "nrel/energyplus:9.6.0", "tail", "-f", "/dev/null", stdout=subprocess.DEVNULL)
        started.append("demo-energyplus")
        mounts = [x for d in WORKDIRS for x in ("-v", f"{work / d}:/app/{d}")]
        run("docker", "run", "-d", "--name", "demo-backend", "--memory=2g", "-p", f"{PORT}:5000",
            "-v", "/var/run/docker.sock:/var/run/docker.sock", "-e", "ENERGYPLUS_CONTAINER=demo-energyplus",
            "-e", "SURROGATE_ENGINE=bdopt", "-e", "IDD_PATH=/app/EnergyPlus-9-6-0/Energy+.idd", *mounts,
            "backend:demo-build", stdout=subprocess.DEVNULL, env=None)
        started.append("demo-backend")
        for _ in range(60):
            try:
                call("GET", "/sessions/", timeout=5)
                break
            except Exception:
                time.sleep(2)
        # the workspace skeleton (templates); its last step needs InfluxDB, which this stack has not: expected error
        call("DELETE", "/model_editor/reset_session", timeout=120)
        out = subprocess.run(
            ["curl", "-s", "-m", "900", "-F", f"idf_file=@{TUTORIALS / 'test.idf'}",
             "-F", f"epw_file=@{TUTORIALS / 'ITA_Torino.160590_IWEC.epw'}", f"http://localhost:{PORT}/model_editor/upload_files"],
            capture_output=True, text=True).stdout
        if "Successfully" not in out:
            sys.exit(f"upload failed: {out[:300]}")
        status, body = call("POST", "/surrogate_modeling/problem", PROBLEM)
        if status != 200:
            sys.exit(f"problem refused: {body}")
        shutil.copytree(TUTORIALS, work / "surrogate_notebooks" / "tutorials", dirs_exist_ok=True)
        status, body = call("POST", "/sessions/save", {"name": META["name"]})
        if status != 200:
            sys.exit(f"save failed: {body}")
        sid = body["current"]
        saved = work / "sessions" / sid
        if SEED.exists():
            aside = work / "previous-seed"
            shutil.move(str(SEED), str(aside))
            print("previous seed moved to", aside)
        SEED.mkdir(parents=True)
        shutil.copytree(saved / "state", SEED / "state")
        meta = json.loads((saved / "meta.json").read_text(encoding="utf8"))
        meta.update(META)
        (SEED / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf8")
        print("seed written to", SEED)
    finally:
        for name in started:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        print("temporary folder kept at", work)


if __name__ == "__main__":
    main()
