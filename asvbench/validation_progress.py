"""Track progress of the validation suites across commits as asv benchmarks.

Each commit is measured by running the trusted harness in
``validation/compare_backends.py``: SymPy's pinned assumptions test suites
are executed against both satask backends (this checkout's
``reasoning.satask.satask`` and SymPy's own ``sympy.assumptions.satask``) in
separate pytest subprocesses.  The benchmarks report:

- ``track_passed``: PASSED count per suite file for the reasoning backend,
  the series that should climb as the engine covers more of the suite.
- ``track_passed_total``: the same count summed over both suite files.
- ``track_passed_sympy``: PASSED count per suite file for the sympy
  backend.  Control series: it measures the pinned SymPy suite against
  itself, so it should stay near-flat at a high count; movement there
  reflects a changed environment or pin, not progress in this project.
- ``track_suite_wall_time``: whole-suite wall-clock seconds per backend.

A full run costs ~50 s per backend, so the work happens once per commit in
``setup_cache``; asv pickles its return value and passes it as the first
argument to every benchmark function.  Counts and wall times are reported
as ``track_*`` benchmarks (single recorded values) rather than ``time_*``
ones, which auto-repeat and keep the minimum -- minutes of wasted
subprocess runs for a ~50 s suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from validation.compare_backends import BACKENDS, DEFAULT_SUITES, run_backend  # noqa: E402

SUITE_NAMES = [suite.stem for suite in DEFAULT_SUITES]

Runs = dict[str, tuple[dict[str, str], float]]


def setup_cache() -> Runs:
    """Run both backends once per commit; cache outcomes and wall time."""
    runs = {}
    for backend in BACKENDS:
        outcomes, _, _, wall = run_backend(backend, list(DEFAULT_SUITES), [])
        runs[backend] = (outcomes, wall)
    return runs


# Two ~50 s pytest subprocesses per commit; asv kills setup_cache after the
# 60 s default benchmark timeout otherwise.
setup_cache.timeout = 900.0


def _count_passed(runs: Runs, backend: str,
                  suite_file: str | None = None) -> int:
    outcomes, _ = runs[backend]
    return sum(1 for key, outcome in outcomes.items()
               if outcome == "PASSED"
               and (suite_file is None or key.startswith(f"{suite_file}::")))


def track_passed(runs: Runs, suite_file: str) -> int:
    """PASSED tests in one suite file against the reasoning backend."""
    return _count_passed(runs, "reasoning", suite_file)


def track_passed_total(runs: Runs) -> int:
    """PASSED tests across both suite files, reasoning backend."""
    return _count_passed(runs, "reasoning")


def track_passed_sympy(runs: Runs, suite_file: str) -> int:
    """PASSED tests in one suite file against the sympy backend (control)."""
    return _count_passed(runs, "sympy", suite_file)


def track_suite_wall_time(runs: Runs, backend: str) -> float:
    """Wall-clock seconds for one full pytest run of both suites."""
    return runs[backend][1]


track_passed.params = [SUITE_NAMES]
track_passed.unit = "tests"

track_passed_sympy.params = [SUITE_NAMES]
track_passed_sympy.unit = "tests"

track_suite_wall_time.params = [list(BACKENDS)]
track_suite_wall_time.unit = "s"
