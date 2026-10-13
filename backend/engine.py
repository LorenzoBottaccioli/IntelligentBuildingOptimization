"""Which library the students' surrogate-modelling notebook is generated for.

The backend never imports BESOS or bdopt; it only writes text (the "Define the problem" cell, the notebook
template). ``SURROGATE_ENGINE`` selects the flavour of that text and must match the image that serves the
students' Jupyter (``jupyter:smartbuilding-surrogate`` for ``bdopt``). The BESOS image
(``jupyter:smartbuilding``) is no longer part of the stack: ``besos`` stays selectable here only for the old
notebooks and the tests. ``docker-compose.yml`` sets ``SURROGATE_ENGINE=bdopt`` explicitly.
"""
import os

ENGINES = ("besos", "bdopt")
DEFAULT_ENGINE = "bdopt"


def surrogate_engine() -> str:
    """``"bdopt"`` (default) or ``"besos"``, from the ``SURROGATE_ENGINE`` environment variable."""
    value = os.environ.get("SURROGATE_ENGINE", DEFAULT_ENGINE).strip().lower()
    return value if value in ENGINES else DEFAULT_ENGINE
