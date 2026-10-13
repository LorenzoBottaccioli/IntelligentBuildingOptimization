"""Put the uploaded model and weather file into the student's surrogate notebook.

Runs in the backend container as a subprocess after every upload (model_editor.upload_files):

    python inject_data.py [<model>.idf <weather>.epw]

The upload route passes the names of the two files it has just saved. Without arguments
the files are found in uploads/ in sorted order, the same rule idf_session.working_path()
and sessions.py use, never in os.listdir() order.

What is inserted depends on SURROGATE_ENGINE (engine.py), right after the setup cell
(cell 0) of surrogate_notebooks/SurrogateNotebook.ipynb:

    besos   building = ef.get_building(r"../uploads/<model>.idf")
            epw_file = r"../uploads/<weather>.epw"
    bdopt   idf = load_idf(r"../uploads/<model>.idf")
            epw_file = r"../uploads/<weather>.epw"

The cell starts with a comment line that this module recognises (INJECTED_MARKERS), so a
second upload updates that cell in place instead of adding another one.

The module is also the one place that knows which library ("flavour") a surrogate notebook
was written for, because sessions.py needs it when a saved session is opened:

    notebook_flavour(nb)   'besos', 'bdopt' or None (cannot tell)
    align_notebook(...)    make SurrogateNotebook.ipynb the flavour of the active engine,
                           keeping a copy of the notebook it replaces
    inject_file(...)       the injection itself

Importing it has no side effects; the script part is main().
"""

import os
import re
import shutil
import sys

import nbformat
from nbformat.v4 import new_code_cell

from engine import ENGINES, surrogate_engine

UPLOAD_DIR = 'uploads'
NOTEBOOK_DIR = 'surrogate_notebooks'
NOTEBOOK_NAME = 'SurrogateNotebook.ipynb'
TEMPLATES_DIR = 'notebook_templates'

#: engine -> template the notebook is reset to (model_editor.clear_workspace)
TEMPLATES = {
    'besos': 'Surrogate_template.ipynb',
    'bdopt': 'Surrogate_template_bdopt.ipynb',
}

#: Notebook metadata key that names the flavour. The bdopt template carries it; the BESOS
#: template is left as it always was and is recognised by its imports.
FLAVOUR_KEY = 'platform_engine'

#: First line of the injected cell: the legacy BESOS cell (Spanish, with a wrench emoji)
#: and the bdopt one. Whoever finds a code cell starting like this knows who wrote it.
INJECTED_MARKERS = (
    '# \U0001f527 Rutas de archivos subidos',
    '# Uploaded model and weather file',
)

_IMPORT_BESOS = re.compile(r'^\s*(?:from|import)\s+besos\b', re.MULTILINE)
_IMPORT_BDOPT = re.compile(r'^\s*(?:from|import)\s+bdopt\b', re.MULTILINE)


# ------------------------------------------------------------------ the cell

def _literal(relative_path):
    """r"..." for the usual file name; repr() for a name a raw string cannot hold."""
    if any(ch in relative_path for ch in '"\\\n\r'):
        return repr(relative_path)
    return f'r"{relative_path}"'


def injected_source(engine, idf_name, epw_name):
    """Source of the cell that defines the model and the weather file for `engine`."""
    idf_ref = _literal(f'../uploads/{idf_name}')
    epw_ref = _literal(f'../uploads/{epw_name}')
    if engine == 'bdopt':
        return (
            '# Uploaded model and weather file (written by the platform at upload)\n'
            f'idf = load_idf({idf_ref})\n'
            f'epw_file = {epw_ref}\n'
        )
    return (
        '# \U0001f527 Rutas de archivos subidos por el usuario\n'
        f'building = ef.get_building({idf_ref})\n'
        f'epw_file = {epw_ref}\n'
    )


def inject_paths(nb, engine, idf_name, epw_name):
    """Make `nb` define the model and weather file. Returns 'inserted', 'updated' or 'unchanged'.

    A cell this module wrote earlier (see INJECTED_MARKERS) is rewritten in place, all of
    them if an older version of this script left several; otherwise one new cell goes
    right after the setup cell.
    """
    source = injected_source(engine, idf_name, epw_name)
    marked = [c for c in nb.cells
              if c.cell_type == 'code' and c.source.startswith(INJECTED_MARKERS)]
    if not marked:
        nb.cells.insert(min(1, len(nb.cells)), new_code_cell(source))
        return 'inserted'
    action = 'unchanged'
    for cell in marked:
        if cell.source != source:
            cell.source = source
            # Whatever it printed belongs to the code it replaces.
            cell['outputs'] = []
            cell['execution_count'] = None
            action = 'updated'
    return action


def inject_file(nb_path, engine, idf_name, epw_name):
    """inject_paths() on the notebook file; written only if something changed."""
    nb = nbformat.read(nb_path, as_version=4)
    action = inject_paths(nb, engine, idf_name, epw_name)
    if action != 'unchanged':
        nbformat.write(nb, nb_path)
    return action


# ------------------------------------------------------------ the uploaded files

