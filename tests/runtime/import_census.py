"""Re-derive the import census for the controller / bms_services image and test every import on the image it runs in.

    docker run --rm --network none --memory=1g --entrypoint /opt/conda/envs/conda_environment/bin/python \
        -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib \
        -v <repo>:/repo:ro -v <repo>/tests/runtime/import_census.py:/census.py:ro  <image>  /census.py [root ...]

Walks the given roots (default: the files the controller and bms_services run), parses every .py and .ipynb with ast
(IPython magics and ! lines are blanked, they are not Python), collects every imported top-level module (absolute imports
and the dotted name), drops the standard library and local modules (files next to the importer), then tries
importlib.import_module on each dotted name and prints one line per module: ok / FAIL, version, the files that import it.
Prints a JSON document on stdout.
"""
import ast
import importlib
import importlib.util
import json
import os
import sys
import traceback

ROOT = "/repo"
DEFAULT = ["Workspace/ai", "Workspace/iot", "Workspace/devices", "gateway", "conda-environment/fmi_mlc"]
EXTRA = ["reference", "Simulation examples"]   # not run by the two containers; listed apart


def stdlib(name):
    if hasattr(sys, "stdlib_module_names"):
        return name in sys.stdlib_module_names
    if name in sys.builtin_module_names:
        return True
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        return False
    if spec is None or spec.origin in (None, "built-in", "frozen"):
        return spec is not None
    return "site-packages" not in spec.origin and "dist-packages" not in spec.origin


def sources(path):
    if path.endswith(".py"):
        yield path, open(path, encoding="utf-8", errors="replace").read()
    else:
        nb = json.load(open(path, encoding="utf-8"))
        for i, c in enumerate(nb.get("cells", [])):
            if c.get("cell_type") == "code":
                src = c["source"] if isinstance(c["source"], str) else "".join(c["source"])
                lines = [("" if l.lstrip().startswith(("%", "!")) else l) for l in src.splitlines()]
                yield f"{path}#cell{i}", "\n".join(lines)


def scan(roots):
    found = {}   # dotted -> set(files)
    errors = []
    for r in roots:
        base = os.path.join(ROOT, r)
        walker = [(os.path.dirname(base), None, [os.path.basename(base)])] if os.path.isfile(base) else os.walk(base)
        for d, dirs, files in walker:
            if dirs is not None:
                dirs[:] = [x for x in dirs if x not in (".ipynb_checkpoints", "__pycache__")]
            local = {os.path.splitext(f)[0] for f in os.listdir(d)} | set(os.listdir(d))
            for f in files:
                if not f.endswith((".py", ".ipynb")):
                    continue
                p = os.path.join(d, f)
                try:
                    for label, src in sources(p):
                        try:
                            tree = ast.parse(src)
                        except SyntaxError as e:
                            errors.append(f"{label}: SyntaxError {e}")
                            continue
                        for n in ast.walk(tree):
                            names = []
                            if isinstance(n, ast.Import):
                                names = [a.name for a in n.names]
                            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                                names = [n.module] + [n.module + "." + a.name for a in n.names if a.name != "*"]
                            for nm in names:
                                top = nm.split(".")[0]
                                if stdlib(top) or top in local:
                                    continue
                                found.setdefault(nm, set()).add(os.path.relpath(p, ROOT).replace(os.sep, "/"))
                except Exception as e:
                    errors.append(f"{p}: {e}")
    return found, errors


def probe(found):
    res = {}
    for nm in sorted(found):
        top = nm.split(".")[0]
        try:
            importlib.import_module(nm)
            m = sys.modules.get(top)
            res[nm] = {"ok": True, "version": getattr(m, "__version__", None)}
        except BaseException as e:
            # "from pkg import name" where name is an attribute, not a submodule, is fine if the parent works
            parent = nm.rsplit(".", 1)[0] if "." in nm else None
            if parent and parent in res and res[parent]["ok"] and isinstance(e, ModuleNotFoundError):
                res[nm] = {"ok": True, "version": None, "note": "attribute of " + parent}
            else:
                res[nm] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
    return res


if __name__ == "__main__":
    roots = sys.argv[1:] or DEFAULT
    found, errors = scan(roots)
    extra, extra_err = scan(EXTRA) if not sys.argv[1:] else ({}, [])
    allnames = {k: set(v) for k, v in found.items()}
    for k, v in extra.items():
        allnames.setdefault(k, set()).update(v)
    res = probe(allnames)
    out = {"python": sys.version.split()[0], "roots": roots, "parse_errors": errors + extra_err, "modules": {}}
    for nm in sorted(allnames):
        out["modules"][nm] = dict(res[nm], used_by_run_scope=sorted(found.get(nm, [])),
                                  used_by_extra=sorted(extra.get(nm, []))[:4])
    json.dump(out, sys.stdout, indent=1)
