"""A unary known-fact theory over opaque predicate atoms.

The SymPy known facts are a fixed CNF template over unary predicates such as
``real``, ``integer`` or ``invertible``: whichever subject the template is
instantiated for, the clauses are the same and only the subject argument
changes.  Instead of materializing all template clauses for every subject in
the SAT database, this module compiles the template once into the set of its
models and lets a theory solver reject SAT assignments that cannot be
extended to a template model.

The module is SymPy-free: a template is a CNF over 1-based integer predicate
indices, and the theory only knows solver variables.  Explanations are clauses
over those variables, so every conflict the theory reports can be added to the
SAT solver as a learned clause.
"""
from __future__ import annotations

from typing import Iterable

Literal = tuple[int, bool]


def _propagate(assignment: list[int],
               clauses: tuple[tuple[int, ...], ...]) -> bool:
    """Unit-propagate *clauses* into *assignment*; return False on conflict.

    ``assignment[i]`` is ``0`` for unassigned, ``1`` for true and ``-1`` for
    false, for the predicate ``i + 1``.
    """
    while True:
        changed = False
        for clause in clauses:
            unassigned = 0
            satisfied = False
            last = 0
            for literal in clause:
                value = assignment[abs(literal) - 1]
                if value == 0:
                    unassigned += 1
                    last = literal
                elif (value == 1) == (literal > 0):
                    satisfied = True
                    break
            if satisfied:
                continue
            if unassigned == 0:
                return False
            if unassigned == 1:
                assignment[abs(last) - 1] = 1 if last > 0 else -1
                changed = True
        if not changed:
            return True


def _enumerate_models(n: int, clauses: tuple[tuple[int, ...], ...]) -> list[int]:
    """Return every model of *clauses* as a bitmask over its predicates."""
    models: list[int] = []

    def search(assignment: list[int], start: int) -> None:
        if not _propagate(assignment, clauses):
            return
        index = start
        while index < n and assignment[index] != 0:
            index += 1
        if index == n:
            bits = 0
            for position, value in enumerate(assignment):
                if value == 1:
                    bits |= 1 << position
            models.append(bits)
            return
        for value in (1, -1):
            search(assignment[:index] + [value] + assignment[index + 1:],
                   index + 1)

    search([0] * n, 0)
    return models


class _Component:
    """One independent block of a template, with its model set."""

    def __init__(self, predicates: list[int],
                 clauses: tuple[tuple[int, ...], ...]) -> None:
        local = {predicate: index + 1
                 for index, predicate in enumerate(predicates)}
        reindexed = tuple(
            tuple(local[abs(literal)] * (1 if literal > 0 else -1)
                  for literal in clause)
            for clause in clauses
        )
        self.models = _enumerate_models(len(predicates), reindexed)
        assert self.models, "template components must be satisfiable"
        self.pred_masks: dict[int, int] = {}
        for index, predicate in enumerate(predicates):
            mask = 0
            for model_index, model in enumerate(self.models):
                if model >> index & 1:
                    mask |= 1 << model_index
            self.pred_masks[predicate] = mask
        self.all = (1 << len(self.models)) - 1

    def inconsistent(self, literals: Iterable[Literal]) -> bool:
        available = self.all
        for predicate, value in literals:
            mask = self.pred_masks[predicate]
            available &= mask if value else ~mask
            if available == 0:
                return True
        return False

    def available(self, literals: Iterable[Literal]) -> int:
        """Return the models consistent with *literals* as a bitmask."""
        available = self.all
        for predicate, value in literals:
            mask = self.pred_masks[predicate]
            available &= mask if value else ~mask
        return available

    def core_for(self, literals: Iterable[Literal], predicate: int,
                 value: bool) -> list[Literal] | None:
        """Return an inconsistent core forcing *predicate* to *value*, or None.

        *literals* must be consistent with the template; ``None`` means the
        template does not force *predicate* under them.  The returned core is
        a subset of *literals* that becomes inconsistent when the opposite
        value of *predicate* is added.
        """
        forced = self.available(literals)
        if forced == 0:
            return None
        mask = self.pred_masks[predicate]
        if value and forced & ~mask != 0:
            return None
        if not value and forced & mask != 0:
            return None
        candidate: list[Literal] = list(literals) + [(predicate, not value)]
        core = self.minimize(candidate)
        return [entry for entry in core if entry != (predicate, not value)]

    def minimize(self, core: list[Literal]) -> list[Literal]:
        """Drop literals the conflict does not need, keeping the core unsat."""
        index = 0
        while index < len(core):
            trial = core[:index] + core[index + 1:]
            if self.inconsistent(trial):
                core = trial
            else:
                index += 1
        return core

    def conflict(self, literals: Iterable[Literal]) -> list[Literal] | None:
        """Return an inconsistent core of *literals*, or None."""
        available = self.all
        seen: list[Literal] = []
        for predicate, value in literals:
            mask = self.pred_masks[predicate]
            available &= mask if value else ~mask
            seen.append((predicate, value))
            if available == 0:
                return self.minimize(seen)
        return None


