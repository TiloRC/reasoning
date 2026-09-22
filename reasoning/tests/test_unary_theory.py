from __future__ import annotations

import pytest
from sympy import MatrixSymbol, Q, symbols

from reasoning.clauses import assert_formula, compile_formula
from reasoning.engine import ReasoningEngine
from reasoning.satask import (
    get_all_relevant_facts, get_facts_and_subjects, satask,
)
from reasoning.solver import IpasirStatus, SATSolver
from reasoning.sympy_adapter import to_formula
from reasoning.unary_adapter import build_unary_theory
from reasoning.unary_theory import CompiledTemplate, UnaryTheory

x, y = symbols('x y')


def test_compiled_template_model_counts() -> None:
    number = CompiledTemplate(2, [(-1, 2)])
    assert number.model_counts() == [3]
    assert number.check([(1, True), (2, True)]) == (True, [])
    consistent, core = number.check([(1, True), (2, False)])
    assert consistent is False
    assert core == [(1, True), (2, False)]


def test_compiled_template_does_not_merge_independent_blocks() -> None:
    # Clauses over {1, 2} and {3, 4} are two components, never one product.
    template = CompiledTemplate(4, [(1, -2), (3, -4)])
    assert template.model_counts() == [3, 3]
    assert template.component_of(1) == template.component_of(2)
    assert template.component_of(1) != template.component_of(3)


def test_theory_propagates_forced_literals_with_explanations() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    theory.assert_lit(1)
    assert theory.propagate() == [(2, [-1])]
    theory.assert_lit(2)
    assert theory.propagate() == []
    assert theory.check() == (True, [])


def test_theory_propagation_reports_a_conflict() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    theory.assert_lit(1)
    theory.assert_lit(-2)
    implied = theory.propagate()
    assert implied == [(-1, [2])]


def test_check_only_theory_still_finds_the_conflict() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}],
                         enable_propagation=False)
    theory.assert_lit(1)
    theory.assert_lit(-2)
    assert theory.propagate() == []
    assert theory.check() == (False, [-1, 2])


def test_theory_levels_undo_assignments() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    theory.assert_lit(1)
    theory.push_level()
    theory.assert_lit(-2)
    assert theory.check() == (False, [-1, 2])
    theory.pop_level()
    assert theory.check() == (True, [])
    assert theory.propagate() == [(2, [-1])]


def test_solver_uses_theory_propagation() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    solver = SATSolver([{1}], {1, 2}, set(), theory_solvers=[theory])
    assert solver.solve() is IpasirStatus.SATISFIABLE
    assert solver.val(2) == 2


def test_solver_reports_a_propagation_conflict() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    solver = SATSolver([{1}, {-2}], {1, 2}, set(), theory_solvers=[theory])
    assert solver.solve() is IpasirStatus.UNSATISFIABLE


def test_engine_answers_with_the_unary_theory() -> None:
    theory = UnaryTheory(CompiledTemplate(2, [(-1, 2)]), [{1: 1, 2: 2}])
    engine = ReasoningEngine([{1, 2}], theory_solvers=[theory])
    assert engine.ask(2) is True
    assert engine.ask(1) is None


def test_uses_number_template_for_number_subjects() -> None:
    prop, assump = to_formula(Q.real(x)), to_formula(Q.positive(x))
    db, subjects = get_facts_and_subjects(prop, assump)
    theory = build_unary_theory(db, subjects)
    assert theory is not None
    assert theory.template.model_counts() == [64]


def test_combined_template_keeps_components_separate() -> None:
    matrix = MatrixSymbol('A', 2, 2)
    prop = to_formula(Q.real(x) & Q.invertible(matrix))
    db, subjects = get_facts_and_subjects(prop, to_formula(True))
    theory = build_unary_theory(db, subjects)
    assert theory is not None
    assert theory.template.model_counts() == [64, 400]


def test_no_theory_without_known_facts() -> None:
    prop, assump = to_formula(Q.real(x)), to_formula(Q.positive(x))
    db, subjects = get_facts_and_subjects(prop, assump)
    with_facts = get_all_relevant_facts(prop, assump)
    assert len(with_facts.data) > len(db.data)
    assert build_unary_theory(db, set()) is None


@pytest.mark.parametrize("proposition,assumptions,expected", [
    (Q.real(x), Q.positive(x), True),
    (Q.zero(x), Q.positive(x), False),
    (Q.positive(x), Q.real(x), None),
    (Q.integer(x), Q.even(x) | Q.odd(x), True),
    (Q.nonzero(x), Q.negative(x) | Q.positive(x), True),
    (Q.zero(x), Q.nonnegative(x) & Q.nonpositive(x), True),
    (Q.prime(x), Q.composite(x), False),
    (Q.zero(x*(x + y)), Q.positive(x) & Q.positive(y), False),
])
def test_answers_match_the_default_path(proposition: object,
                                        assumptions: object,
                                        expected: bool | None) -> None:
    assert satask(proposition, assumptions) is expected
    assert satask(proposition, assumptions, use_unary_theory=True) is expected


def test_matches_the_default_path_for_matrix_subjects() -> None:
    matrix = MatrixSymbol('A', 2, 2)
    proposition = Q.diagonal(matrix)
    assumptions = Q.lower_triangular(matrix) & Q.upper_triangular(matrix)
    assert satask(proposition, assumptions) is True
    assert satask(proposition, assumptions, use_unary_theory=True) is True


def test_theory_builds_only_materialized_predicates() -> None:
    prop, assump = to_formula(Q.real(x)), to_formula(Q.positive(x))
    db, subjects = get_facts_and_subjects(prop, assump)
    assert_formula(assump, db)
    query = compile_formula(prop, db)
    theory = build_unary_theory(db, subjects)
    assert theory is not None
    engine = ReasoningEngine(db, theory_solvers=[theory])
    assert engine.ask(query) is True
    assert len(db.data) == 1
    assert len(db.variables) == 2


def test_unary_theory_shrinks_the_clause_database() -> None:
    xs = symbols('x:10')
    prop = to_formula(Q.integer(sum(xs)))
    assump = to_formula(Q.integer(xs[0]))
    default = get_all_relevant_facts(prop, assump)
    without_known = get_all_relevant_facts(prop, assump, use_known_facts=False)
    assert len(default.data) - len(without_known.data) == 11 * 81
    assert satask(Q.integer(sum(xs)), Q.integer(xs[0]),
                  use_unary_theory=True) is None
