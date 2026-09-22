"""The boundary between SymPy expressions and the propositional core."""
from functools import lru_cache
from typing import Any, Callable, Iterable, TypeAlias, cast

from sympy import S, Symbol
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.kind import NumberKind, UndefinedKind
from sympy.core.relational import Eq, Ne, Gt, Lt, Ge, Le
from sympy.logic.boolalg import (
    And, Or, Not, Implies, Equivalent, Xor, Xnor, ITE, Nand, Nor,
)
from sympy.matrices.kind import MatrixKind

from .clauses import (
    ClauseDB, Formula, AND, OR, NOT, IMPLIES, EQUIVALENT, XOR, ITE as IF,
    iter_atoms,
)
from .knownfacts import template as known_facts_template
from .predicates import AppliedPredicate as LocalAppliedPredicate
from .predicates import Predicate as LocalPredicate
from .predicates import Q as LocalQ
from .sathandlers import class_fact_registry
from .sympy_types import SymPyExpr

NormalizedFormula: TypeAlias = bool | Formula | LocalAppliedPredicate


def to_sympy(value: object) -> SymPyExpr:
    """Normalize a public input to a SymPy expression.

    Python Booleans become ``S.true``/``S.false`` and legacy CNF objects are
    converted clause by clause.  Anything else must already be a SymPy
    expression, otherwise a ``TypeError`` is raised.
    """
    if isinstance(value, SymPyExpr):
        result: object = value
    elif value is True or value is False:
        result = S.true if value else S.false
    else:
        clauses = getattr(value, 'clauses', None)
        if clauses is None:
            raise TypeError(
                f"expected a SymPy expression, got {type(value).__name__}")
        result = And(*(Or(*(Not(lit.lit) if lit.is_Not else lit.lit
                            for lit in clause))
                       for clause in clauses))
    assert isinstance(result, SymPyExpr)
    return result


def to_local_predicate(applied: Any) -> LocalAppliedPredicate:
    """Convert a SymPy applied predicate to the local predicate vocabulary."""
    return LocalQ.of(applied.function.name)(*applied.arguments)


def normalize(value: object) -> NormalizedFormula:
    """Normalize a public input to a SymPy-free formula.

    SymPy Booleans, relations, and ``Q`` applications become lightweight
    formulas whose atoms are :mod:`reasoning.predicates` applications; the
    only SymPy values that remain are the expression arguments of those
    applications.  Any other leaf raises TypeError.
    """
    expr = to_sympy(value)
    assert isinstance(expr, SymPyExpr)
    formula = to_formula(expr)
    for atom in iter_atoms(formula):
        if not isinstance(atom, LocalAppliedPredicate):
            raise TypeError(f"{atom!r} is not an applied predicate")
    return cast("NormalizedFormula", formula)


def to_formula(expr: object) -> object:
    if isinstance(expr, (Formula, bool)):
        return expr
    if expr is S.true:
        return True
    if expr is S.false:
        return False
    value = cast("Any", expr)
    # Accept old CNF inputs at the helper API boundary, without using their
    # implementation anywhere in the reasoning pipeline.
    clauses = getattr(value, 'clauses', None)
    if clauses is not None:
        return AND(*(OR(*(NOT(to_formula(lit.lit)) if lit.is_Not
                           else to_formula(lit.lit) for lit in clause))
                     for clause in clauses))
    relation = {Eq: LocalQ.eq, Ne: LocalQ.ne, Gt: LocalQ.gt,
                Lt: LocalQ.lt, Ge: LocalQ.ge, Le: LocalQ.le}.get(type(value))
    if relation is not None:
        return relation(*value.args)
    operators: dict[Any, Callable[..., object]] = {
        And: AND, Or: OR, Not: NOT, Implies: IMPLIES,
        Equivalent: EQUIVALENT, Xor: XOR, ITE: IF,
    }
    constructor = operators.get(type(value))
    if constructor is not None:
        return constructor(*(to_formula(arg) for arg in value.args))
    if isinstance(value, (Nand, Nor, Xnor)):
        constructor = AND if isinstance(value, Nand) else OR if isinstance(value, Nor) else XOR
        return NOT(constructor(*(to_formula(arg) for arg in value.args)))
    if isinstance(value, AppliedPredicate):
        return to_local_predicate(value)
    return expr


@lru_cache(maxsize=3)
def _known_template(numbers: bool, matrices: bool) -> tuple[
    list[LocalPredicate], tuple[tuple[int, ...], ...],
]:
    names, clauses = known_facts_template(numbers, matrices)
    predicates = [LocalQ.of(name) for name in names]
    return predicates, clauses


class SympyAdapter:
    def relevance_keys(self, atom: Any) -> set[SymPyExpr]:
        if isinstance(atom, LocalAppliedPredicate):
            keys: set[SymPyExpr] = set()
            for argument in atom.arguments:
                keys.update(cast("Any", argument).atoms(Symbol))
            return keys
        return cast("set[SymPyExpr]", atom.atoms(Symbol))

    def subjects(self, atom: Any) -> Iterable[object]:
        if isinstance(atom, (LocalAppliedPredicate, AppliedPredicate)):
            return atom.arguments
        return (atom,)

    def fact_subjects(self, atom: Any) -> Iterable[object]:
        if isinstance(atom, (LocalAppliedPredicate, AppliedPredicate)):
            return atom.arguments
        return ()

    def facts_for(self, subject: SymPyExpr) -> Iterable[object]:
        return (to_formula(fact) for fact in class_fact_registry(subject))

    def add_known_facts(self, subjects: Iterable[SymPyExpr], db: ClauseDB) -> None:
        numbers = any(expr.kind in (NumberKind, UndefinedKind) for expr in subjects)
        matrices = any(expr.kind == MatrixKind(NumberKind) for expr in subjects)
        predicates, clauses = _known_template(numbers, matrices)
        for subject in subjects:
            mapping: list[int | None] = [None] + [
                db.literal(predicate(subject)) for predicate in predicates
            ]
            for clause in clauses:
                literals = [
                    cast(int, mapping[lit]) if lit > 0
                    else -cast(int, mapping[-lit])
                    for lit in clause
                ]
                db.add_clause(literals)
