"""Warm-cache timings with fixed queries and explicit answer contracts.

Inputs are built and answers checked outside timing. Mutable databases/engines
are recreated for each call; Solve additionally disables timeit's inner loop
and warmup so its engine has not already answered the query. See benchmarks/README.md.
"""
from reasoning.clauses import assert_formula, compile_formula
from reasoning.engine import ReasoningEngine
from reasoning.satask import get_all_relevant_facts, satask
from reasoning.sympy_adapter import normalize

from ._workloads import (
    CONSISTENT_NAMES, NAMES, VERSION, answer, answer_code, case, check, sum_case,
)


def _database(workload):
    prop, assumptions = normalize(workload.proposition), normalize(workload.assumptions)
    db = get_all_relevant_facts(prop, assumptions)
    assert_formula(assumptions, db)
    return db, compile_formula(prop, db)


class Pipeline:
    params = NAMES
    param_names = ["case"]
    version = VERSION

    def setup(self, name):
        self.workload = case(name)
        check(answer(lambda: satask(self.workload.proposition, self.workload.assumptions)),
              self.workload.expected)

    def time_satask(self, name):
        # Keep the result check in the timed path too: a behavior change on a
        # repeated call must not produce a misleading successful measurement.
        check(answer(lambda: satask(self.workload.proposition, self.workload.assumptions)),
              self.workload.expected)


class Phases:
    params = CONSISTENT_NAMES
    param_names = ["case"]
    version = VERSION

    def setup(self, name):
        self.workload = case(name)
        self.prop = normalize(self.workload.proposition)
        self.assumptions = normalize(self.workload.assumptions)
        self.db, self.query = _database(self.workload)
        check(ReasoningEngine(self.db).ask(self.query), self.workload.expected)

    def time_discovery_encoding(self, name):
        db = get_all_relevant_facts(self.prop, self.assumptions)
        assert_formula(self.assumptions, db)
        compile_formula(self.prop, db)

    def time_engine_ctor(self, name):
        ReasoningEngine(self.db)

    def track_clauses(self, name):
        return len(self.db.data)

    def track_variables(self, name):
        return len(self.db.variables)


class Solve:
    params = CONSISTENT_NAMES
    param_names = ["case"]
    version = VERSION
    number = 1
    warmup_time = 0
    repeat = 10

    def setup(self, name):
        self.workload = case(name)
        db, self.query = _database(self.workload)
        check(ReasoningEngine(db).ask(self.query), self.workload.expected)
        self.engine = ReasoningEngine(db)

    def time_solve(self, name):
        check(self.engine.ask(self.query), self.workload.expected)


class Outcomes:
    """Record actual behavior even when a timing's answer contract fails."""
    params = NAMES
    param_names = ["case"]
    version = VERSION

    def setup(self, name):
        self.workload = case(name)

    def track_answer(self, name):
        return answer_code(answer(lambda: satask(self.workload.proposition,
                                                self.workload.assumptions)))


class SumScaling:
    params = [10, 20, 40, 80]
    param_names = ["arity"]
    version = VERSION

    def setup(self, arity):
        self.workload = sum_case(arity)
        check(answer(lambda: satask(self.workload.proposition, self.workload.assumptions)),
              self.workload.expected)
        self.db, _ = _database(self.workload)

    def time_satask(self, arity):
        check(answer(lambda: satask(self.workload.proposition, self.workload.assumptions)),
              self.workload.expected)

    def track_clauses(self, arity):
        return len(self.db.data)

    def track_variables(self, arity):
        return len(self.db.variables)