class CompiledTemplate:
    """A CNF template compiled into independent components and model sets.

    Components are found by connectedness in the clause hypergraph, so a
    template that is the disjoint union of two fact sets (the number and
    matrix predicates) is never enumerated as their Cartesian product.
    """

    def __init__(self, n_predicates: int,
                 clauses: Iterable[Iterable[int]]) -> None:
        clause_list = tuple(
            tuple(dict.fromkeys(clause)) for clause in clauses)
        parent = list(range(n_predicates + 1))

        def find(item: int) -> int:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        for clause in clause_list:
            head = find(abs(clause[0]))
            for literal in clause[1:]:
                other = find(abs(literal))
                if other != head:
                    parent[other] = head

        groups: dict[int, list[int]] = {}
        for predicate in range(1, n_predicates + 1):
            groups.setdefault(find(predicate), []).append(predicate)

        self.components: list[_Component] = []
        self._component_of: dict[int, int] = {}
        for predicates in groups.values():
            members = set(predicates)
            member_clauses = tuple(
                clause for clause in clause_list
                if abs(clause[0]) in members
            )
            component = _Component(predicates, member_clauses)
            index = len(self.components)
            self.components.append(component)
            for predicate in predicates:
                self._component_of[predicate] = index

    def check(self, literals: Iterable[Literal]
              ) -> tuple[bool, list[Literal]]:
        """Return ``(True, [])`` or ``(False, core)`` for *literals*.

        ``literals`` is an iterable of ``(predicate, value)`` pairs with
        1-based predicate indices; the core is a subset that is already
        inconsistent with the template.
        """
        grouped: dict[int, list[Literal]] = {}
        for predicate, value in literals:
            grouped.setdefault(self._component_of[predicate], []).append(
                (predicate, value))
        for index, component_literals in grouped.items():
            core = self.components[index].conflict(component_literals)
            if core is not None:
                return False, core
        return True, []

    def model_counts(self) -> list[int]:
        return [len(component.models) for component in self.components]

    def component_of(self, predicate: int) -> int:
        """Return the component index of a 1-based predicate index."""
        return self._component_of[predicate]


