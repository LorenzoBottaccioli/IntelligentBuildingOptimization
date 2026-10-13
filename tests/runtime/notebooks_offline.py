"""Run the Workspace data notebooks (iot/data_access, iot/energy_signature, ai/forecasting) with no network.

They talk to InfluxDB with urllib only, so a fake InfluxDB 1.x HTTP server (this script, 127.0.0.1:8086) stands in for it:
SHOW MEASUREMENTS / TAG KEYS / FIELD KEYS / TAG VALUES / SERIES and SELECT (a synthetic series of 14 days, hourly, two points).
The TODO cells of the templates raise NotImplementedError ON PURPOSE (the student writes them): those are reported as `expected_todo`;
every other exception is `unexpected`. Extra cells appended at the end (marked "INJECTED") exercise what a student's solution
imports: pandas pivot/resample, sklearn Ridge + GradientBoostingRegressor + metrics, matplotlib (Agg), numpy polyfit.

    docker run --rm --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --entrypoint /opt/conda/envs/conda_environment/bin/python \
      -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e MPLBACKEND=Agg \
      -v <COPY of Workspace>:/home/jovyan/notebooks -v <repo>/tests/runtime/notebooks_offline.py:/nbo.py:ro  <image> /nbo.py

Prints a JSON summary. The notebooks are executed IN PLACE (as *.executed.ipynb copies, the originals are not rewritten).
"""
import json
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import nbformat
import numpy as np
from nbclient import NotebookClient

os.environ["INFLUX_URL"] = "http://127.0.0.1:8086"
os.environ["INFLUX_USERNAME"] = "admin"
os.environ["INFLUX_PASSWORD"] = "x"

T0 = 1735689600000   # 2025-01-01T00:00Z in ms
POINTS = ["Electricity_Facility", "Zone_Mean_Air_Temperature_KITCHEN"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0]
        u = q.upper()
        if u.startswith("SHOW MEASUREMENTS"):
            s = [{"name": "measurements", "columns": ["name"], "values": [["points"]]}]
        elif u.startswith("SHOW TAG KEYS"):
            s = [{"name": "points", "columns": ["tagKey"], "values": [["point"], ["run"]]}]
        elif u.startswith("SHOW FIELD KEYS"):
            s = [{"name": "points", "columns": ["fieldKey", "fieldType"], "values": [["value", "float"]]}]
        elif u.startswith("SHOW"):
            s = [{"name": "points", "columns": ["key", "value"], "values": [["point", p] for p in POINTS]}]
        else:
            vals = []
            for h in range(14 * 24):
                vals.append([T0 + h * 3600000, 20 + 5 * np.sin(h / 24 * 2 * np.pi) + (h // 24) * 0.1, "Zone_Mean_Air_Temperature_KITCHEN"])
                vals.append([T0 + h * 3600000, 1e6 * (1 + 0.5 * np.sin(h / 24 * 2 * np.pi)), "Electricity_Facility"])
            s = [{"name": "points", "columns": ["time", "value", "point"], "values": vals}]
        body = json.dumps({"results": [{"statement_id": 0, "series": s}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


threading.Thread(target=HTTPServer(("127.0.0.1", 8086), H).serve_forever, daemon=True).start()

INJECT = {
    "ai/forecasting.ipynb": '''# INJECTED: what a solution imports and does
raw = query("base_building", "SELECT value FROM points GROUP BY point")
wide = raw.pivot_table(index=raw.index, columns="point", values="value", aggfunc="last").resample("1h").last().ffill().dropna()
TARGET = "Electricity_Facility"
X = pd.DataFrame(index=wide.index)
for lag in range(0, 4): X[f"lag{lag}"] = wide[TARGET].shift(lag)
X["hour_sin"] = np.sin(2*np.pi*X.index.hour/24); X["hour_cos"] = np.cos(2*np.pi*X.index.hour/24)
y = wide[TARGET].shift(-1)
d = pd.concat([X, y.rename("y")], axis=1).dropna()
days = d.index.normalize(); tr = days < days.unique()[-3]
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
res = {}
for name, m in (("ridge", Ridge()), ("gbr", GradientBoostingRegressor(n_estimators=50, random_state=0))):
    m.fit(d[tr].drop(columns="y"), d[tr]["y"]); p = m.predict(d[~tr].drop(columns="y"))
    res[name] = (round(mean_absolute_error(d[~tr]["y"], p), 3), round(mean_squared_error(d[~tr]["y"], p) ** 0.5, 3))
plt.figure(); plt.plot(d[~tr]["y"].values); plt.savefig("/tmp/forecast.png"); print("INJECTED OK", res, "pandas", pd.__version__)''',
    "iot/energy_signature.ipynb": '''# INJECTED
T = np.linspace(-5, 20, 30); E = 100 - 3.0 * T + np.random.default_rng(0).normal(0, 2, 30)
b, a = np.polyfit(T, E, 1); r2 = 1 - ((E - (a + b*T))**2).sum() / ((E - E.mean())**2).sum()
ax = plot_signature(T, E, a, b); ax.figure.savefig("/tmp/sig.png"); print("INJECTED OK a=%.1f b=%.2f r2=%.3f" % (a, b, r2))''',
    "iot/data_access.ipynb": '''# INJECTED
df = query(DB_BASE, "SELECT value FROM points GROUP BY point")
daily = df[df["point"] == "Electricity_Facility"].set_index("time")["value"].resample("1D").sum() / 3.6e6
print("INJECTED OK", daily.shape, round(float(daily.iloc[0]), 2), "kWh on day 1")''',
}

summary = {}
for rel, inject in INJECT.items():
    path = "/home/jovyan/notebooks/" + rel
    nb = nbformat.read(path, as_version=4)
    n_orig = len(nb.cells)
    nb.cells.append(nbformat.v4.new_code_cell(inject))
    NotebookClient(nb, kernel_name="conda_environment", timeout=300, allow_errors=True,
                   resources={"metadata": {"path": os.path.dirname(path)}}).execute()
    expected, unexpected, ran = [], [], 0
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        ran += 1
        for o in c.get("outputs", []):
            if o.output_type == "error":
                rec = {"cell": i, "injected": i >= n_orig, "error": f"{o.ename}: {o.evalue}"[:200]}
                (expected if o.ename == "NotImplementedError" and i < n_orig else unexpected).append(rec)
    last = "".join(o.get("text", "") for o in nb.cells[-1].get("outputs", []) if o.output_type == "stream").strip()
    first_out = "".join(o.get("text", "") for c in nb.cells for o in c.get("outputs", []) if o.output_type == "stream")[:300]
    summary[rel] = {"code_cells_run": ran, "expected_todo": len(expected), "unexpected": unexpected,
                    "injected_cell_output": last[-300:], "first_stream_output": first_out}
    nbformat.write(nb, path.replace(".ipynb", ".executed.ipynb"))
print(json.dumps(summary, indent=1))
