"""Facts inferred from the structure of SymPy expressions.

This module only uses SymPy to inspect expressions and create predicate atoms.
The facts themselves are lightweight formulas from :mod:`reasoning.clauses`.
"""
from __future__ import annotations

from typing import Any, Callable

from sympy.assumptions.ask import Q
from sympy.core import Add, Mul, Pow, Number, NumberSymbol
from sympy.core.numbers import ImaginaryUnit
from sympy.functions.elementary.complexes import Abs
from sympy.logic.boolalg import And, Or
from sympy.matrices.expressions import MatMul

from reasoning.clauses import AND, EQUIVALENT, IMPLIES, NOT, OR
from reasoning.registry import ClassFactRegistry

Predicate = Callable[[Any], object]


# The public helpers preserve their old signature. Registered handlers use the
# predicate-callable helpers below, so they never create a SymPy Boolean
# expression or substitute a placeholder into one.
def allargs(symbol: Any, fact: Any, expr: Any) -> Any:
    return And(*(fact.subs(symbol, arg) for arg in expr.args))


def anyarg(symbol: Any, fact: Any, expr: Any) -> Any:
    return Or(*(fact.subs(symbol, arg) for arg in expr.args))


def exactlyonearg(symbol: Any, fact: Any, expr: Any) -> Any:
    predicates = [fact.subs(symbol, arg) for arg in expr.args]
    return Or(*(And(predicate, *(~other for other in predicates[:index] + predicates[index + 1:]))
                for index, predicate in enumerate(predicates)))


def _allargs(predicate: Predicate, expr: Any) -> object:
    return AND(*(predicate(arg) for arg in expr.args))


def _anyarg(predicate: Predicate, expr: Any) -> object:
    return OR(*(predicate(arg) for arg in expr.args))


def _exactlyonearg(predicate: Predicate, expr: Any) -> object:
    predicates = [predicate(arg) for arg in expr.args]
    return OR(*(AND(item, *(NOT(other) for other in predicates[:index] + predicates[index + 1:]))
                for index, item in enumerate(predicates)))


class_fact_registry = ClassFactRegistry()


@class_fact_registry.multiregister(Abs)
def _abs_facts(expr: Any) -> list[object]:
    arg = expr.args[0]
    return [
        Q.nonnegative(expr),
        EQUIVALENT(NOT(Q.zero(arg)), NOT(Q.zero(expr))),
        IMPLIES(Q.even(arg), Q.even(expr)),
        IMPLIES(Q.odd(arg), Q.odd(expr)),
        IMPLIES(Q.integer(arg), Q.integer(expr)),
    ]


@class_fact_registry.multiregister(Add)
def _add_facts(expr: Any) -> list[object]:
    return [
        IMPLIES(_allargs(Q.positive, expr), Q.positive(expr)),
        IMPLIES(_allargs(Q.negative, expr), Q.negative(expr)),
        IMPLIES(_allargs(Q.real, expr), Q.real(expr)),
        IMPLIES(_allargs(Q.rational, expr), Q.rational(expr)),
        IMPLIES(_allargs(Q.integer, expr), Q.integer(expr)),
        IMPLIES(_exactlyonearg(lambda arg: NOT(Q.integer(arg)), expr), NOT(Q.integer(expr))),
    ]


@class_fact_registry.register(Add)
def _add_irrational_fact(expr: Any) -> object:
    return IMPLIES(
        _allargs(Q.real, expr),
        IMPLIES(_exactlyonearg(Q.irrational, expr), Q.irrational(expr)),
    )


@class_fact_registry.multiregister(Mul)
def _mul_facts(expr: Any) -> list[object]:
    return [
        EQUIVALENT(Q.zero(expr), _anyarg(Q.zero, expr)),
        IMPLIES(_allargs(Q.positive, expr), Q.positive(expr)),
        IMPLIES(_allargs(Q.real, expr), Q.real(expr)),
        IMPLIES(_allargs(Q.rational, expr), Q.rational(expr)),
        IMPLIES(_allargs(Q.integer, expr), Q.integer(expr)),
        IMPLIES(
            AND(_allargs(lambda arg: NOT(Q.zero(arg)), expr),
                _exactlyonearg(lambda arg: NOT(Q.rational(arg)), expr)),
            NOT(Q.integer(expr)),
        ),
        IMPLIES(_allargs(Q.commutative, expr), Q.commutative(expr)),
    ]


@class_fact_registry.register(Mul)
def _mul_prime_fact(expr: Any) -> object:
    return IMPLIES(_allargs(Q.prime, expr), NOT(Q.prime(expr)))


@class_fact_registry.register(Mul)
def _mul_imaginary_fact(expr: Any) -> object:
    return IMPLIES(
        AND(_allargs(lambda arg: OR(Q.imaginary(arg), Q.real(arg)), expr),
            _allargs(lambda arg: NOT(Q.zero(arg)), expr)),
        IMPLIES(_exactlyonearg(Q.imaginary, expr), Q.imaginary(expr)),
    )


@class_fact_registry.register(Mul)
def _mul_irrational_fact(expr: Any) -> object:
    return IMPLIES(
        AND(_allargs(Q.real, expr), _allargs(lambda arg: NOT(Q.zero(arg)), expr)),
        IMPLIES(_exactlyonearg(Q.irrational, expr), Q.irrational(expr)),
    )


@class_fact_registry.register(Mul)
def _mul_even_fact(expr: Any) -> object:
    return IMPLIES(
        _allargs(Q.integer, expr),
        EQUIVALENT(_anyarg(Q.even, expr), Q.even(expr)),
    )


@class_fact_registry.register(MatMul)
def _matmul_invertible_fact(expr: Any) -> object:
    return IMPLIES(
        _allargs(Q.square, expr),
        EQUIVALENT(Q.invertible(expr), _allargs(Q.invertible, expr)),
    )


@class_fact_registry.multiregister(Pow)
def _pow_facts(expr: Any) -> list[object]:
    base, exp = expr.base, expr.exp
    return [
        IMPLIES(AND(Q.real(base), Q.even(exp), Q.nonnegative(exp)), Q.nonnegative(expr)),
        IMPLIES(AND(Q.nonnegative(base), Q.odd(exp), Q.nonnegative(exp)), Q.nonnegative(expr)),
        IMPLIES(AND(Q.nonpositive(base), Q.odd(exp), Q.nonnegative(exp)), Q.nonpositive(expr)),
        EQUIVALENT(Q.zero(expr), AND(Q.zero(base), Q.positive(exp))),
    ]


_old_assump_getters: dict[Any, Callable[[Any], Any]] = {
    Q.positive: lambda obj: obj.is_positive,
    Q.zero: lambda obj: obj.is_zero,
    Q.negative: lambda obj: obj.is_negative,
    Q.rational: lambda obj: obj.is_rational,
    Q.irrational: lambda obj: obj.is_irrational,
    Q.even: lambda obj: obj.is_even,
    Q.odd: lambda obj: obj.is_odd,
    Q.imaginary: lambda obj: obj.is_imaginary,
    Q.prime: lambda obj: obj.is_prime,
    Q.composite: lambda obj: obj.is_composite,
}


@class_fact_registry.multiregister(Number, NumberSymbol, ImaginaryUnit)
def _number_facts(expr: Any) -> list[object]:
    facts = []
    for predicate, getter in _old_assump_getters.items():
        value = getter(expr)
        if value is not None:
            facts.append(EQUIVALENT(predicate(expr), value))
    return facts


__all__ = [
    'ClassFactRegistry', 'allargs', 'anyarg', 'exactlyonearg',
    'class_fact_registry',
]
