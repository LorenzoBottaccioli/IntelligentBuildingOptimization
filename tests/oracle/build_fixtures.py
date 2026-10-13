"""Convert the stored BESOS/Harlow results of the seven surrogate tests to CSV.

Run once, in the venv that wrote the pickles (pandas 1.4.3, BESOS 2.1.3 on
Python 3.9), so the oracle does not depend on pandas pickle compatibility:

    python -I tests/oracle/build_fixtures.py

Only DataFrames are converted. Harlow's own state pickles (not DataFrames, they
need the harlow package) are listed in the manifest as skipped.

The CSVs are bit-exact copies of the pickles ONLY when read back with
`pd.read_csv(path, float_precision="round_trip")`; the default fast parser
changes the last digit (checked: max relative difference 5.7e-15 on 29 tables,
0 differences with round_trip). Always read them with round_trip.

Output: tests/fixtures/oracle/test<N>/<pickle name>.csv and manifest.json. The
IDF and EPW files are referenced by path, not copied: they stay where they are
in 'Surrogate modeling examples/' (they are the oracle inputs and must not drift).
"""
import glob
import json
import os
import pickle

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "Surrogate modeling examples")
OUT = os.path.join(ROOT, "tests", "fixtures", "oracle")
OBJECTIVES = ("Electricity:Facility", "DistrictHeating:Facility", "DistrictCooling:Facility")

manifest = {
    "pandas": pd.__version__,
    "read_csv_hint": "pd.read_csv(path, float_precision='round_trip')  # bit-exact; the default parser is not",
    "tests": {},
}
for n in range(1, 8):
    src = os.path.join(SRC, f"Test {n}")
    out = os.path.join(OUT, f"test{n}")
    os.makedirs(out, exist_ok=True)
    entry = {
        "idf": [os.path.relpath(p, ROOT).replace("\\", "/") for p in glob.glob(os.path.join(src, "*.idf"))],
        "epw": [os.path.relpath(p, ROOT).replace("\\", "/") for p in glob.glob(os.path.join(src, "*.epw"))],
        "tables": {},
        "skipped": [],
    }
    for f in sorted(glob.glob(os.path.join(src, "*.pkl"))):
        name = os.path.basename(f)
        try:
            df = pd.read_pickle(f)
        except Exception as e:  # harlow state pickles need the harlow package
            entry["skipped"].append({"file": name, "reason": f"{type(e).__name__}: {e}"})
            continue
        if not isinstance(df, pd.DataFrame):
            entry["skipped"].append({"file": name, "reason": f"not a DataFrame ({type(df).__name__})"})
            continue
        csv = os.path.join(out, name[:-4] + ".csv")
        df.to_csv(csv, index=False, float_format="%.17g")
        entry["tables"][name] = {
            "csv": os.path.relpath(csv, ROOT).replace("\\", "/"),
            "rows": int(df.shape[0]),
            "columns": [str(c) for c in df.columns],
            "objectives": [str(c) for c in df.columns if c in OBJECTIVES],
            "inputs": [str(c) for c in df.columns if c not in OBJECTIVES],
        }
    manifest["tests"][f"test{n}"] = entry

with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=1)

for k, v in manifest["tests"].items():
    print(k, "tables:", {t: d["rows"] for t, d in v["tables"].items()}, "skipped:", [s["file"] for s in v["skipped"]])
