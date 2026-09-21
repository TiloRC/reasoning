"""Run SymPy's own ``test_matrices.py`` against this checkout's ``satask``.

The suite is imported from the installed SymPy, which the ``sympy`` extra in
``pyproject.toml`` pins to a git commit.  ``ask`` and ``_ask_recursive`` are
rebound to ``reasoning.satask.satask`` in the imported module, and the test
functions are re-exported so pytest collects them.

``validation/compare_backends.py`` runs the same upstream suite with those
names bound to SymPy's ``satask`` instead, and compares the outcomes.
"""
from ._pinned_sympy import check_pinned_sympy

check_pinned_sympy()

from reasoning.satask import satask as _satask  # noqa: E402
from sympy.assumptions.tests import test_matrices as _suite  # noqa: E402

_suite.ask = _satask
_suite._ask_recursive = _satask

from sympy.assumptions.tests.test_matrices import *  # noqa: E402,F401,F403