class UnaryTheory:
    """A theory solver enforcing a :class:`CompiledTemplate` per subject.

    The caller supplies, for every subject the template applies to, a mapping
    from template predicate index to the solver variable that represents that
    predicate for the subject.  Assignments arrive through ``assert_lit``;
    ``check`` verifies that each subject's assignment extends to a template
    model and returns a conflict clause otherwise.
    """

    def __init__(self, template: CompiledTemplate,
                 subjects: Iterable[dict[int, int]],
                 enable_propagation: bool = True) -> None:
        self.template = template
        self.enable_propagation = enable_propagation
        self._subject_variables = [dict(mapping) for mapping in subjects]
        self._variable_info: dict[int, tuple[int, int]] = {}
        for subject, mapping in enumerate(self._subject_variables):
            for predicate, variable in mapping.items():
                self._variable_info[variable] = (subject, predicate)
        self._entries: list[
            list[tuple[int, _Component, list[tuple[int, int]]]]
        ] = []
        for mapping in self._subject_variables:
            grouped: dict[int, list[tuple[int, int]]] = {}
            for predicate, variable in mapping.items():
                grouped.setdefault(template.component_of(predicate), []).append(
                    (predicate, variable))
            self._entries.append([
                (index, template.components[index], entries)
                for index, entries in grouped.items()
            ])
        self._assignments: list[dict[int, bool]] = [
            {} for _ in self._subject_variables]
        self._levels: list[list[tuple[int, int]]] = [[]]
        self._version = 0
        self._propagation_cache: tuple[int, list[tuple[int, list[int]]]] | None = None
        self.num_checks = 0
        self.num_conflicts = 0

    def assert_lit(self, literal: int) -> tuple[bool, list[int]] | None:
        info = self._variable_info.get(abs(literal))
        if info is None:
            return None
        subject, predicate = info
        if predicate in self._assignments[subject]:
            # The solver can assert the same literal more than once, for
            # example when two clauses put it in the unit queue.
            return None
        self._assignments[subject][predicate] = literal > 0
        self._levels[-1].append((subject, predicate))
        self._version += 1
        self._propagation_cache = None
        return None

    def check(self) -> tuple[bool, list[int]]:
        self.num_checks += 1
        for subject, assignment in enumerate(self._assignments):
            if not assignment:
                continue
            consistent, core = self.template.check(assignment.items())
            if consistent:
                continue
            variables = self._subject_variables[subject]
            clause = [
                -variables[predicate] if value else variables[predicate]
                for predicate, value in core
            ]
            self.num_conflicts += 1
            return False, clause
        return True, []

    def push_level(self) -> None:
        self._levels.append([])

    def pop_level(self) -> None:
        for subject, predicate in self._levels.pop():
            del self._assignments[subject][predicate]
            self._version += 1
        self._propagation_cache = None

    def propagate(self) -> list[tuple[int, list[int]]]:
        """Return literals every template model forces under the assignment.

        Only predicates with a solver variable are reported; a predicate the
        clause database never allocated cannot affect the SAT search because
        the model masks already quantify over it.
        """
        if not self.enable_propagation:
            return []
        cached = self._propagation_cache
        if cached is not None and cached[0] == self._version:
            return cached[1]
        implied: list[tuple[int, list[int]]] = []
        for subject, assignment in enumerate(self._assignments):
            if not assignment:
                continue
            mapping = self._subject_variables[subject]
            for index, component, entries in self._entries[subject]:
                literals = [
                    (predicate, value)
                    for predicate, value in assignment.items()
                    if self.template.component_of(predicate) == index
                ]
                if not literals:
                    continue
                available = component.available(literals)
                if available == 0:
                    core = component.conflict(literals)
                    assert core
                    conflict_clause = [
                        -mapping[item] if item_value else mapping[item]
                        for item, item_value in core
                    ]
                    # The first literal is false under the assignment, so the
                    # solver reads this pair as a conflict clause.
                    implied.append((conflict_clause[0], conflict_clause[1:]))
                    self._propagation_cache = (self._version, implied)
                    return implied
                for predicate, variable in entries:
                    if predicate in assignment:
                        continue
                    mask = component.pred_masks[predicate]
                    if available & mask == 0:
                        value = False
                    elif available & ~mask == 0:
                        value = True
                    else:
                        continue
                    core = component.core_for(literals, predicate, value)
                    assert core is not None
                    explanation = [
                        -mapping[item] if item_value else mapping[item]
                        for item, item_value in core
                    ]
                    implied.append(
                        (variable if value else -variable, explanation))
        self._propagation_cache = (self._version, implied)
        return implied


__all__ = ["CompiledTemplate", "Literal", "UnaryTheory"]
