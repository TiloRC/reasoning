"""Facts about concrete SymPy numbers from direct structural inspection.

This module never reads SymPy's old assumptions: the exact class of the
expression selects a static table, and the remaining values (sign, parity,
primality) come from Python-level fields such as ``Integer.p`` or ``Float.num``.
"""
from __future__ import annotations

from typing import Any

from sympy.core.numbers import (
    ComplexInfinity, Exp1, Float, GoldenRatio, ImaginaryUnit, Infinity, Integer,
    NaN, NegativeInfinity, NumberSymbol, Pi, Rational, TribonacciConstant,
    int_valued,
)
from sympy.ntheory.primetest import isprime

from reasoning.clauses import EQUIVALENT
from reasoning.predicates import Predicate, Q
from reasoning.sympy_types import SymPyExpr


def _facts(expr: SymPyExpr, values: dict[Predicate, bool]) -> list[object]:
    return [EQUIVALENT(predicate(expr), value) for predicate, value in values.items()]


def _integer_facts(expr: SymPyExpr) -> list[object]:
    value = expr.p
    positive = value > 0
    negative = value < 0
    zero = value == 0
    nonzero = value != 0
    return _facts(expr, {
        Q.positive: positive,
        Q.negative: negative,
        Q.zero: zero,
        Q.nonzero: nonzero,
        Q.nonnegative: value >= 0,
        Q.nonpositive: value <= 0,
        Q.extended_positive: positive,
        Q.extended_negative: negative,
        Q.extended_nonnegative: value >= 0,
        Q.extended_nonpositive: value <= 0,
        Q.extended_nonzero: nonzero,
        Q.rational: True,
        Q.irrational: False,
        Q.integer: True,
        Q.even: value % 2 == 0,
        Q.odd: value % 2 != 0,
        Q.prime: value > 1 and isprime(value),
        Q.composite: value > 1 and not isprime(value),
        Q.algebraic: True,
        Q.transcendental: False,
        Q.real: True,
        Q.complex: True,
        Q.extended_real: True,
        Q.finite: True,
        Q.infinite: False,
        Q.imaginary: False,
        Q.commutative: True,
        Q.hermitian: True,
        Q.antihermitian: zero,
    })


def _rational_facts(expr: SymPyExpr) -> list[object]:
    numerator = expr.p
    sign = numerator * expr.q
    zero = numerator == 0
    nonzero = numerator != 0
    return _facts(expr, {
        Q.positive: sign > 0,
        Q.negative: sign < 0,
        Q.zero: zero,
        Q.nonzero: nonzero,
        Q.nonnegative: sign >= 0,
        Q.nonpositive: sign <= 0,
        Q.extended_positive: sign > 0,
        Q.extended_negative: sign < 0,
        Q.extended_nonnegative: sign >= 0,
        Q.extended_nonpositive: sign <= 0,
        Q.extended_nonzero: nonzero,
        Q.rational: True,
        Q.irrational: False,
        Q.integer: False,
        Q.even: False,
        Q.odd: False,
        Q.prime: False,
        Q.composite: False,
        Q.algebraic: True,
        Q.transcendental: False,
        Q.real: True,
        Q.complex: True,
        Q.extended_real: True,
        Q.finite: True,
        Q.infinite: False,
        Q.imaginary: False,
        Q.commutative: True,
        Q.hermitian: True,
        Q.antihermitian: zero,
    })


def _float_facts(expr: SymPyExpr) -> list[object]:
    value = expr.num
    zero = value == 0
    positive = value > 0
    negative = value < 0
    nonzero = value != 0
    values: dict[Predicate, bool] = {
        Q.positive: positive,
        Q.negative: negative,
        Q.zero: zero,
        Q.nonzero: nonzero,
        Q.nonnegative: value >= 0,
        Q.nonpositive: value <= 0,
        Q.extended_positive: positive,
        Q.extended_negative: negative,
        Q.extended_nonnegative: value >= 0,
        Q.extended_nonpositive: value <= 0,
        Q.extended_nonzero: nonzero,
        Q.real: True,
        Q.complex: True,
        Q.extended_real: True,
        Q.finite: True,
        Q.infinite: False,
        Q.imaginary: False,
        Q.commutative: True,
        Q.hermitian: True,
        Q.antihermitian: zero,
    }
    if not int_valued(expr):
        values.update({
            Q.integer: False,
            Q.even: False,
            Q.odd: False,
            Q.prime: False,
            Q.composite: False,
        })
    return _facts(expr, values)


_TRANSCENDENTAL_SYMBOL_FACTS: dict[Predicate, bool] = {
    Q.irrational: True,
    Q.algebraic: False,
    Q.transcendental: True,
    Q.real: True,
    Q.complex: True,
    Q.positive: True,
    Q.negative: False,
    Q.zero: False,
    Q.nonzero: True,
    Q.finite: True,
    Q.infinite: False,
    Q.extended_real: True,
    Q.extended_positive: True,
    Q.extended_negative: False,
    Q.extended_nonzero: True,
    Q.commutative: True,
    Q.integer: False,
    Q.rational: False,
    Q.even: False,
    Q.odd: False,
    Q.prime: False,
    Q.composite: False,
    Q.imaginary: False,
    Q.hermitian: True,
    Q.antihermitian: False,
}

