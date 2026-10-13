"""The surrogate notebook per engine: templates, injection at upload, reset, session restore.

Covers SURROGATE_ENGINE=besos and bdopt (backend/engine.py) for

    backend/notebook_templates/Surrogate_template*.ipynb
    backend/inject_data.py          the cell that defines the uploaded model and weather file
    backend/model_editor.py         clear_workspace() resets the notebook to the engine's template
    backend/sessions.py             opening a session saved with the other flavour

Everything runs on COPIES of the backend sources in a temporary directory (the working directory
of the backend is where its relative paths -- uploads/, surrogate_notebooks/, sessions/ -- live),
so no real upload, notebook or session is touched. It needs the backend image's packages (Flask,
SQLAlchemy, eppy, nbformat), so run it there, mounting the sources read-only:

    MSYS_NO_PATHCONV=1 docker run --rm --memory=1g -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python \
        -v C:/.../backend:/repo/backend:ro -v C:/.../tests/backend:/repo/tests/backend:ro \
        backend:latest -m unittest discover -v -s /repo/tests/backend -p "test_engine_templates.py"

BACKEND_SRC overrides the location of the backend sources (default: ../../backend of this file).
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_SRC = os.environ.get('BACKEND_SRC') or os.path.abspath(os.path.join(HERE, '..', '..', 'backend'))

APP = None            # temporary copy of the backend: the working directory of every test
ORIGINAL_CWD = os.getcwd()
inject_data = model_editor = sessions = nbformat = None

WORK_DIRS = ['uploads', 'originals', 'simulation_outputs', 'user_files', 'simulation_notebooks',
             'surrogate_notebooks', 'workspace', 'field', 'sessions']
NB_REL = os.path.join('surrogate_notebooks', 'SurrogateNotebook.ipynb')

OLD_STACK = {'besos', 'tensorflow', 'keras', 'harlow', 'epw', 'seaborn', 'plotly', 'geomeppy', 'torch'}

# What inject_data has always written for BESOS (the Spanish comment and the wrench emoji included),
# and the bdopt counterpart of the shared contract (idf, epw_file).
BESOS_CELL = ('# \U0001f527 Rutas de archivos subidos por el usuario\n'
              'building = ef.get_building(r"../uploads/{idf}")\n'
              'epw_file = r"../uploads/{epw}"\n')
BDOPT_CELL = ('# Uploaded model and weather file (written by the platform at upload)\n'
              'idf = load_idf(r"../uploads/{idf}")\n'
              'epw_file = r"../uploads/{epw}"\n')
CELL = {'besos': BESOS_CELL, 'bdopt': BDOPT_CELL}


def setUpModule():
    global APP, inject_data, model_editor, sessions, nbformat
    try:
        import flask  # noqa: F401
        import flask_sqlalchemy  # noqa: F401
        import eppy  # noqa: F401
        import nbformat as _nbformat
    except ImportError as exc:  # not the backend image
        raise unittest.SkipTest(f'needs the backend image packages: {exc}')
    nbformat = _nbformat
    APP = tempfile.mkdtemp(prefix='engine_templates_')
    for name in os.listdir(BACKEND_SRC):
        if name.endswith('.py'):
            shutil.copy(os.path.join(BACKEND_SRC, name), os.path.join(APP, name))
    shutil.copytree(os.path.join(BACKEND_SRC, 'notebook_templates'),
                    os.path.join(APP, 'notebook_templates'))
    os.environ['OPENHAB_CONF_PATH'] = os.path.join(APP, 'openhab_conf')
    sys.dont_write_bytecode = True
    os.chdir(APP)
    sys.path.insert(0, APP)
    import inject_data as _inject
    import model_editor as _model_editor
    import sessions as _sessions
    from config import app, db
    inject_data, model_editor, sessions = _inject, _model_editor, _sessions
    app.register_blueprint(sessions.sessions_bp, url_prefix='/sessions')
    with app.app_context():
        db.create_all()


def tearDownModule():
    os.chdir(ORIGINAL_CWD)
    if APP:
        shutil.rmtree(APP, ignore_errors=True)


# ------------------------------------------------------------------------------ helpers

def template_file(engine):
    return os.path.join(APP, 'notebook_templates', inject_data.TEMPLATES[engine])


def read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()


def read_nb(path=NB_REL):
    return nbformat.read(path, as_version=4)


def sources(nb):
    return [cell.source for cell in nb.cells]


def install_template(engine, path=NB_REL):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copyfile(template_file(engine), path)


def install_injected(engine, idf='model.idf', epw='weather.epw', path=NB_REL):
    """A notebook as the platform leaves it after an upload: template + injected cell."""
    install_template(engine, path)
    nb = read_nb(path)
    inject_data.inject_paths(nb, engine, idf, epw)
    nbformat.write(nb, path)


def put_uploads(*names):
    os.makedirs('uploads', exist_ok=True)
    for name in names:
        with open(os.path.join('uploads', name), 'w') as handle:
            handle.write('!- test file\n')


def run_inject(engine, *args):
    """python inject_data.py as model_editor.upload_files runs it, in the temporary backend."""
    env = dict(os.environ, SURROGATE_ENGINE=engine, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([sys.executable, 'inject_data.py', *args], cwd=APP, env=env,
                          capture_output=True, text=True)


def marked_cells(nb):
    return [c for c in nb.cells if c.cell_type == 'code' and c.source.startswith(inject_data.INJECTED_MARKERS)]


class BackendCopyCase(unittest.TestCase):
    """A clean working state before each test, and the engine variable put back after."""

    def setUp(self):
        os.chdir(APP)
        for name in WORK_DIRS:
            shutil.rmtree(name, ignore_errors=True)
            os.makedirs(name)
        self._engine = os.environ.get('SURROGATE_ENGINE')
        self.addCleanup(self._restore_engine)

    def _restore_engine(self):
        if self._engine is None:
            os.environ.pop('SURROGATE_ENGINE', None)
        else:
            os.environ['SURROGATE_ENGINE'] = self._engine


# ---------------------------------------------------------------------------- templates

class TemplateFiles(BackendCopyCase):

    def test_every_engine_has_its_template(self):
        self.assertEqual(set(inject_data.TEMPLATES), {'besos', 'bdopt'})
        for engine in inject_data.TEMPLATES:
            self.assertTrue(os.path.isfile(template_file(engine)), engine)
            self.assertTrue(os.path.samefile(inject_data.template_path(engine, 'notebook_templates'),
                                             template_file(engine)))

    def test_bdopt_template_is_one_valid_setup_cell_for_the_python3_kernel(self):
        nb = read_nb(template_file('bdopt'))
        nbformat.validate(nb)
        self.assertEqual(len(nb.cells), 1)
        self.assertEqual(nb.cells[0].cell_type, 'code')
        # image B has the kernel "python3" and no other
        self.assertEqual(nb.metadata.kernelspec.name, 'python3')
        self.assertEqual(nb.metadata.language_info.name, 'python')
        self.assertEqual(nb.metadata.get('platform_engine'), 'bdopt')
        self.assertEqual(inject_data.notebook_flavour(nb), 'bdopt')

    def test_bdopt_template_imports_bdopt_and_nothing_of_the_old_stack(self):
        source = read_nb(template_file('bdopt')).cells[0].source
        code = '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith('%'))
        tree = ast.parse(code)
        modules, names = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.')[0] for alias in node.names)
                names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module.split('.')[0])
                names.update(alias.asname or alias.name for alias in node.names)
        self.assertFalse(modules & OLD_STACK, modules & OLD_STACK)
        for module in ('bdopt', 'numpy', 'pandas', 'matplotlib'):
            self.assertIn(module, modules)
        for name in ('load_idf', 'AdaptiveSampler', 'GPSurrogate', 'lhs', 'nsga2'):
            self.assertIn(name, names)
        # inject_data defines idf and epw_file; the template must not look for the files itself
        self.assertNotIn('glob', modules)
        self.assertNotIn('pathlib', modules)

    def test_besos_template_is_still_the_besos_one(self):
        nb = read_nb(template_file('besos'))
        self.assertNotIn('platform_engine', nb.metadata)
        self.assertIn('from besos import', nb.cells[0].source)
        self.assertEqual(inject_data.notebook_flavour(nb), 'besos')


# ------------------------------------------------------------------------------ flavour

class Flavour(BackendCopyCase):

    @staticmethod
    def notebook(*cells, **metadata):
        nb = nbformat.v4.new_notebook(metadata=metadata)
        for kind, text in cells:
            nb.cells.append(nbformat.v4.new_code_cell(text) if kind == 'code'
                            else nbformat.v4.new_markdown_cell(text))
        return nb

    def test_imports_decide_when_there_is_no_marker(self):
        flavour = inject_data.notebook_flavour
        self.assertEqual(flavour(self.notebook(('code', 'from besos import sampling'))), 'besos')
        self.assertEqual(flavour(self.notebook(('code', '    import besos'))), 'besos')
        self.assertEqual(flavour(self.notebook(('code', 'from bdopt.sampling import lhs'))), 'bdopt')

    def test_the_marker_wins_over_the_imports(self):
        nb = self.notebook(('code', 'from besos import sampling'), platform_engine='bdopt')
        self.assertEqual(inject_data.notebook_flavour(nb), 'bdopt')
        nb = self.notebook(('code', 'import bdopt'), platform_engine='besos')
        self.assertEqual(inject_data.notebook_flavour(nb), 'besos')

    def test_unclear_means_none(self):
        flavour = inject_data.notebook_flavour
        self.assertIsNone(flavour(self.notebook(('code', 'import numpy'))))
        self.assertIsNone(flavour(self.notebook(('code', 'from besos import x\nfrom bdopt import y'))))
        # a comment, a string or a markdown cell that merely names the library is not an import
        self.assertIsNone(flavour(self.notebook(('code', '# BESOS\nx = "from besos import y"'))))
        self.assertIsNone(flavour(self.notebook(('markdown', 'from besos import sampling'))))
        # a marker that is not an engine is ignored
        self.assertIsNone(flavour(self.notebook(('code', 'x = 1'), platform_engine='tensorflow')))


# --------------------------------------------------------------------------- injection

class Injection(BackendCopyCase):

    def test_besos_cell_text_is_what_it_always_was(self):
        self.assertEqual(
            inject_data.injected_source('besos', 'lab_optimal.idf', 'my_epw_file.epw'),
            '# \U0001f527 Rutas de archivos subidos por el usuario\n'
            'building = ef.get_building(r"../uploads/lab_optimal.idf")\n'
            'epw_file = r"../uploads/my_epw_file.epw"\n')

    def test_a_name_a_raw_string_cannot_hold_is_quoted(self):
        text = inject_data.injected_source('bdopt', 'we"ird.idf', 'w.epw')
        compile(text, '<cell>', 'exec')
        self.assertIn("'../uploads/we\"ird.idf'", text)

    def test_inserted_once_right_after_the_setup_cell(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                install_template(engine)
                put_uploads('model.idf', 'weather.epw')
                done = run_inject(engine, 'model.idf', 'weather.epw')
                self.assertEqual(done.returncode, 0, done.stderr)
                nb = read_nb()
                nbformat.validate(nb)
                self.assertEqual(len(nb.cells), 2)
                self.assertEqual(nb.cells[0].source, read_nb(template_file(engine)).cells[0].source)
                self.assertEqual(nb.cells[1].source, CELL[engine].format(idf='model.idf', epw='weather.epw'))
                self.assertEqual(nb.cells[1].cell_type, 'code')

    def test_a_second_upload_of_the_same_files_changes_nothing(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                install_template(engine)
                put_uploads('model.idf', 'weather.epw')
                run_inject(engine, 'model.idf', 'weather.epw')
                first = read_bytes(NB_REL)
                again = run_inject(engine, 'model.idf', 'weather.epw')
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertEqual(read_bytes(NB_REL), first)
                self.assertEqual(len(marked_cells(read_nb())), 1)

    def test_a_second_upload_of_other_files_updates_the_cell_instead_of_adding_one(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                install_template(engine)
                put_uploads('model.idf', 'weather.epw', 'other.idf', 'other.epw')
                run_inject(engine, 'model.idf', 'weather.epw')
                nb = read_nb()
                nb.cells.append(nbformat.v4.new_code_cell('x = 1'))      # the student's own work
                nb.cells[1]['outputs'] = [nbformat.v4.new_output('stream', name='stdout', text='old')]
                nb.cells[1]['execution_count'] = 3
                nbformat.write(nb, NB_REL)
                done = run_inject(engine, 'other.idf', 'other.epw')
                self.assertEqual(done.returncode, 0, done.stderr)
                nb = read_nb()
                self.assertEqual(len(nb.cells), 3)
                self.assertEqual(len(marked_cells(nb)), 1)
                self.assertEqual(nb.cells[1].source, CELL[engine].format(idf='other.idf', epw='other.epw'))
                self.assertEqual(nb.cells[1].outputs, [])
                self.assertIsNone(nb.cells[1].execution_count)
                self.assertEqual(nb.cells[2].source, 'x = 1')

    def test_cells_left_by_the_old_script_are_all_updated_not_added_to(self):
        # the old skip rule never matched: every upload added a cell
        install_template('besos')
        nb = read_nb()
        for idf in ('first.idf', 'second.idf'):
            nb.cells.insert(1, nbformat.v4.new_code_cell(BESOS_CELL.format(idf=idf, epw='w.epw')))
        nbformat.write(nb, NB_REL)
        put_uploads('third.idf', 'w.epw')
        done = run_inject('besos', 'third.idf', 'w.epw')
        self.assertEqual(done.returncode, 0, done.stderr)
        nb = read_nb()
        self.assertEqual(len(nb.cells), 3)
        self.assertEqual([c.source for c in marked_cells(nb)],
                         [BESOS_CELL.format(idf='third.idf', epw='w.epw')] * 2)

    def test_without_arguments_the_first_of_each_in_sorted_order(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                shutil.rmtree('uploads')
                put_uploads('z_last.idf', 'b_model.idf', 'a_model.idf', 'z.epw', 'm.epw', 'fmu_roles.json')
                install_template(engine)
                done = run_inject(engine)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(read_nb().cells[1].source,
                                 CELL[engine].format(idf='a_model.idf', epw='m.epw'))
                # with arguments, the files just uploaded win over any other
                run_inject(engine, 'z_last.idf', 'z.epw')
                self.assertEqual(read_nb().cells[1].source,
                                 CELL[engine].format(idf='z_last.idf', epw='z.epw'))

    def test_missing_files_are_an_error_and_leave_the_notebook_alone(self):
        install_template('besos')
        before = read_bytes(NB_REL)
        put_uploads('model.idf')                                  # no weather file
        self.assertNotEqual(run_inject('besos').returncode, 0)
        self.assertNotEqual(run_inject('besos', 'model.idf', 'weather.epw').returncode, 0)
        self.assertNotEqual(run_inject('besos', '../uploads/model.idf', 'weather.epw').returncode, 0)
        self.assertNotEqual(run_inject('besos', 'model.idf').returncode, 0)
        self.assertEqual(read_bytes(NB_REL), before)

    def test_a_missing_notebook_is_recreated_from_the_engine_template(self):
        put_uploads('model.idf', 'weather.epw')
        done = run_inject('bdopt', 'model.idf', 'weather.epw')
        self.assertEqual(done.returncode, 0, done.stderr)
        nb = read_nb()
        self.assertEqual(inject_data.notebook_flavour(nb), 'bdopt')
        self.assertEqual(len(nb.cells), 2)

    def test_a_notebook_of_the_other_flavour_is_replaced_and_kept_beside(self):
        for engine, other in (('bdopt', 'besos'), ('besos', 'bdopt')):
            with self.subTest(engine=engine):
                shutil.rmtree('surrogate_notebooks')
                os.makedirs('surrogate_notebooks')
                put_uploads('model.idf', 'weather.epw')
                install_injected(other, 'old.idf', 'old.epw')
                nb = read_nb()
                nb.cells.append(nbformat.v4.new_code_cell('student_work = 42'))
                nbformat.write(nb, NB_REL)
                old = read_bytes(NB_REL)

                done = run_inject(engine, 'model.idf', 'weather.epw')
                self.assertEqual(done.returncode, 0, done.stderr)
                backup = os.path.join('surrogate_notebooks', f'SurrogateNotebook_{other}_backup.ipynb')
                self.assertEqual(read_bytes(backup), old)
                nb = read_nb()
                self.assertEqual(inject_data.notebook_flavour(nb), engine)
                self.assertEqual(len(nb.cells), 2)
                self.assertEqual(nb.cells[1].source, CELL[engine].format(idf='model.idf', epw='weather.epw'))
                self.assertNotIn('student_work', ''.join(sources(nb)))

                # a second replacement never overwrites the first copy
                install_injected(other, 'older.idf', 'older.epw')
                newer = read_bytes(NB_REL)
                run_inject(engine, 'model.idf', 'weather.epw')
                self.assertEqual(read_bytes(backup), old)
                backup2 = os.path.join('surrogate_notebooks', f'SurrogateNotebook_{other}_backup_2.ipynb')
                self.assertEqual(read_bytes(backup2), newer)

    def test_a_notebook_whose_flavour_cannot_be_told_is_kept(self):
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_code_cell('import pandas'), nbformat.v4.new_code_cell('y = 2')]
        nbformat.write(nb, NB_REL)
        put_uploads('model.idf', 'weather.epw')
        done = run_inject('bdopt', 'model.idf', 'weather.epw')
        self.assertEqual(done.returncode, 0, done.stderr)
        nb = read_nb()
        self.assertEqual(sources(nb)[0], 'import pandas')
        self.assertEqual(nb.cells[1].source, BDOPT_CELL.format(idf='model.idf', epw='weather.epw'))
        self.assertEqual(sorted(os.listdir('surrogate_notebooks')), ['SurrogateNotebook.ipynb'])

    def test_an_unreadable_notebook_is_replaced_and_kept(self):
        with open(NB_REL, 'w') as handle:
            handle.write('{ this is not json')
        put_uploads('model.idf', 'weather.epw')
        done = run_inject('bdopt', 'model.idf', 'weather.epw')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(inject_data.notebook_flavour(read_nb()), 'bdopt')
        kept = os.path.join('surrogate_notebooks', 'SurrogateNotebook_unreadable_backup.ipynb')
        self.assertEqual(read_bytes(kept), b'{ this is not json')

    def test_upload_files_hands_the_saved_names_to_the_script(self):
        import inspect
        source = inspect.getsource(model_editor.upload_files)
        self.assertIn('"inject_data.py", original_idf_filename, epw_filename', source)


# --------------------------------------------------------------------------------- reset

class Reset(BackendCopyCase):

    def reset_with(self, engine):
        from config import app
        if engine is None:
            os.environ.pop('SURROGATE_ENGINE', None)
        else:
            os.environ['SURROGATE_ENGINE'] = engine
        with app.app_context():
            model_editor.clear_workspace()

    def test_reset_puts_back_the_template_of_the_engine(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                install_injected('besos' if engine == 'bdopt' else 'bdopt')
                self.reset_with(engine)
                self.assertEqual(read_bytes(NB_REL), read_bytes(template_file(engine)))

    def test_bdopt_is_the_default(self):
        install_injected('besos')
        self.reset_with(None)
        self.assertEqual(read_bytes(NB_REL), read_bytes(template_file('bdopt')))
        self.assertEqual(inject_data.notebook_flavour(read_nb()), 'bdopt')

    def test_besos_still_resets_byte_for_byte_as_before(self):
        install_injected('bdopt')
        self.reset_with('besos')
        self.assertEqual(read_bytes(NB_REL), read_bytes(os.path.join('notebook_templates', 'Surrogate_template.ipynb')))
        self.assertEqual(inject_data.notebook_flavour(read_nb()), 'besos')

    def test_reset_empties_the_working_state_as_before(self):
        put_uploads('model.idf', 'weather.epw')
        os.makedirs('originals', exist_ok=True)
        with open(os.path.join('originals', 'model.idf'), 'w') as handle:
            handle.write('x')
        self.reset_with('bdopt')
        self.assertEqual(os.listdir('uploads'), [])
        self.assertEqual(os.listdir('originals'), [])
        self.assertTrue(os.path.isdir(os.path.join('workspace', 'logs')))

    def test_reset_then_upload_gives_the_bdopt_student_the_cell(self):
        self.reset_with('bdopt')
        put_uploads('model.idf', 'weather.epw')
        done = run_inject('bdopt', 'model.idf', 'weather.epw')
        self.assertEqual(done.returncode, 0, done.stderr)
        nb = read_nb()
        self.assertEqual(len(nb.cells), 2)
        self.assertEqual(inject_data.notebook_flavour(nb), 'bdopt')
        self.assertIn('idf = load_idf(r"../uploads/model.idf")', nb.cells[1].source)

    def test_the_dead_restore_notebook_function_is_gone(self):
        self.assertFalse(hasattr(model_editor, 'restore_notebook'))


# --------------------------------------------------------------------------- sessions

def make_snapshot(sid, notebook_engine=None, with_model=True, extra_backup=False):
    """sessions/<sid>/ with a state whose surrogate notebook is `notebook_engine`'s."""
    base = os.path.join('sessions', sid)
    state = os.path.join(base, 'state')
    os.makedirs(os.path.join(state, 'surrogate_notebooks'))
    os.makedirs(os.path.join(state, 'uploads'))
    with open(os.path.join(base, 'meta.json'), 'w') as handle:
        json.dump({'id': sid, 'name': sid, 'created': 'x', 'saved': 'x', 'idf': '', 'epw': ''}, handle)
    if with_model:
        for name in ('model.idf', 'weather.epw'):
            with open(os.path.join(state, 'uploads', name), 'w') as handle:
                handle.write('x')
    if notebook_engine:
        nb_path = os.path.join(state, NB_REL)
        install_template(notebook_engine, nb_path)
        if with_model:
            nb = read_nb(nb_path)
            inject_data.inject_paths(nb, notebook_engine, 'model.idf', 'weather.epw')
            nb.cells.append(nbformat.v4.new_code_cell('student_work = 42'))
            nbformat.write(nb, nb_path)
    if extra_backup:
        shutil.copyfile(template_file('besos'),
                        os.path.join(state, 'surrogate_notebooks', 'SurrogateNotebook_besos_backup.ipynb'))
    return state


