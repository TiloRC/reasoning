"""SymPy-facing entry points for the independent SAT reasoning core."""
from __future__ import annotations

from .clauses import ClauseDB, assert_formula, compile_formula, iter_atoms
from .discovery import discover_facts, relevant_subjects
from .engine import ReasoningEngine
from .sympy_adapter import SympyAdapter, to_formula


def _iteration_limit(iterations):
    # Keep accepting the former oo default at the public boundary.
    from sympy import oo
    if iterations is None or iterations == oo:
        return None
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 0:
        raise ValueError("iterations must be a nonnegative integer or None")
    return iterations


def satask(proposition, assumptions=True, use_known_facts=True, iterations=None,
           early_return=False):
    """Return True, False, or None according to the supplied assumptions.

    Expression facts are discovered breadth-first, processing each expression
    once. ``iterations=None`` runs until no unseen expression remains; zero
    disables expression-fact discovery. Known predicate facts are controlled
    independently by ``use_known_facts``.

    By default inconsistent assumptions raise ValueError. ``early_return``
    permits an answer from unit propagation while trusting consistency.
    """
    proposition = to_formula(proposition)
    assumptions = to_formula(assumptions)
    db = get_all_relevant_facts(proposition, assumptions, use_known_facts, iterations)
    assert_formula(assumptions, db)
    query = compile_formula(proposition, db)
    return ReasoningEngine(db).ask(query, early_return=early_return)


def extract_predargs(proposition, assumptions=None):
    """Find subjects connected to the proposition through assumption symbols."""
    return relevant_subjects(to_formula(proposition),
                             to_formula(True if assumptions is None else assumptions),
                             SympyAdapter())


def find_symbols(proposition):
    adapter = SympyAdapter()
    return set().union(*(adapter.relevance_keys(atom)
                         for atom in iter_atoms(to_formula(proposition))))


def get_relevant_clsfacts(exprs, relevant_facts=None):
    """Encode one discovery round; return new subjects and a ClauseDB."""
    adapter = SympyAdapter()
    db = ClauseDB() if relevant_facts is None else relevant_facts
    following = set()
    for expr in exprs:
        for fact in adapter.facts_for(expr):
            for atom in iter_atoms(fact):
                following.update(adapter.fact_subjects(atom))
            assert_formula(fact, db)
    return following - set(exprs), db


def get_all_relevant_facts(proposition, assumptions, use_known_facts=True,
                           iterations=None):
    """Build integer clauses for expression and known predicate facts."""
    adapter = SympyAdapter()
    subjects = relevant_subjects(to_formula(proposition), to_formula(assumptions), adapter)
    db = ClauseDB()
    visited = discover_facts(subjects, db, adapter, _iteration_limit(iterations))
    if use_known_facts:
        adapter.add_known_facts(subjects | visited, db)
    return db
