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
from reasoning.satask import get_all_relevant_facts
from reasoning.sympy_adapter import to_formula
from reasoning.sympy_types import SymPyExpr


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


def measure(proposition: SymPyExpr, assumptions: SymPyExpr) -> dict[str, Any]:
    start = perf_counter()
    prop, assump = to_formula(proposition), to_formula(assumptions)
    converted = perf_counter()
    db = get_all_relevant_facts(prop, assump)
    discovered = perf_counter()
    assert_formula(assump, db)
    query = compile_formula(prop, db)
    encoded = perf_counter()
    result: bool | str | None
    try:
        result = ReasoningEngine(db).ask(query)
    except ValueError:
        result = 'inconsistent'
    solved = perf_counter()
    return {
        'conversion_ms': (converted-start)*1000,
        'discovery_encoding_ms': (discovered-converted)*1000,
        'query_encoding_ms': (encoded-discovered)*1000,
        'solve_ms': (solved-encoded)*1000,
        'total_ms': (solved-start)*1000,
        'clauses': len(db.data), 'variables': len(db.variables), 'result': result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeat', type=int, default=15)
    args = parser.parse_args()
    output: dict[str, dict[str, Any]] = {}
    for name, inputs in cases().items():
        measure(*inputs)
        runs = [measure(*inputs) for _ in range(args.repeat)]
        output[name] = {key: statistics.median(run[key] for run in runs)
                        if key.endswith('_ms') else runs[-1][key] for key in runs[-1]}
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
