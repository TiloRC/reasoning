"""Regression tests for domain guards on the Pow facts.

``0**negative`` is complex infinity, ``0**0`` is 1, and ``0**non-real`` is
undefined, so a Pow rule that treats the power as an ordinary complex,
algebraic, finite, or hermitian value must either require a nonzero base or
restrict the exponent to the real nonnegative (or otherwise non-singular)
case.  Each test below fails on the unguarded handlers.
"""
from __future__ import annotations

from sympy import I, Q, pi, symbols, sqrt
from sympy.functions.combinatorial.factorials import factorial
from sympy.logic.boolalg import Not

from reasoning.clauses import iter_atoms
from reasoning.predicates import Q as LocalQ
from reasoning.satask import satask
from reasoning.sathandlers import _pow_real_facts

x, y, n = symbols('x y n')


def test_not_complex_inverse_does_not_force_nonzero() -> None:
    # x = 0 satisfies ~Q.complex(1/x) (1/0 is zoo) and makes Q.zero(x) true,
    # so a definite False would be unsound.
    assert satask(Q.zero(x), Not(Q.complex(1/x))) is None
    assert satask(Q.complex(1/x), Q.complex(x)) is None


def test_pow_closures_require_regular_base_or_exponent() -> None:
    assert satask(Q.zero(x), Not(Q.algebraic(1/x))) is None
    assert satask(Q.zero(x), Not(Q.finite(1/x))) is None
    assert satask(Q.zero(x), Not(Q.hermitian(1/x))) is None
    assert satask(Q.complex(x**y), Q.complex(x) & Q.complex(y)) is None
    assert satask(Q.algebraic(x**y), Q.algebraic(x) & Q.rational(y)) is None
    assert satask(Q.hermitian(x**y), Q.hermitian(x) & Q.integer(y)) is None
    assert satask(Q.finite(x**y),
                  Q.finite(x) & Q.finite(y) & Q.zero(x)) is None


def test_pow_closures_keep_nonzero_base_answers() -> None:
    assert satask(Q.complex(1/x), Q.complex(x) & Q.nonzero(x)) is True
    assert satask(Q.algebraic(1/x), Q.algebraic(x) & Q.nonzero(x)) is True
    assert satask(Q.finite(1/x), Q.finite(x) & Q.nonzero(x)) is True
    assert satask(Q.complex(x**y),
                  Q.complex(x) & Q.complex(y) & Q.nonzero(x)) is True
    assert satask(Q.algebraic(x**y),
                  Q.algebraic(x) & Q.rational(y) & Q.nonzero(x)) is True
    assert satask(Q.hermitian(x**y),
                  Q.hermitian(x) & Q.integer(y) & Q.nonzero(x)) is True


def test_pow_real_rules_require_nonzero_exponent() -> None:
    atoms = set(iter_atoms(_pow_real_facts(x**y)))
    assert LocalQ.zero(y) in atoms
    assert satask(Q.real(5**(2*I*pi*n)), Q.integer(n)) is None
    assert satask(Q.real(5**(2*I*pi*n)),
                  Q.integer(n) & Q.nonzero(n)) is False


def test_pow_real_and_finite_rules_reject_singular_powers() -> None:
    assert satask(Q.real(1/sqrt(x)), Q.real(x) & Q.zero(x)) is None
    assert satask(Q.finite(x**I), Q.zero(x)) is None


def test_pow_antihermitian_guards() -> None:
    assert satask(Q.antihermitian(x**y),
                  Q.antihermitian(x) & Q.even(y)) is None
    assert satask(Q.antihermitian(x**y),
                  Q.antihermitian(x) & Q.odd(y)) is None
    assert satask(Q.antihermitian(x**y),
                  Q.antihermitian(x) & Q.odd(y) & Not(Q.zero(x))) is True
    assert satask(Q.antihermitian(x**y),
                  Q.antihermitian(x) & Q.even(y) & Not(Q.zero(x))) is False


def test_factorial_integer_requires_nonnegative_argument() -> None:
    # factorial(-1) is zoo, so integer alone is not enough.
    assert satask(Q.integer(factorial(x)), Q.integer(x)) is None
    assert satask(Q.integer(factorial(x)),
                  Q.integer(x) & Q.nonnegative(x)) is True
