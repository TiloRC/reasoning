"""Bridge SymPy's old symbol assumptions into local predicate premises.

A symbol created with old-assumption keywords carries facts that are only
visible through the old assumptions API, for example::

    x = Symbol("x", positive=True)

The reasoning core deliberately never reads those attributes (see
``tools/check_old_assumptions.py``).  Instead this module harvests the
*declared* facts through the public new-assumptions entry point
:func:`sympy.assumptions.ask.ask`, which is allowed to consult them, and
returns them as plain ``(predicate name, truth value)`` pairs.  The adapter
asserts the pairs as local premises, so the core keeps operating on its own
predicate vocabulary.

Only the symbol's own declared assumptions are consulted: the upstream query
runs with an empty context, so neither ``global_assumptions`` nor the
assumptions passed to :func:`reasoning.satask.satask` leak into the harvest.
Results are cached per symbol; the cache is keyed by the symbol object, whose
equality and hash include the declared assumptions.

Matrix symbols are skipped.  Their old-assumption answers describe the fact
that a matrix is not a scalar number rather than a declared fact, and matrix
knowledge is assembled by :mod:`reasoning.matrixfacts` instead.
"""
from __future__ import annotations

from sympy import Q as SymPyQ
from sympy.assumptions.ask import ask
from sympy.core.symbol import Symbol
from sympy.matrices.expressions.matexpr import MatrixSymbol

# SymPy's scalar old-assumption vocabulary, mirrored by the checker's
# ``ASSUMPTION_NAMES``.  These are exactly the keywords a Symbol accepts and
# the predicates whose declared truth values can be harvested.
DECLARED_ASSUMPTIONS = (
    "algebraic", "antihermitian", "commutative", "complex", "composite",
    "even", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero", "extended_positive",
    "extended_real", "finite", "hermitian", "imaginary", "infinite",
    "integer", "irrational", "negative", "nonnegative", "nonpositive",
    "nonzero", "odd", "positive", "prime", "rational", "real",
    "transcendental", "zero",
)

_CACHE: dict[Symbol, tuple[tuple[str, bool], ...]] = {}


def declared_assumptions(symbol: Symbol) -> tuple[tuple[str, bool], ...]:
    """Return the declared ``(predicate, truth)`` pairs of *symbol*.

    Predicates the old assumptions leave undetermined are omitted.  Matrix
    symbols have no scalar declarations and return an empty tuple.
    """
    if isinstance(symbol, MatrixSymbol):
        return ()
    cached = _CACHE.get(symbol)
    if cached is None:
        facts: list[tuple[str, bool]] = []
        for name in DECLARED_ASSUMPTIONS:
            result = ask(getattr(SymPyQ, name)(symbol), context=())
            if result is True:
                facts.append((name, True))
            elif result is False:
                facts.append((name, False))
        cached = tuple(facts)
        _CACHE[symbol] = cached
    return cached


__all__ = ["DECLARED_ASSUMPTIONS", "declared_assumptions"]
