"""Domain-independent relevance and fact discovery."""
from typing import Any, Hashable, Iterable, Protocol

from .clauses import ClauseDB, assert_formula, iter_atoms


class Adapter(Protocol):
    """Supplies expression knowledge to the discovery algorithms."""

    def relevance_keys(self, atom: Any) -> Iterable[Hashable]: ...

    def subjects(self, atom: Any) -> Iterable[object]: ...

    def fact_subjects(self, atom: Any) -> Iterable[object]: ...

    def facts_for(self, subject: Any) -> Iterable[object]: ...


def relevant_subjects(proposition: object, assumptions: object,
                      adapter: Adapter) -> set[object]:
    atoms = set(iter_atoms(proposition))
    candidates = set(iter_atoms(assumptions)) - atoms
    keys: set[Hashable] = set()
    for atom in atoms:
        keys.update(adapter.relevance_keys(atom))
    indexed: list[tuple[object, set[Hashable]]] = [
        (atom, set(adapter.relevance_keys(atom))) for atom in candidates
    ]
    while True:
        remaining: list[tuple[object, set[Hashable]]] = []
        changed = False
        for atom, atom_keys in indexed:
            if keys & atom_keys:
                atoms.add(atom)
                keys.update(atom_keys)
                changed = True
            else:
                remaining.append((atom, atom_keys))
        if not changed:
            break
        indexed = remaining
    subjects: set[object] = set()
    for atom in atoms:
        subjects.update(adapter.subjects(atom))
    return subjects


def discover_facts(subjects: Iterable[object], db: ClauseDB, adapter: Adapter,
                   iterations: int | None = None) -> set[object]:
    """Process each subject once, respecting breadth-first discovery rounds."""
    visited: set[object] = set()
    frontier = set(subjects)
    rounds = 0
    while frontier and (iterations is None or rounds < iterations):
        visited.update(frontier)
        following: set[object] = set()
        for subject in frontier:
            for fact in adapter.facts_for(subject):
                for atom in iter_atoms(fact):
                    following.update(adapter.fact_subjects(atom))
                assert_formula(fact, db)
        frontier = following - visited
        rounds += 1
    return visited