def _check_name(name):
    if not name or os.path.basename(name) != name:
        raise ValueError(f'Not a plain file name: {name!r}')
    if not os.path.isfile(os.path.join(UPLOAD_DIR, name)):
        raise RuntimeError(f'{name} is not in {UPLOAD_DIR}')
    return name


def uploaded_files(upload_dir=UPLOAD_DIR):
    """(model, weather file) found in uploads/: the first of each in sorted order."""
    names = sorted(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else []
    idf_files = [f for f in names if f.lower().endswith('.idf')]
    epw_files = [f for f in names if f.lower().endswith('.epw')]
    if not idf_files or not epw_files:
        raise RuntimeError('No .idf or .epw files found in uploads')
    return idf_files[0], epw_files[0]


# ----------------------------------------------------------------- the flavour

def notebook_flavour(nb):
    """'besos' or 'bdopt': the library the notebook was written for; None when it cannot be told.

    The metadata marker wins. Without one the imports decide, and a notebook that imports
    both (or neither) is left undecided.
    """
    marker = nb.metadata.get(FLAVOUR_KEY)
    if marker in ENGINES:
        return marker
    code = '\n'.join(c.source for c in nb.cells if c.cell_type == 'code')
    besos = bool(_IMPORT_BESOS.search(code))
    bdopt = bool(_IMPORT_BDOPT.search(code))
    if besos and not bdopt:
        return 'besos'
    if bdopt and not besos:
        return 'bdopt'
    return None


def template_path(engine=None, templates_dir=TEMPLATES_DIR):
    return os.path.join(templates_dir, TEMPLATES[engine or surrogate_engine()])


def _free_backup_path(nb_path, flavour):
    """SurrogateNotebook_<flavour>_backup.ipynb, or _2, _3, ... if that name is taken."""
    stem, ext = os.path.splitext(nb_path)
    candidate = f'{stem}_{flavour}_backup{ext}'
    number = 2
    while os.path.exists(candidate):
        candidate = f'{stem}_{flavour}_backup_{number}{ext}'
        number += 1
    return candidate


def _install_template(template, nb_path):
    # Copy beside the target, then rename: Jupyter never sees half a notebook.
    temp = nb_path + '.tmp'
    shutil.copyfile(template, temp)
    os.replace(temp, nb_path)


def align_notebook(engine=None, nb_dir=NOTEBOOK_DIR, templates_dir=TEMPLATES_DIR, create=True):
    """Make surrogate_notebooks/SurrogateNotebook.ipynb a notebook of the active engine's flavour.

    Returns (action, backup):
      ('created', None)   there was no notebook: the template was copied
      ('missing', None)   there was no notebook and create=False: nothing was done
      ('kept', None)      it is of the right flavour, or the flavour cannot be told: untouched
      ('replaced', name)  it was of the other flavour (or unreadable): copied to `name`
                          (never overwriting an earlier copy) and replaced by the template
    A replaced notebook has no paths in it; the caller injects them.

    The upload (main) wants a notebook to inject into, so it creates a missing one. Opening
    a saved session (sessions.py) passes create=False: that session never had one and
    gets none, as before.
    """
    engine = engine or surrogate_engine()
    nb_path = os.path.join(nb_dir, NOTEBOOK_NAME)
    template = template_path(engine, templates_dir)
    if not os.path.isfile(nb_path):
        if not create:
            return 'missing', None
        os.makedirs(nb_dir, exist_ok=True)
        _install_template(template, nb_path)
        return 'created', None
    try:
        flavour = notebook_flavour(nbformat.read(nb_path, as_version=4))
    except Exception:
        flavour = 'unreadable'
    if flavour is None or flavour == engine:
        return 'kept', None
    backup = _free_backup_path(nb_path, flavour)
    shutil.copy2(nb_path, backup)
    _install_template(template, nb_path)
    return 'replaced', os.path.basename(backup)


# ----------------------------------------------------------------------- script

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (0, 2):
        raise SystemExit('usage: inject_data.py [<model>.idf <weather>.epw]')
    if argv:
        idf_name, epw_name = _check_name(argv[0]), _check_name(argv[1])
    else:
        idf_name, epw_name = uploaded_files()

    engine = surrogate_engine()
    nb_path = os.path.join(NOTEBOOK_DIR, NOTEBOOK_NAME)

    # A notebook of the other flavour cannot run on this engine's image: replace it
    # (the old one stays beside it) before the paths go in.
    aligned, backup = align_notebook(engine)
    if aligned == 'replaced':
        print(f'{nb_path} was written for another library; kept as {backup}')
    elif aligned == 'created':
        print(f'{nb_path} was missing; created from the {engine} template')

    action = inject_file(nb_path, engine, idf_name, epw_name)
    if action == 'unchanged':
        print(f'{nb_path} already points at IDF={idf_name} and EPW={epw_name}')
    else:
        verb = 'Injected cell into' if action == 'inserted' else 'Updated injected cell in'
        print(f'{verb} {nb_path} with IDF={idf_name} and EPW={epw_name}')


if __name__ == '__main__':
    main()