class SessionRestore(BackendCopyCase):

    def restore(self, sid, engine):
        os.environ['SURROGATE_ENGINE'] = engine
        return sessions._restore(sid)

    def test_a_besos_session_on_a_bdopt_platform(self):
        state = make_snapshot('old', 'besos')
        saved = read_bytes(os.path.join(state, NB_REL))
        warnings = self.restore('old', 'bdopt')
        self.assertEqual(len(warnings), 1)
        self.assertIn('SurrogateNotebook_besos_backup.ipynb', warnings[0])
        nb = read_nb()
        self.assertEqual(inject_data.notebook_flavour(nb), 'bdopt')
        self.assertEqual(nb.metadata.get('platform_engine'), 'bdopt')
        self.assertEqual(len(nb.cells), 2)
        self.assertEqual(nb.cells[1].source, BDOPT_CELL.format(idf='model.idf', epw='weather.epw'))
        # nothing lost: the old notebook, byte for byte, next to the new one
        self.assertEqual(read_bytes(os.path.join('surrogate_notebooks', 'SurrogateNotebook_besos_backup.ipynb')), saved)
        # the rest of the session came back
        self.assertEqual(sorted(os.listdir('uploads')), ['model.idf', 'weather.epw'])
        # and the snapshot itself was not touched
        self.assertEqual(read_bytes(os.path.join(state, NB_REL)), saved)

    def test_a_bdopt_session_on_a_besos_platform(self):
        state = make_snapshot('new', 'bdopt')
        saved = read_bytes(os.path.join(state, NB_REL))
        warnings = self.restore('new', 'besos')
        self.assertEqual(len(warnings), 1)
        self.assertIn('SurrogateNotebook_bdopt_backup.ipynb', warnings[0])
        nb = read_nb()
        self.assertEqual(inject_data.notebook_flavour(nb), 'besos')
        self.assertEqual(nb.cells[1].source, BESOS_CELL.format(idf='model.idf', epw='weather.epw'))
        self.assertEqual(read_bytes(os.path.join('surrogate_notebooks', 'SurrogateNotebook_bdopt_backup.ipynb')), saved)

    def test_a_session_of_the_same_flavour_is_restored_untouched(self):
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                shutil.rmtree('sessions')
                os.makedirs('sessions')
                state = make_snapshot('same', engine)
                self.assertEqual(self.restore('same', engine), [])
                self.assertEqual(read_bytes(NB_REL), read_bytes(os.path.join(state, NB_REL)))
                self.assertEqual(os.listdir('surrogate_notebooks'), ['SurrogateNotebook.ipynb'])

    def test_a_notebook_of_unknown_flavour_is_restored_untouched(self):
        state = make_snapshot('odd', None)
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_code_cell('import pandas')]
        nbformat.write(nb, os.path.join(state, NB_REL))
        self.assertEqual(self.restore('odd', 'bdopt'), [])
        self.assertEqual(read_bytes(NB_REL), read_bytes(os.path.join(state, NB_REL)))

    def test_a_session_that_never_had_a_notebook_gets_none(self):
        # as before the flavour check existed: restoring does not create what the session lacked
        for engine in ('besos', 'bdopt'):
            with self.subTest(engine=engine):
                shutil.rmtree('sessions')
                os.makedirs('sessions')
                make_snapshot('bare', None)
                self.assertEqual(self.restore('bare', engine), [])
                self.assertEqual(os.listdir('surrogate_notebooks'), [])
                self.assertEqual(inject_data.align_notebook(engine, create=False), ('missing', None))
                self.assertEqual(os.listdir('surrogate_notebooks'), [])

    def test_an_existing_backup_in_the_session_is_not_overwritten(self):
        state = make_snapshot('twice', 'besos', extra_backup=True)
        first = read_bytes(os.path.join(state, 'surrogate_notebooks', 'SurrogateNotebook_besos_backup.ipynb'))
        saved = read_bytes(os.path.join(state, NB_REL))
        warnings = self.restore('twice', 'bdopt')
        self.assertIn('SurrogateNotebook_besos_backup_2.ipynb', warnings[0])
        self.assertEqual(read_bytes(os.path.join('surrogate_notebooks', 'SurrogateNotebook_besos_backup.ipynb')), first)
        self.assertEqual(read_bytes(os.path.join('surrogate_notebooks', 'SurrogateNotebook_besos_backup_2.ipynb')), saved)

    def test_a_session_without_a_model_gets_the_bare_template(self):
        make_snapshot('empty', 'besos', with_model=False)
        warnings = self.restore('empty', 'bdopt')
        self.assertEqual(len(warnings), 1)
        self.assertEqual(read_bytes(NB_REL), read_bytes(template_file('bdopt')))

    def test_the_open_route_reports_the_replacement(self):
        from config import app
        make_snapshot('viaroute', 'besos')
        os.environ['SURROGATE_ENGINE'] = 'bdopt'
        with mock.patch.object(sessions, '_require_building_stopped'), \
                mock.patch.object(sessions, '_rebuild_memory', return_value=[]), \
                mock.patch.object(sessions.session_stores, 'influx_restore', return_value=[]), \
                mock.patch.object(sessions.session_stores, 'grafana_restore', return_value=[]):
            reply = app.test_client().post('/sessions/open', json={'id': 'viaroute'})
        self.assertEqual(reply.status_code, 200, reply.get_data(as_text=True))
        payload = reply.get_json()
        self.assertEqual(len(payload['warnings']), 1)
        self.assertIn('SurrogateNotebook_besos_backup.ipynb', payload['warnings'][0])
        self.assertEqual(payload['current'], 'viaroute')
        self.assertEqual(inject_data.notebook_flavour(read_nb()), 'bdopt')

    def test_the_open_route_says_nothing_for_a_matching_session(self):
        from config import app
        make_snapshot('quiet', 'bdopt')
        os.environ['SURROGATE_ENGINE'] = 'bdopt'
        with mock.patch.object(sessions, '_require_building_stopped'), \
                mock.patch.object(sessions, '_rebuild_memory', return_value=[]), \
                mock.patch.object(sessions.session_stores, 'influx_restore', return_value=[]), \
                mock.patch.object(sessions.session_stores, 'grafana_restore', return_value=[]):
            reply = app.test_client().post('/sessions/open', json={'id': 'quiet'})
        self.assertEqual(reply.status_code, 200, reply.get_data(as_text=True))
        self.assertNotIn('warnings', reply.get_json())


if __name__ == '__main__':
    unittest.main()