_ALGEBRAIC_SYMBOL_FACTS: dict[Predicate, bool] = {
    **_TRANSCENDENTAL_SYMBOL_FACTS,
    Q.algebraic: True,
    Q.transcendental: False,
}

_NUMBER_SYMBOL_FACTS: dict[type[Any], dict[Predicate, bool]] = {
    Pi: _TRANSCENDENTAL_SYMBOL_FACTS,
    Exp1: _TRANSCENDENTAL_SYMBOL_FACTS,
    GoldenRatio: _ALGEBRAIC_SYMBOL_FACTS,
    TribonacciConstant: _ALGEBRAIC_SYMBOL_FACTS,
}

_IMAGINARY_UNIT_FACTS: dict[Predicate, bool] = {
    Q.algebraic: True,
    Q.transcendental: False,
    Q.imaginary: True,
    Q.real: False,
    Q.complex: True,
    Q.finite: True,
    Q.infinite: False,
    Q.commutative: True,
    Q.extended_real: False,
    Q.extended_positive: False,
    Q.extended_negative: False,
    Q.extended_nonzero: False,
    Q.zero: False,
    Q.nonzero: False,
    Q.positive: False,
    Q.negative: False,
    Q.rational: False,
    Q.irrational: False,
    Q.integer: False,
    Q.even: False,
    Q.odd: False,
    Q.prime: False,
    Q.composite: False,
    Q.hermitian: False,
    Q.antihermitian: True,
}

_INFINITY_FACTS: dict[Predicate, bool] = {
    Q.infinite: True,
    Q.finite: False,
    Q.extended_real: True,
    Q.real: False,
    Q.complex: False,
    Q.extended_positive: True,
    Q.extended_negative: False,
    Q.positive: False,
    Q.negative: False,
    Q.zero: False,
    Q.nonzero: False,
    Q.rational: False,
    Q.irrational: False,
    Q.integer: False,
    Q.even: False,
    Q.odd: False,
    Q.prime: False,
    Q.composite: False,
    Q.algebraic: False,
    Q.transcendental: False,
    Q.commutative: True,
    Q.hermitian: False,
    Q.antihermitian: False,
    Q.positive_infinite: True,
    Q.negative_infinite: False,
    Q.extended_nonzero: True,
    Q.extended_nonnegative: True,
    Q.extended_nonpositive: False,
    Q.nonnegative: False,
    Q.nonpositive: False,
}

_NEGATIVE_INFINITY_FACTS: dict[Predicate, bool] = {
    **_INFINITY_FACTS,
    Q.extended_positive: False,
    Q.extended_negative: True,
    Q.positive_infinite: False,
    Q.negative_infinite: True,
    Q.extended_nonnegative: False,
    Q.extended_nonpositive: True,
}

_COMPLEX_INFINITY_FACTS: dict[Predicate, bool] = {
    Q.infinite: True,
    Q.finite: False,
    Q.extended_real: False,
    Q.real: False,
    Q.complex: False,
    Q.extended_positive: False,
    Q.extended_negative: False,
    Q.positive: False,
    Q.negative: False,
    Q.zero: False,
    Q.nonzero: False,
    Q.rational: False,
    Q.irrational: False,
    Q.integer: False,
    Q.even: False,
    Q.odd: False,
    Q.prime: False,
    Q.composite: False,
    Q.algebraic: False,
    Q.transcendental: False,
    Q.commutative: True,
    Q.hermitian: False,
    Q.antihermitian: False,
    Q.positive_infinite: False,
    Q.negative_infinite: False,
    Q.extended_nonzero: False,
    Q.nonnegative: False,
    Q.nonpositive: False,
    Q.extended_nonnegative: False,
    Q.extended_nonpositive: False,
}

_NAN_FACTS: dict[Predicate, bool] = {
    Q.commutative: True,
}


def number_facts(expr: SymPyExpr) -> list[object]:
    """Return the facts known about a concrete number expression."""
    if isinstance(expr, Integer):
        return _integer_facts(expr)
    if isinstance(expr, Rational):
        return _rational_facts(expr)
    if isinstance(expr, Float):
        return _float_facts(expr)
    if isinstance(expr, NaN):
        return _facts(expr, _NAN_FACTS)
    if isinstance(expr, Infinity):
        return _facts(expr, _INFINITY_FACTS)
    if isinstance(expr, NegativeInfinity):
        return _facts(expr, _NEGATIVE_INFINITY_FACTS)
    if isinstance(expr, ComplexInfinity):
        return _facts(expr, _COMPLEX_INFINITY_FACTS)
    if isinstance(expr, ImaginaryUnit):
        return _facts(expr, _IMAGINARY_UNIT_FACTS)
    if isinstance(expr, NumberSymbol):
        values = _NUMBER_SYMBOL_FACTS.get(type(expr))
        if values is not None:
            return _facts(expr, values)
    return []


__all__ = ["number_facts"]
