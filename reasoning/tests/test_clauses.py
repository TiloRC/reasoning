from itertools import product

import pytest

from reasoning.clauses import (
    AND, EQUIVALENT, ITE, IMPLIES, NOT, OR, XOR,
    ClauseDB, assert_formula, compile_formula, iter_atoms,
)


def _satisfies(clauses, assignment):
    return all(any(assignment[abs(literal)] == (literal > 0) for literal in clause)
               for clause in clauses)


def _can_satisfy(db, fixed):
    variables = range(1, max([0, *db.symbols, *db.auxiliaries]) + 1)
    free = [variable for variable in variables if variable not in fixed]
    for values in product((False, True), repeat=len(free)):
        assignment = dict(fixed)
        assignment.update(zip(free, values))
        if _satisfies(db.data, assignment):
            return True
    return False


def _formula_value(formula, values):
    if formula is True or formula is False:
        return formula
    if not hasattr(formula, "op"):
        return values[formula]
    args = [_formula_value(arg, values) for arg in formula.args]
    if formula.op == "and":
        return all(args)
    if formula.op == "or":
        return any(args)
    if formula.op == "not":
        return not args[0]
    if formula.op == "implies":
        return not args[0] or args[1]
    if formula.op == "equivalent":
        return all(arg == args[0] for arg in args[1:])
    if formula.op == "xor":
        return args[0] != args[1]
    if formula.op == "ite":
        return args[1] if args[0] else args[2]
    raise AssertionError(formula.op)


@pytest.mark.parametrize("formula", [
    AND("a", OR("b", NOT("c"))),
    IMPLIES(AND("a", "b"), OR("c", NOT("a"))),
    EQUIVALENT("a", "b", NOT("c")),
    XOR("a", "b", "c"),
    ITE("a", XOR("b", "c"), EQUIVALENT("b", "c")),
    AND(True, OR(False, "a"), IMPLIES("b", False)),
])
def test_compiled_literal_is_equivalent_to_formula(formula):
    db = ClauseDB()
    query = compile_formula(formula, db)
    atoms = tuple(dict.fromkeys(iter_atoms(formula)))
    for bits in product((False, True), repeat=len(atoms)):
        values = dict(zip(atoms, bits))
        fixed = {db.literal(atom): value for atom, value in values.items()}
        expected = _formula_value(formula, values)
        if isinstance(query, bool):
            assert query is expected
        else:
            assert _can_satisfy(db, {**fixed, abs(query): expected == (query > 0)})
            assert not _can_satisfy(db, {**fixed, abs(query): expected != (query > 0)})


def test_assert_formula_handles_constants_and_direct_clauses():
    db = ClauseDB()
    assert_formula(AND(True, OR("a", NOT("b")), IMPLIES("b", "c")), db)
    assert db.data == [{1, -2}, {-2, 3}]
    assert db.encoding == {"a": 1, "b": 2, "c": 3}

    hybrid = ClauseDB()
    assert_formula(IMPLIES(AND("a", NOT("b")), OR("c", NOT("d"))), hybrid)
    assert hybrid.data == [{-1, 2, 3, -4}]
    assert hybrid.auxiliaries == set()

    false_db = ClauseDB()
    assert_formula(False, false_db)
    assert false_db.data == [set()]

    true_db = ClauseDB()
    assert_formula(True, true_db)
    assert true_db.data == []


def test_clause_normalization_and_auxiliary_variables():
    db = ClauseDB()
    a = db.literal("a")
    auxiliary = db.new_auxiliary_variable()
    db.add_clause((a, -a))
    db.add_clause((False, auxiliary))
    db.add_clause((True, auxiliary))
    assert db.data == [{auxiliary}]
    assert db.symbols == {a: "a"}
    assert db.auxiliaries == {auxiliary}
    assert db.format_clauses() == "('@2')"
    with pytest.raises(ValueError):
        db.add_clause((0,))


def test_iter_atoms_excludes_constants_and_preserves_opaque_objects():
    atom = ("predicate", 1)
    assert list(iter_atoms(AND(True, atom, NOT(False)))) == [atom]
