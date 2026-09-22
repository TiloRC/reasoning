"""The interface between the propositional solver and a theory solver."""
from __future__ import annotations

from typing import Any, Iterable, Protocol


class TheorySolver(Protocol):
    """A theory solver working alongside :class:`~reasoning.solver.SATSolver`.

    The SAT solver owns the search and reports every literal it assigns and
    every decision level it opens and closes.  The theory answers with a
    *conflict clause* whenever the literals seen so far are inconsistent --
    the negations of the assigned literals that together caused the conflict.
    The clause is added to the SAT solver, which then avoids repeating the
    assignment.  A conflict clause must be non-empty.

    The protocol matches the four-method interface proposed for SymPy's
    ``dpll2.SATSolver``; notably it has no theory propagation, so a theory
    that only implements these methods can only prune inconsistent total
    assignments.  A theory may additionally implement :class:`PropagatingTheory`
    to prune inconsistent partial assignments.
    """

    def assert_lit(self, literal: int) -> tuple[bool, list[int]] | None:
        """Record an assigned literal, returning a conflict clause if any.

        The first element of the result is ``False`` for a conflict.  A
        theory that does not interpret *literal* returns ``None``.
        """
        ...

    def check(self) -> tuple[bool, Any] | None:
        """Check the current assignment for consistency.

        Returns ``(True, model)`` when the assignment is theory-consistent
        and ``(False, conflict_clause)`` when it is not.  ``None`` means the
        theory has nothing to say about the current assignment.
        """
        ...

    def push_level(self) -> None:
        """Remember enough state to undo the decision level being opened."""
        ...

    def pop_level(self) -> None:
        """Undo every assertion made since the matching ``push_level``."""
        ...


class PropagatingTheory(TheorySolver, Protocol):
    """A theory that can also propagate literals into the SAT solver.

    ``propagate`` is called from ``SATSolver._simplify`` after unit
    propagation.  Each yielded pair is a literal the theory entails under the
    current assignment together with a non-empty *explanation clause* (when
    the implication is unconditional the explanation may be empty): the
    clause is entailed by the theory and is satisfied by the literal, so the
    solver can add it and assign the literal.  Iterator results are computed
    against the assignment as it was when ``propagate`` was called; literal
    assignments made by the solver afterwards are reported back through
    ``assert_lit``.
    """

    def propagate(self) -> Iterable[tuple[int, list[int]]]:
        """Yield ``(literal, explanation_clause)`` pairs the theory entails."""
        ...


__all__ = ["PropagatingTheory", "TheorySolver"]
