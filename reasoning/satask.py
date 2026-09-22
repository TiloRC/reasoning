"""SymPy-facing entry points for the independent SAT reasoning core."""
from __future__ import annotations

from typing import Iterable

from .clauses import ClauseDB, assert_formula, compile_formula, iter_atoms
from .discovery import discover_facts, relevant_subjects
from .engine import ReasoningEngine
from .lra_adapter import build_lra_theory
from .sympy_adapter import (
    NormalizedFormula, SympyAdapter, normalize, to_formula,
)
from .sympy_types import SymPyExpr
from .theory import TheorySolver
from .unary_adapter import build_unary_theory


def _iteration_limit(iterations: object) -> int | None:
    # Keep accepting the former oo default at the public boundary.
    from sympy import oo
    if iterations is None or iterations == oo:
        return None
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 0:
        raise ValueError("iterations must be a nonnegative integer or None")
    return iterations


def satask(proposition: SymPyExpr | bool, assumptions: SymPyExpr | bool = True,
           use_known_facts: bool = True, iterations: object = None,
           early_return: bool = False,
           use_lra_theory: bool = False,
           use_unary_theory: bool = True) -> bool | None:
    """Return True, False, or None according to the supplied assumptions.

    Expression facts are discovered breadth-first, processing each expression
    once. ``iterations=None`` runs until no unseen expression remains; zero
    disables expression-fact discovery. Known predicate facts are controlled
    independently by ``use_known_facts``.

    By default inconsistent assumptions raise ValueError. ``early_return``
    permits an answer from unit propagation while trusting consistency.

    ``use_lra_theory`` additionally interprets the linear relations among the
    discovered ``Q.eq``/``Q.gt``/``Q.lt``/``Q.ge``/``Q.le`` atoms and lets the
    linear arithmetic solver prune inconsistent assignments. It is opt-in
    because the theory changes the search and only helps formulas whose
    Boolean structure leaves relations undecided.

    ``use_unary_theory`` (the default) keeps the per-subject known-fact
    clauses out of the clause database and enforces those facts through a
    unary theory instead. Pass ``False`` to materialize the known-fact
    templates as clauses; both encodings answer the same queries.

    Inputs are normalized by :func:`~reasoning.sympy_adapter.normalize`:
    Python Booleans and legacy CNF objects are accepted, any other non-SymPy
    value raises TypeError, and SymPy ``Q`` applications become local
    :mod:`reasoning.predicates` applications whose arguments are the original
    SymPy expressions.
    """
    prop_formula: NormalizedFormula = normalize(proposition)
    assump_formula: NormalizedFormula = normalize(assumptions)
    known_subjects: set[object] | None = None
    if use_unary_theory and use_known_facts:
        db, known_subjects = get_facts_and_subjects(
            prop_formula, assump_formula, iterations)
    else:
        db = get_all_relevant_facts(
            prop_formula, assump_formula, use_known_facts, iterations)
    assert_formula(assump_formula, db)
    query = compile_formula(prop_formula, db)

    theories: list[TheorySolver] = []
    if use_lra_theory:
        lra, conflicts = build_lra_theory(db)
        for conflict in conflicts:
            db.add_clause(conflict)
        if lra is not None:
            theories.append(lra)
    if known_subjects is not None:
        unary = build_unary_theory(db, known_subjects)
        if unary is not None:
            theories.append(unary)

    engine = ReasoningEngine(db, theory_solvers=theories)
    return engine.ask(query, early_return=early_return)


def extract_predargs(proposition: object,
                     assumptions: object = None) -> set[object]:
    """Find subjects connected to the proposition through assumption symbols."""
    return relevant_subjects(to_formula(proposition),
                             to_formula(True if assumptions is None else assumptions),
                             SympyAdapter())


def find_symbols(proposition: object) -> set[object]:
    adapter = SympyAdapter()
    symbols: set[object] = set()
    for atom in iter_atoms(to_formula(proposition)):
        symbols.update(adapter.relevance_keys(atom))
    return symbols


def get_relevant_clsfacts(exprs: Iterable[object],
                          relevant_facts: ClauseDB | None = None,
                          ) -> tuple[set[object], ClauseDB]:
    """Encode one discovery round; return new subjects and a ClauseDB."""
    adapter = SympyAdapter()
    db = ClauseDB() if relevant_facts is None else relevant_facts
    following: set[object] = set()
    for expr in exprs:
        for fact in adapter.facts_for(expr):
            for atom in iter_atoms(fact):
                following.update(adapter.fact_subjects(atom))
            assert_formula(fact, db)
    return following - set(exprs), db


def get_facts_and_subjects(proposition: object, assumptions: object,
                           iterations: object = None,
                           ) -> tuple[ClauseDB, set[object]]:
    """Build the handler-fact database and report the known-fact subjects.

    This is the ``use_known_facts=False`` half of
    :func:`get_all_relevant_facts`, kept public so :func:`satask` can attach
    the unary theory instead of materializing the known-fact templates.
    """
    adapter = SympyAdapter()
    subjects = relevant_subjects(
        to_formula(proposition), to_formula(assumptions), adapter)
    db = ClauseDB()
    visited = discover_facts(subjects, db, adapter, _iteration_limit(iterations))
    return db, subjects | visited


def get_all_relevant_facts(proposition: object, assumptions: object,
                           use_known_facts: bool = True,
                           iterations: object = None) -> ClauseDB:
    """Build integer clauses for expression and known predicate facts."""
    db, known_subjects = get_facts_and_subjects(
        proposition, assumptions, iterations)
    if use_known_facts:
        SympyAdapter().add_known_facts(known_subjects, db)
    return db
