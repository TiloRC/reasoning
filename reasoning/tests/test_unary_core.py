"""Synthetic tests for the SymPy-free unary known-fact theory.

The theory is a pure-Python module, so these tests build tiny CNF templates by
hand, drive the solver and engine directly, and never import SymPy.
"""
from __future__ import annotations

from reasoning.engine import ReasoningEngine
from reasoning.solver import IpasirStatus, SATSolver
from reasoning.unary_theory import CompiledTemplate, UnaryTheory


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
