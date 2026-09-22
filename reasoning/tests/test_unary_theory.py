from __future__ import annotations

import copy

import pytest
from sympy import MatrixSymbol, Q, symbols

from reasoning.clauses import assert_formula, compile_formula
from reasoning.engine import ReasoningEngine
from reasoning.satask import (
    get_all_relevant_facts, get_facts_and_subjects, satask,
)
from reasoning.sympy_adapter import SympyAdapter, select_known_template, to_formula
from reasoning.unary_adapter import build_unary_theory

x, y = symbols('x y')


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


def test_theory_mapping_matches_materialized_encoding() -> None:
    matrix = MatrixSymbol('A', 2, 2)
    prop = to_formula(Q.real(x) & Q.invertible(matrix))
    assump = to_formula(Q.positive(x) & Q.square(matrix))
    db, subjects = get_facts_and_subjects(prop, assump)
    assert_formula(assump, db)
    theory = build_unary_theory(db, subjects)
    assert theory is not None

    # `add_known_facts` materializes every template predicate for every
    # subject; the copy keeps the variable ids of the atoms already allocated
    # by discovery, so the theory's variables can be compared directly.
    materialized = copy.deepcopy(db)
    SympyAdapter().add_known_facts(subjects, materialized)

    ordered = sorted(subjects, key=str)
    selected = select_known_template(ordered)
    assert selected is not None
    assert len(theory._subject_variables) == len(ordered)
    for subject, mapping in zip(ordered, theory._subject_variables):
        assert mapping
        expected = {
            index: materialized.encoding[predicate(subject)]
            for index, predicate in enumerate(selected.predicates, start=1)
            if predicate(subject) in db.encoding
        }
        assert mapping == expected
        assert set(mapping.values()) == {
            materialized.encoding[predicate(subject)]
            for predicate in selected.predicates
            if predicate(subject) in db.encoding
        }


def test_unary_theory_shrinks_the_clause_database() -> None:
    xs = symbols('x:10')
    prop = to_formula(Q.integer(sum(xs)))
    assump = to_formula(Q.integer(xs[0]))
    default = get_all_relevant_facts(prop, assump)
    without_known = get_all_relevant_facts(prop, assump, use_known_facts=False)
    assert len(default.data) - len(without_known.data) == 11 * 81
    assert satask(Q.integer(sum(xs)), Q.integer(xs[0]),
                  use_unary_theory=True) is None
