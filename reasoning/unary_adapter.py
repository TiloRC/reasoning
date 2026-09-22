"""Build the unary known-fact theory for a clause database.

The SymPy known-fact templates are selected exactly the way
:meth:`~reasoning.sympy_adapter.SympyAdapter.add_known_facts` selects them:
the kind of the subjects decides whether the number template, the matrix
template, or both apply.  The difference is that no clauses are added; the
returned theory enforces the template through conflicts instead.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from sympy.core.kind import NumberKind, UndefinedKind
from sympy.matrices.kind import MatrixKind

from .clauses import ClauseDB
from .predicates import Q
from .sympy_adapter import _known_template
from .sympy_types import SymPyExpr
from .unary_theory import CompiledTemplate, UnaryTheory


@lru_cache(maxsize=3)
def _compiled(numbers: bool, matrices: bool) -> CompiledTemplate:
    """Compile a known-fact template once per process."""
    predicates, clauses = _known_template(numbers, matrices)
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
    numbers = any(expr.kind in (NumberKind, UndefinedKind)
                  for expr in subject_list)
    matrices = any(expr.kind == MatrixKind(NumberKind)
                   for expr in subject_list)
    if not numbers and not matrices:
        return None

    predicates, _clauses = _known_template(numbers, matrices)
    template = _compiled(numbers, matrices)
    mappings: list[dict[int, int]] = []
    for subject in subject_list:
        mapping: dict[int, int] = {}
        for index, predicate in enumerate(predicates, start=1):
            variable = db.encoding.get(Q.of(predicate.name)(subject))
            if variable is not None:
                mapping[index] = variable
        mappings.append(mapping)
    return UnaryTheory(template, mappings, enable_propagation)


__all__ = ["build_unary_theory"]
