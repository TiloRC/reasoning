"""Fixed workloads and answer contracts; independent of validation test flow."""
from collections.abc import Callable
from dataclasses import dataclass

from sympy import MatrixSymbol, Q, symbols

# Bump when inputs, expected answers, or cache policy change. This also versions
# timings whose function source does not include the workload definitions.
VERSION = "1"
NAMES = ("simple", "nested", "sum10", "matrix", "contradiction",
         "upstream_integer", "upstream_zero", "upstream_unknown")
CONSISTENT_NAMES = tuple(name for name in NAMES if name != "contradiction")


@dataclass(frozen=True)
class Case:
    proposition: object
    assumptions: object
    expected: bool | str | None


def sum_case(arity: int) -> Case:
    xs = symbols(f"x:{arity}")
    return Case(Q.integer(sum(xs)), Q.integer(xs[0]), None)


def case(name: str) -> Case:
    x, y = symbols("x y")
    matrix = MatrixSymbol("A", 2, 2)
    # First five inputs match benchmarks.satask.cases(). The remaining cases
    # are individual assertions from pinned SymPy test_query.py's test_integer
    # and test_zero. Extracting assertions fixes the workload even when an
    # earlier assertion in the upstream test starts passing or failing.
    return {
        "simple": Case(Q.real(x), Q.positive(x), True),
        "nested": Case(Q.zero(x*(x+y)), Q.positive(x) & Q.positive(y), False),
        "sum10": sum_case(10),
        "matrix": Case(Q.invertible(matrix), Q.fullrank(matrix) & Q.square(matrix), True),
        "contradiction": Case(Q.real(x), Q.real(x) & ~Q.real(x), "inconsistent"),
        "upstream_integer": Case(Q.integer(x), Q.even(x) | Q.odd(x), True),
        "upstream_zero": Case(Q.zero(x), Q.negative(x) | Q.positive(x), False),
        "upstream_unknown": Case(Q.integer(x), ~Q.positive(x), None),
    }[name]


def answer(call: Callable[[], bool | None]) -> bool | str | None:
    try:
        return call()
    except ValueError as error:
        if str(error) != "Inconsistent assumptions":
            raise
        return "inconsistent"


def check(actual: bool | str | None, expected: bool | str | None) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise AssertionError(f"answer changed: expected {expected!r}, got {actual!r}")


def answer_code(value: bool | str | None) -> int:
    """-1 unknown, 0 false, 1 true, 2 inconsistent; never a speed score."""
    return {None: -1, False: 0, True: 1, "inconsistent": 2}[value]
