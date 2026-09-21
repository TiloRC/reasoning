"""The boundary between SymPy expressions and the propositional core."""
from functools import lru_cache

from sympy import S, Symbol
from sympy.assumptions.assume import AppliedPredicate
from sympy.assumptions.ask import Q
from sympy.assumptions.ask_generated import (
    get_all_known_matrix_facts, get_all_known_number_facts,
)
from sympy.core.kind import NumberKind, UndefinedKind
from sympy.core.relational import Eq, Ne, Gt, Lt, Ge, Le
from sympy.logic.boolalg import (
    And, Or, Not, Implies, Equivalent, Xor, Xnor, ITE, Nand, Nor,
)
from sympy.matrices.kind import MatrixKind

from .clauses import Formula, AND, OR, NOT, IMPLIES, EQUIVALENT, XOR, ITE as IF
from .sathandlers import class_fact_registry


def to_formula(expr):
    if isinstance(expr, (Formula, bool)):
        return expr
    if expr is S.true:
        return True
    if expr is S.false:
        return False
    # Accept old CNF inputs at the helper API boundary, without using their
    # implementation anywhere in the reasoning pipeline.
    if hasattr(expr, 'clauses'):
        return AND(*(OR(*(NOT(to_formula(lit.lit)) if lit.is_Not
                           else to_formula(lit.lit) for lit in clause))
                     for clause in expr.clauses))
    relation = {Eq: Q.eq, Ne: Q.ne, Gt: Q.gt, Lt: Q.lt, Ge: Q.ge, Le: Q.le}.get(type(expr))
    if relation is not None:
        return relation(*expr.args)
    operators = {And: AND, Or: OR, Not: NOT, Implies: IMPLIES,
                 Equivalent: EQUIVALENT, Xor: XOR, ITE: IF}
    constructor = operators.get(type(expr))
    if constructor is not None:
        return constructor(*(to_formula(arg) for arg in expr.args))
    if isinstance(expr, (Nand, Nor, Xnor)):
        constructor = AND if isinstance(expr, Nand) else OR if isinstance(expr, Nor) else XOR
        return NOT(constructor(*(to_formula(arg) for arg in expr.args)))
    return expr


@lru_cache(maxsize=3)
def _known_template(numbers, matrices):
    clauses = set()
    if numbers:
        clauses.update(get_all_known_number_facts())
    if matrices:
        clauses.update(get_all_known_matrix_facts())
    predicates = sorted({lit.lit for clause in clauses for lit in clause}, key=str)
    encoding = {predicate: i + 1 for i, predicate in enumerate(predicates)}
    data = tuple(tuple(-encoding[lit.lit] if lit.is_Not else encoding[lit.lit]
                       for lit in clause) for clause in clauses)
    return predicates, data


class SympyAdapter:
    def relevance_keys(self, atom):
        return atom.atoms(Symbol)

    def subjects(self, atom):
        return atom.arguments if isinstance(atom, AppliedPredicate) else (atom,)

    def fact_subjects(self, atom):
        return atom.arguments if isinstance(atom, AppliedPredicate) else ()

    def facts_for(self, subject):
        return (to_formula(fact) for fact in class_fact_registry(subject))

    def add_known_facts(self, subjects, db):
        numbers = any(expr.kind in (NumberKind, UndefinedKind) for expr in subjects)
        matrices = any(expr.kind == MatrixKind(NumberKind) for expr in subjects)
        predicates, clauses = _known_template(numbers, matrices)
        for subject in subjects:
            mapping = [None] + [db.literal(predicate(subject)) for predicate in predicates]
            for clause in clauses:
                db.add_clause(mapping[lit] if lit > 0 else -mapping[-lit] for lit in clause)
