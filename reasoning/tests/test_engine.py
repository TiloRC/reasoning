from itertools import product
import random

from reasoning.engine import ReasoningEngine
from reasoning.solver import IpasirStatus, SATSolver


def test_engine_answers_both_polarities_and_unknown() -> None:
    engine = ReasoningEngine([{1, -2}, {2}])
    assert engine.ask(1) is True
    assert ReasoningEngine([{1, -2}, {2}]).ask(-1) is False
    assert ReasoningEngine([{1, 2}]).ask(1) is None


def test_engine_constants_and_propagation() -> None:
    engine = ReasoningEngine([{1}, {-1, 2}])
    assert engine.ask(True) is True
    assert ReasoningEngine([{1}, {-1, 2}]).ask(False) is False
    assert engine.fixed(2) is True
    assert engine.ask(2, early_return=True) is True


def test_engine_reuses_its_base_model_for_repeated_queries() -> None:
    engine = ReasoningEngine([{1}])
    assert [engine.ask(query) for query in (1, -1, 2, -2, True, False, 1)] == [
        True, False, None, None, True, False, True,
    ]


def test_engine_rejects_inconsistent_facts() -> None:
    try:
        ReasoningEngine([{1}, {-1}]).ask(1)
    except ValueError as error:
        assert str(error) == "Inconsistent assumptions"
    else:
        raise AssertionError("inconsistent facts were accepted")


def test_engine_rejects_root_propagation_conflicts_immediately() -> None:
    try:
        ReasoningEngine([{1}, {-1}])
    except ValueError as error:
        assert str(error) == "Inconsistent assumptions"
    else:
        raise AssertionError("root conflict was accepted")


def test_early_return_can_answer_propagation_before_consistency_check() -> None:
    engine = ReasoningEngine([{1}, {2, 3}, {-2, 3}, {2, -3}, {-2, -3}])
    assert engine.ask(1, early_return=True) is True
    try:
        engine.ask(1)
    except ValueError as error:
        assert str(error) == "Inconsistent assumptions"
    else:
        raise AssertionError("inconsistent facts were accepted")


def test_solver_assumptions_are_temporary() -> None:
    solver = SATSolver([{1, 2}, {-1, -2}], {1, 2})
    solver.assume(1)
    assert solver.solve() is IpasirStatus.SATISFIABLE
    assert solver.val(2) == -2
    assert solver.solve() is IpasirStatus.SATISFIABLE


def test_unknown_unallocated_literal_does_not_become_an_assumption() -> None:
    assert ReasoningEngine([{1, 2}]).ask(99) is None


def test_zero_is_not_a_clause_or_query_literal() -> None:
    try:
        ReasoningEngine([{0}])
    except ValueError as error:
        assert str(error) == "0 is not a CNF literal"
    else:
        raise AssertionError("zero clause literal was accepted")


def test_repeated_queries_and_random_cnf_match_brute_force() -> None:
    randomizer = random.Random(729)
    for _ in range(100):
        clauses = [
            {randomizer.choice((-1, 1)) * randomizer.randint(1, 3)
             for _ in range(randomizer.randint(1, 3))}
            for _ in range(randomizer.randint(1, 8))
        ]
        models = [
            assignment for assignment in product((False, True), repeat=3)
            if all(any(assignment[abs(literal) - 1] == (literal > 0)
                       for literal in clause) for clause in clauses)
        ]
        if not models:
            try:
                ReasoningEngine(clauses).ask(1)
            except ValueError:
                continue
            raise AssertionError("unsatisfiable CNF was accepted")
        engine = ReasoningEngine(clauses)
        for literal in (1, -1, 2, -2, 3, -3):
            expected = [assignment[abs(literal) - 1] == (literal > 0)
                        for assignment in models]
            answer = False if not any(expected) else True if all(expected) else None
            assert engine.ask(literal) is answer
