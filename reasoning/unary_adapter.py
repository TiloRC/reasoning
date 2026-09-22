"""Build the unary known-fact theory for a clause database.

The template selection is shared with
:meth:`~reasoning.sympy_adapter.SympyAdapter.add_known_facts` through
:func:`~reasoning.sympy_adapter.select_known_template`: the kinds of the
subjects decide whether the number template, the matrix template, or both
apply.  The difference is that no clauses are added; the returned theory
enforces the template through conflicts instead.

This module is only the mapping layer: it compiles the selected template once
per process and maps the template predicate atoms that the clause database
already materialized to their solver variables.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from .clauses import ClauseDB
from .predicates import Predicate, Q
from .sympy_adapter import select_known_template
from .sympy_types import SymPyExpr
from .unary_theory import CompiledTemplate, UnaryTheory


@lru_cache(maxsize=4)
def _compiled(predicates: tuple[Predicate, ...],
              clauses: tuple[tuple[int, ...], ...]) -> CompiledTemplate:
    """Compile a selected template once per process."""
    return CompiledTemplate(len(predicates), clauses)


def build_unary_theory(db: ClauseDB,
                       subjects: Iterable[SymPyExpr],
                       enable_propagation: bool = True) -> UnaryTheory | None:
    """Return a theory enforcing the known facts of *subjects*, or None.

    *subjects* is the same set :meth:`SympyAdapter.add_known_facts` receives,
    so the template selection matches the materialized encoding.  Predicates
    that the clause database never allocated simply stay unconstrained.
    ``enable_propagation`` turns the theory's ``propagate`` method into a
    no-op, which leaves a check-only theory for comparison.
    """
    subject_list = list(subjects)
    # The subjects arrive as a set, so fix an order; the theory's propagation
    # order otherwise follows Python's per-process hash randomization.
    subject_list.sort(key=str)
    selected = select_known_template(subject_list)
    if selected is None:
        return None

    template = _compiled(tuple(selected.predicates), selected.clauses)
    mappings: list[dict[int, int]] = []
    for subject in subject_list:
        mapping: dict[int, int] = {}
        for index, predicate in enumerate(selected.predicates, start=1):
            variable = db.encoding.get(Q.of(predicate.name)(subject))
            if variable is not None:
                mapping[index] = variable
        mappings.append(mapping)
    return UnaryTheory(template, mappings, enable_propagation)


__all__ = ["build_unary_theory"]
