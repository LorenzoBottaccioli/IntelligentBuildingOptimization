"""Does EnergyPlus accept the models edited by ``window_to_wall.set_window_to_wall``? (not for students)

Short simulations, NOT a year: the run period of each model is cut to 3 days (1-3 January) and EnergyPlus is called
directly, one run at a time. For each model the unedited model is run first; then the model edited at some ratios.
The script prints the number of Severe and Fatal errors and Warnings in ``eplusout.err`` and the Warning lines that
mention a subsurface, window or overlap. It does not read results: it only tells whether EnergyPlus takes the geometry.

Usage, in the folder of ``window_to_wall.py`` and the models, with EnergyPlus on the PATH::

    python eplus_wwr_smoke.py ITA_Torino.160590_IWEC.epw test.idf:0.1,0.5,0.8 example_idf.idf:0.1,0.5,0.9
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from bdopt import load_idf

import window_to_wall as w2w


def three_days(idf):
    for run in idf.by_class("RunPeriod"):
        run.set(1, 1)   # Begin Month
        run.set(2, 1)   # Begin Day of Month
        run.set(4, 1)   # End Month
        run.set(5, 3)   # End Day of Month
    return idf


def run(idf, epw, work):
    work.mkdir(parents=True, exist_ok=True)
    model = work / "in.idf"
    idf.save(model)
    p = subprocess.run(["energyplus", "-w", str(Path(epw).resolve()), "-d", str(work), str(model)],
                       capture_output=True, text=True, timeout=900)
    err = (work / "eplusout.err").read_text(errors="replace") if (work / "eplusout.err").exists() else ""
    found = re.findall(r"(\d+) Warning;\s+(\d+) Severe Errors", err)   # several summaries: the last one counts the whole run
    warn, severe = (int(found[-1][0]), int(found[-1][1])) if found else (-1, -1)
    lines = [l.strip() for l in err.splitlines() if re.search(r"subsurface|sub-surface|window|overlap|outside", l, re.I)
             and l.strip().startswith(("** Warning", "** Severe", "**  ~~~**"))]
    dxf = sorted(f.name for f in work.glob("*.dxf"))
    return p.returncode, warn, severe, "EnergyPlus Completed Successfully" in err, lines, dxf


def main(epw, specs):
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for spec in specs:
            path, ratios = spec.split(":")
            base = three_days(load_idf(path))
            cases = [("unedited", base)]
            for r in ratios.split(","):
                m = base.copy()
                w2w.set_window_to_wall(m, float(r))
                cases.append((f"ratio {r}", m))
            for label, idf in cases:
                rc, warn, severe, done, lines, dxf = run(idf, epw, Path(tmp) / (Path(path).stem + "_" + label.replace(" ", "_")))
                print(f"{path:18s} {label:11s} exit={rc} completed={done} warnings={warn} severe={severe} dxf={dxf}")
                for l in lines[:4]:
                    print("      ", l[:160])
                if not done or severe != 0 and label != "unedited":
                    bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
