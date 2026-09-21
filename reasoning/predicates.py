"""A SymPy-independent predicate vocabulary.

The names mirror SymPy's ``Q``, but this module never imports SymPy.  A
:class:`Predicate` is applied to opaque arguments to produce an
:class:`AppliedPredicate`, which is hashable and compares structurally, so the
propositional core can use it as an atom.  In the SymPy adapter the arguments
are SymPy expressions, which are the only SymPy values that reach the core.
"""
from __future__ import annotations

from typing import Iterable


class Predicate:
    """An un-applied predicate such as ``Q.real``."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = str(name)

    def __call__(self, *arguments: object) -> AppliedPredicate:
        return AppliedPredicate(self, arguments)

    def __repr__(self) -> str:
        return f"Q.{self.name}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Predicate) and other.name == self.name

    def __hash__(self) -> int:
        return hash((Predicate, self.name))


class AppliedPredicate:
    """A predicate applied to arguments, such as ``Q.real(x)``."""

    __slots__ = ("predicate", "arguments")

    def __init__(self, predicate: Predicate,
                 arguments: tuple[object, ...]) -> None:
        self.predicate = predicate
        self.arguments = arguments

    @property
    def name(self) -> str:
        return self.predicate.name

    def __repr__(self) -> str:
        arguments = ", ".join(repr(argument) for argument in self.arguments)
        return f"Q.{self.name}({arguments})"

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, AppliedPredicate)
                and other.predicate == self.predicate
                and other.arguments == self.arguments)

    def __hash__(self) -> int:
        return hash((AppliedPredicate, self.predicate, self.arguments))


_PREDICATE_NAMES = frozenset({
    "algebraic", "antihermitian", "commutative", "complex",
    "complex_elements", "composite", "diagonal", "eq", "even", "extended_negative",
    "extended_nonnegative", "extended_nonpositive", "extended_nonzero",
    "extended_positive", "extended_real", "finite", "fullrank", "ge", "gt",
    "hermitian", "imaginary", "infinite", "integer", "integer_elements",
    "invertible", "irrational", "le", "lower_triangular", "lt", "ne",
    "negative", "negative_infinite", "nonnegative", "nonpositive", "nonzero",
    "normal", "odd", "orthogonal", "positive", "positive_definite",
    "positive_infinite", "prime", "rational", "real", "real_elements",
    "singular", "square", "symmetric", "transcendental", "triangular",
    "unit_triangular", "unitary", "upper_triangular", "zero",
})


class PredicateNamespace:
    """Attribute access to the known predicates, mirroring SymPy's ``Q``."""

    def __init__(self, names: Iterable[str] = _PREDICATE_NAMES) -> None:
        self._predicates = {name: Predicate(name) for name in names}

    def __getattr__(self, name: str) -> Predicate:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._predicates[name]
        except KeyError:
            raise AttributeError(f"unknown predicate {name!r}") from None

    def __getitem__(self, name: str) -> Predicate:
        return self._predicates[name]

    def of(self, name: str) -> Predicate:
        """Return the predicate called *name*, creating unknown ones."""
        name = str(name)
        predicate = self._predicates.get(name)
        return Predicate(name) if predicate is None else predicate

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._predicates

    def names(self) -> list[str]:
        return sorted(self._predicates)


Q = PredicateNamespace()

__all__ = ["AppliedPredicate", "Predicate", "PredicateNamespace", "Q"]
