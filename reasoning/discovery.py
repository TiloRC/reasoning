"""Domain-independent relevance and fact discovery."""
from .clauses import assert_formula, iter_atoms


def relevant_subjects(proposition, assumptions, adapter):
    atoms = set(iter_atoms(proposition))
    candidates = set(iter_atoms(assumptions)) - atoms
    keys = set().union(*(adapter.relevance_keys(atom) for atom in atoms))
    indexed = [(atom, adapter.relevance_keys(atom)) for atom in candidates]
    while True:
        remaining = []
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
    return set().union(*(adapter.subjects(atom) for atom in atoms))


def discover_facts(subjects, db, adapter, iterations=None):
    """Process each subject once, respecting breadth-first discovery rounds."""
    visited = set()
    frontier = set(subjects)
    rounds = 0
    while frontier and (iterations is None or rounds < iterations):
        visited.update(frontier)
        following = set()
        for subject in frontier:
            for fact in adapter.facts_for(subject):
                for atom in iter_atoms(fact):
                    following.update(adapter.fact_subjects(atom))
                assert_formula(fact, db)
        frontier = following - visited
        rounds += 1
    return visited
