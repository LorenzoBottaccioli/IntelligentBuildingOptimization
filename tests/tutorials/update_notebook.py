"""Brings a student's copy of a tutorial notebook up to a newer version of it, keeping what the student has already run.

    python tests/tutorials/update_notebook.py <new notebook> <student's notebook> <backup folder>

The result is the new notebook (every cell as in the new version) in which each cell that is *identical* (same type, same
source) to a cell of the student's copy keeps that cell's id, outputs and execution count. A cell that is new, or whose
text changed, comes empty. Cells that exist only in the student's copy are not carried over: if the student had changed
a code cell the report lists it, so run it with ``--check`` first to see that nothing of the student's would be lost:

    python tests/tutorials/update_notebook.py --check <new notebook> <student's notebook> <seed version of the student's notebook>

Widget outputs (``application/vnd.jupyter.widget-view+json``) are dropped: their models die with the kernel, and Jupyter
would show "Error displaying widget" in their place. The student's notebook is copied to the backup folder first.
"""
import json
import shutil
import sys
from pathlib import Path

WIDGET = "application/vnd.jupyter.widget-view+json"


def source(cell):
    return "".join(cell["source"])


def clean_outputs(outputs):
    kept, dropped = [], 0
    for o in outputs:
        if WIDGET in o.get("data", {}):
            dropped += 1
            continue
        kept.append(o)
    return kept, dropped


def merge(new, live):
    cells, used, report = [], set(), {"kept": 0, "new": 0, "widgets_dropped": 0}
    position = 0
    for cell in new["cells"]:
        match = None
        for i in list(range(position, len(live["cells"]))) + list(range(0, position)):
            c = live["cells"][i]
            if i not in used and c["cell_type"] == cell["cell_type"] and source(c) == source(cell):
                match = i
                break
        out = json.loads(json.dumps(cell))
        if match is not None:
            used.add(match)
            position = match + 1
            c = live["cells"][match]
            out["id"] = c.get("id", out.get("id"))
            if out["cell_type"] == "code":
                out["outputs"], dropped = clean_outputs(c.get("outputs", []))
                out["execution_count"] = c.get("execution_count")
                report["widgets_dropped"] += dropped
            report["kept"] += 1
        else:
            report["new"] += 1
        cells.append(out)
    merged = dict(new)
    merged["cells"] = cells
    metadata = dict(live.get("metadata", {}))
    metadata.pop("widgets", None)
    merged["metadata"] = metadata or new.get("metadata", {})
    lost = [i for i in range(len(live["cells"])) if i not in used]
    return merged, report, lost


def main(argv):
    check = argv[0] == "--check"
    if check:
        new_p, live_p, base_p = map(Path, argv[1:4])
        base = json.loads(base_p.read_text(encoding="utf8"))
        live = json.loads(live_p.read_text(encoding="utf8"))
        sources = {(c["cell_type"], source(c)) for c in base["cells"]}
        changed = [i for i, c in enumerate(live["cells"]) if (c["cell_type"], source(c)) not in sources]
        print("cells of the student's copy that are not in the seed version:", changed)
        for i in changed:
            print("  ", i, live["cells"][i]["cell_type"], repr(source(live["cells"][i])[:100]))
        return
    new_p, live_p, backup = map(Path, argv[:3])
    new = json.loads(new_p.read_text(encoding="utf8"))
    live = json.loads(live_p.read_text(encoding="utf8"))
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_p, backup / live_p.name)
    merged, report, lost = merge(new, live)
    live_p.write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n", encoding="utf8", newline="\n")
    print(live_p.name, report, "| cells only in the old copy:", len(lost),
          [(i, live["cells"][i]["cell_type"], source(live["cells"][i])[:50]) for i in lost][:6])


if __name__ == "__main__":
    main(sys.argv[1:])
