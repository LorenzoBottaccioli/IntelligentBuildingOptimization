"""In-memory IDF working session with a pristine copy of the upload kept aside.

Layout:
    originals/<name>.idf  pristine upload, written once, never edited
    uploads/<name>.idf    working copy -- every edit lands here
    module-level IDF      live state, parsed once and reused across requests

The working copy stays in uploads/ because the rest of the stack addresses it
there: the eptofmu container only looks in /workspace/uploads/<basename> and
names the FMU after it, inject_data.py globs uploads/, and the export bundle
ships that same file.
"""

import glob
import os
import shutil
import threading

from eppy.modeleditor import IDF

UPLOAD_FOLDER = 'uploads'
ORIGINALS_FOLDER = 'originals'
IDD_PATH = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')

# RLock so a mutate() callback can call get() without deadlocking.
_lock = threading.RLock()
_idf = None
# Bumped whenever the live model may have changed, so readers can cache what
# they derive from it (the design-space catalogue takes seconds on a real model).
_generation = 0


def generation():
    return _generation


def _bump():
    global _generation
    _generation += 1


class NoModelLoadedError(RuntimeError):
    """Raised when a caller needs the working model but none has been uploaded."""


def working_path():
    """Path of the editable copy, or None when nothing has been uploaded."""
    candidates = sorted(glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf')))
    return candidates[0] if candidates else None


def original_path():
    """Path of the pristine upload, or None when nothing has been uploaded."""
    candidates = sorted(glob.glob(os.path.join(ORIGINALS_FOLDER, '*.idf')))
    return candidates[0] if candidates else None


def has_model():
    return working_path() is not None


def load(uploaded_path):
    """Register a freshly uploaded IDF: archive it, then parse it into memory."""
    global _idf
    with _lock:
        os.makedirs(ORIGINALS_FOLDER, exist_ok=True)
        for stale in glob.glob(os.path.join(ORIGINALS_FOLDER, '*.idf')):
            os.remove(stale)
        shutil.copyfile(
            uploaded_path,
            os.path.join(ORIGINALS_FOLDER, os.path.basename(uploaded_path))
        )
        _idf = None
        _bump()
        return get()


def get():
    """Return the live IDF, re-parsing if the cache is cold.

    Re-parsing on a cold cache is what lets the working state survive a Flask
    reloader restart.
    """
    global _idf
    with _lock:
        if _idf is None:
            path = working_path()
            if not path:
                raise NoModelLoadedError('No IDF has been uploaded yet.')
            IDF.setiddname(IDD_PATH)
            _idf = IDF(path)
        return _idf


def try_get():
    """The live model without waiting: None while a request is writing it (a save can take seconds).

    For pages that poll: they keep what they showed and ask again, instead of queueing behind a write.
    """
    if not _lock.acquire(blocking=False):
        return None
    try:
        return get()
    finally:
        _lock.release()


def mutate(fn):
    """Apply fn to the live IDF, enforce invariants, and flush to disk."""
    from methods import ensure_ems_runtime

    with _lock:
        idf = get()
        result = fn(idf)
        _bump()
        ensure_ems_runtime(idf)
        idf.save()
        return result


def save():
    """Flush the in-memory model without mutating it."""
    with _lock:
        get().save()


def reset():
    """Discard every edit and restore the model the student uploaded."""
    global _idf
    with _lock:
        original = original_path()
        if not original:
            raise NoModelLoadedError('No original IDF is archived.')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        for edited in glob.glob(os.path.join(UPLOAD_FOLDER, '*.idf')):
            os.remove(edited)
        shutil.copyfile(
            original,
            os.path.join(UPLOAD_FOLDER, os.path.basename(original))
        )
        _idf = None
        _bump()
        return get()


def clear():
    """Forget the session -- used when the whole workspace is torn down."""
    global _idf
    with _lock:
        _idf = None
        _bump()
        # Empty it, do not remove it: it is a bind-mount root.
        os.makedirs(ORIGINALS_FOLDER, exist_ok=True)
        for entry in os.listdir(ORIGINALS_FOLDER):
            full = os.path.join(ORIGINALS_FOLDER, entry)
            if os.path.isdir(full) and not os.path.islink(full):
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)


def invalidate():
    """Drop the parsed model so the next get() re-reads uploads/ from disk.

    Used after the files on disk were replaced behind this module's back
    (opening a saved session): unlike load(), it leaves originals/ alone.
    """
    global _idf
    with _lock:
        _idf = None
        _bump()
