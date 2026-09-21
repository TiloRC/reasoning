"""Refuse to run unless the installed SymPy matches the pyproject.toml pin.

The ``sympy`` extra in ``pyproject.toml`` pins SymPy to a git commit; the
validation shims call :func:`check_pinned_sympy` at import time so their
re-exported tests always come from that exact suite.
"""
from __future__ import annotations

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import cast

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
    return cast("str | None",
                json.loads(direct_url).get("vcs_info", {}).get("commit_id"))


def check_pinned_sympy() -> None:
    pinned, installed = _pinned_commit(), _installed_commit()
    if installed != pinned:
        raise RuntimeError(
            f"the validation suite requires sympy @ {pinned}, but the installed "
            f"sympy is {installed or 'not installed from git'}; install it with "
            "`pip install -e '.[sympy,dev]'`"
        )
