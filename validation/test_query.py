"""Run SymPy's own ``test_query.py`` against this checkout's ``satask``.

The suite is imported from the installed SymPy, which the ``sympy`` extra in
``pyproject.toml`` pins to a git commit.  ``ask`` and ``_ask_recursive`` are
rebound to ``reasoning.satask.satask`` in the imported module, and the test
functions are re-exported so pytest collects them.

``validation/compare_backends.py`` runs the same upstream suite with those
names bound to SymPy's ``satask`` instead, and compares the outcomes.
"""
from __future__ import annotations

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

_PIN = re.compile(r"sympy @ git\+\S+?@([0-9a-f]{40})")


def _pinned_commit() -> str | None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = _PIN.search(pyproject.read_text())
    return match.group(1) if match else None


def _installed_commit() -> str | None:
    try:
        direct_url = distribution("sympy").read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if direct_url is None:
        return None
    return json.loads(direct_url).get("vcs_info", {}).get("commit_id")


def _check_pinned_sympy() -> None:
    pinned, installed = _pinned_commit(), _installed_commit()
    if installed != pinned:
        raise RuntimeError(
            f"the validation suite requires sympy @ {pinned}, but the installed "
            f"sympy is {installed or 'not installed from git'}; install it with "
            "`pip install -e '.[sympy,dev]'`"
        )


_check_pinned_sympy()

from reasoning.satask import satask as _satask  # noqa: E402
from sympy.assumptions.tests import test_query as _suite  # noqa: E402

_suite.ask = _satask
_suite._ask_recursive = _satask

from sympy.assumptions.tests.test_query import *  # noqa: E402,F401,F403
