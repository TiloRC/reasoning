"""Run with: python -m benchmarks.satask [--repeat 15].

Reports warm median timings in milliseconds. Timings are illustrative, not a
performance assertion. The phase timings expose conversion, discovery/encoding,
query encoding, and solving separately.
"""
import argparse
import json
import statistics
from time import perf_counter
from typing import Any

from sympy import MatrixSymbol, Q, symbols

from reasoning.clauses import assert_formula, compile_formula
from reasoning.engine import ReasoningEngine
from reasoning.satask import get_all_relevant_facts, get_facts_and_subjects
from reasoning.sympy_adapter import to_formula
from reasoning.sympy_types import SymPyExpr
from reasoning.unary_adapter import build_unary_theory


def cases() -> dict[str, tuple[SymPyExpr, SymPyExpr]]:
    x, y = symbols('x y')
    xs = symbols('x:10')
    matrix = MatrixSymbol('A', 2, 2)
    return {
        'simple': (Q.real(x), Q.positive(x)),
        'nested': (Q.zero(x*(x+y)), Q.positive(x) & Q.positive(y)),
        'sum10': (Q.integer(sum(xs)), Q.integer(xs[0])),
        'matrix': (Q.invertible(matrix), Q.fullrank(matrix) & Q.square(matrix)),
        'contradiction': (Q.real(x), Q.real(x) & ~Q.real(x)),
    }


def measure(proposition: SymPyExpr, assumptions: SymPyExpr,
            unary: bool = False) -> dict[str, Any]:
    start = perf_counter()
    prop, assump = to_formula(proposition), to_formula(assumptions)
    converted = perf_counter()
    known_subjects: set[Any] | None = None
    if unary:
        db, known_subjects = get_facts_and_subjects(prop, assump)
    else:
        db = get_all_relevant_facts(prop, assump)
    discovered = perf_counter()
    assert_formula(assump, db)
    query = compile_formula(prop, db)
    encoded = perf_counter()
    theories = []
    if known_subjects is not None:
        theory = build_unary_theory(db, known_subjects)
        if theory is not None:
            theories.append(theory)
    theory_built = perf_counter()
    result: bool | str | None
    try:
        result = ReasoningEngine(db, theory_solvers=theories).ask(query)
    except ValueError:
        result = 'inconsistent'
    solved = perf_counter()
    return {
        'conversion_ms': (converted-start)*1000,
        'discovery_encoding_ms': (discovered-converted)*1000,
        'query_encoding_ms': (encoded-discovered)*1000,
        'theory_build_ms': (theory_built-encoded)*1000,
        'solve_ms': (solved-theory_built)*1000,
        'total_ms': (solved-start)*1000,
        'clauses': len(db.data), 'variables': len(db.variables), 'result': result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeat', type=int, default=15)
    parser.add_argument('--unary', action='store_true',
                        help="use the unary known-fact theory instead of "
                             "materializing the known-fact clauses")
    args = parser.parse_args()
    output: dict[str, dict[str, Any]] = {}
    for name, inputs in cases().items():
        measure(*inputs, unary=args.unary)
        runs = [measure(*inputs, unary=args.unary) for _ in range(args.repeat)]
        output[name] = {key: statistics.median(run[key] for run in runs)
                        if key.endswith('_ms') else runs[-1][key] for key in runs[-1]}
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
