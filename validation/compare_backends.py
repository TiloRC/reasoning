"""Compare satask backends by running the validation suite against each.

Example::

    .venv/bin/python validation/compare_backends.py

``validation/test_query.py`` re-exports SymPy's pinned ``test_query`` suite
with ``ask`` and ``_ask_recursive`` rebound to this checkout's ``satask``.  The
SymPy backend runs a temporary re-export of the same upstream suite with those
names rebound to ``sympy.assumptions.satask``.  Each backend runs in its own
pytest subprocess; per-test outcomes and timings are compared.  The exit status
is 1 when the backends disagree and 0 otherwise.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = Path(__file__).resolve().parent / "test_query.py"
BACKENDS = ("reasoning", "sympy")
SYMPY_SUITE = "sympy.assumptions.tests.test_query"
SYMPY_PACKAGE, SYMPY_MODULE = SYMPY_SUITE.rsplit(".", 1)
SYMPY_BACKEND_SUITE = f"""\
from {SYMPY_PACKAGE} import {SYMPY_MODULE} as _suite
from sympy.assumptions.satask import satask as _satask

_suite.ask = _satask
_suite._ask_recursive = _satask

from {SYMPY_SUITE} import *  # noqa: E402,F401,F403
"""
REASONING_BINDING = "from reasoning.satask import satask"

OUTCOME = re.compile(r"^(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)\s+(\S+)", re.MULTILINE)
OUTCOMES = ("PASSED", "FAILED", "ERROR", "XFAIL", "XPASS", "SKIPPED")


def write_sympy_suite(directory: Path) -> Path:
    target = directory / "test_query_sympy.py"
    target.write_text(SYMPY_BACKEND_SUITE)
    return target


def run_pytest(suite: Path, report: Path, pytest_args: list[str]) -> tuple[str, float]:
    command = [
        sys.executable, "-m", "pytest", str(suite),
        "-q", "--tb=no", "-rA", "--color=no", "--no-header",
        "-p", "no:cacheprovider", f"--junit-xml={report}", *pytest_args,
    ]
    start = perf_counter()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return result.stdout + result.stderr, perf_counter() - start


def parse_outcomes(output: str) -> dict[str, str]:
    outcomes = {}
    for outcome, nodeid in OUTCOME.findall(output):
        outcomes[nodeid.rsplit("::", 1)[-1]] = outcome
    return outcomes


def parse_timings(report: Path) -> dict[str, float]:
    if not report.exists():
        return {}
    timings = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        name = case.get("name")
        time = case.get("time")
        if name is not None:
            timings[name] = float(time) if time is not None else 0.0
    return timings


def run_backend(backend: str, suite: Path,
                pytest_args: list[str]) -> tuple[dict[str, str], dict[str, float], float]:
    with tempfile.TemporaryDirectory(dir=suite.parent) as directory_name:
        directory = Path(directory_name)
        target = (suite if backend == "reasoning"
                  else write_sympy_suite(directory))
        output, wall = run_pytest(target, directory / "report.xml", pytest_args)
        timings = parse_timings(directory / "report.xml")
    outcomes = parse_outcomes(output)
    if not outcomes:
        print(output, file=sys.stderr)
        raise SystemExit(f"pytest collected no tests for the {backend} backend")
    return outcomes, timings, wall


def summarize(outcomes: dict[str, str]) -> str:
    counts = Counter(outcomes.values())
    return ", ".join(f"{counts[outcome]} {outcome.lower()}" for outcome in OUTCOMES
                     if counts[outcome])


def format_time(seconds: float | None) -> str:
    return "-" if seconds is None else f"{seconds:.2f}s"


def print_timings(backends: dict[str, tuple[dict[str, str], dict[str, float], float]],
                  count: int) -> None:
    reasoning = backends["reasoning"][1]
    sympy_ = backends["sympy"][1]
    rows = []
    for test in reasoning.keys() | sympy_.keys():
        times = [time for time in (reasoning.get(test), sympy_.get(test))
                 if time is not None]
        rows.append((max(times), test, reasoning.get(test), sympy_.get(test)))
    rows.sort(reverse=True)
    print(f"\nslowest {min(count, len(rows))} tests:")
    print(f"  {'test':<50} {'reasoning':>10} {'sympy':>10} {'delta':>9}")
    for _, test, reasoning_time, sympy_time in rows[:count]:
        delta = ("" if reasoning_time is None or sympy_time is None
                 else f"{sympy_time - reasoning_time:+.2f}s")
        print(f"  {test:<50} {format_time(reasoning_time):>10} "
              f"{format_time(sympy_time):>10} {delta:>9}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[],
                        help="extra arguments forwarded to pytest")
    parser.add_argument("--timings", type=int, default=10,
                        help="number of slowest tests to show; 0 disables")
    parser.add_argument("--verbose", action="store_true",
                        help="list each backend's failing tests")
    args = parser.parse_args()

    if REASONING_BINDING not in args.suite.read_text():
        raise SystemExit(f"{args.suite} does not bind satask from reasoning")

    backends = {name: run_backend(name, args.suite, args.pytest_args)
                for name in BACKENDS}

    for name, (outcomes, timings, wall) in backends.items():
        print(f"{name}: {len(outcomes)} tests: {summarize(outcomes)} "
              f"(wall {wall:.2f}s, tests {sum(timings.values()):.2f}s)")
        if args.verbose:
            for test, outcome in sorted(outcomes.items()):
                if outcome in ("FAILED", "ERROR"):
                    print(f"  {outcome} {test}")

    if args.timings:
        print_timings(backends, args.timings)

    reasoning, sympy_ = backends["reasoning"][0], backends["sympy"][0]
    mismatches = [(test, reasoning.get(test), sympy_.get(test))
                  for test in sorted(reasoning.keys() | sympy_.keys())
                  if reasoning.get(test) != sympy_.get(test)]
    if mismatches:
        print(f"\n{len(mismatches)} outcome mismatches:")
        for test, reasoning_outcome, sympy_outcome in mismatches:
            print(f"  {test}: reasoning={reasoning_outcome} sympy={sympy_outcome}")
    else:
        print("\nNo outcome mismatches.")
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
