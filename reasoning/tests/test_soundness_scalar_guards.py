"""Regression tests for the scalar domain guards.

Each test pins one guard added to ``reasoning/sathandlers.py`` or
``reasoning/functionfacts.py``: a rule that used to ignore a singularity or an
infinite value now either requires the finite/nonzero domain in which it is
sound or is restricted to its sound direction.  The second half of every test
checks that the guard did not remove the inference it was meant to keep.
"""
from __future__ import annotations

from sympy import (
    Abs, E, I, Pow, Q, S, acos, exp, im, log, oo, re, symbols,
)
from sympy.logic.boolalg import Not

from reasoning.satask import satask

x, y = symbols('x y')
xi = symbols('xi', infinite=True)
yi = symbols('yi', integer=True, negative=True)


def test_imaginary_sum_needs_a_nonzero_real_part() -> None:
    # x = I, y = -I gives x + y == 0, so the closed-group rule cannot infer
    # imaginary(x + y); antihermitian is the sound closure (zero is
    # antihermitian).
    assumptions = Q.imaginary(x) & Q.imaginary(y)
    assert satask(Q.real(x + y), assumptions) is None
    assert satask(Q.imaginary(x + y), assumptions) is None
    assert satask(Q.antihermitian(x + y), assumptions) is True

    # The one-real-argument direction needs that argument nonzero: x = 0
    # leaves x + I purely imaginary.
    assert satask(Q.imaginary(x + y), Q.imaginary(x) & Q.real(y)) is None
    assert satask(Q.imaginary(x + y),
                  Q.imaginary(x) & Q.real(y) & Q.nonzero(y)) is False


def test_acos_positivity_excludes_one() -> None:
    # acos(1) == 0 is not positive, so the upper end must be excluded.
    assert satask(Q.positive(acos(x)), Q.zero(x - 1)) is not True
    assert satask(Q.positive(acos(x)),
                  Q.nonnegative(x + 1) & Q.negative(x - 1)) is True


def test_function_facts_require_finite_arguments() -> None:
    # exp(oo) == oo and exp(-oo) == 0, re(oo) == oo, im(zoo) == nan, and
    # Abs(oo) == oo.
    assert satask(Q.finite(exp(x)), Q.infinite(x)) is None
    assert satask(Q.finite(E**x), Q.infinite(x)) is None
    assert satask(Q.complex(exp(x)), Q.finite(x)) is True

    assert satask(Q.finite(re(x)), Q.infinite(x)) is not True
    assert satask(Q.finite(im(x)), Q.infinite(x)) is None
    assert satask(Q.real(re(x)), Q.finite(x)) is True
    assert satask(Q.real(im(x)), Q.finite(x)) is True

    assert satask(Q.finite(Abs(x)), ~Q.finite(x)) is not True
    assert satask(Q.nonnegative(Abs(x)), Q.finite(x)) is True
    assert satask(Q.positive(Abs(x)), ~Q.zero(x)) is None
    assert satask(Q.positive(Abs(x)), ~Q.zero(x) & Q.finite(x)) is True


def test_unbounded_function_assumptions_are_satisfiable() -> None:
    # Every assumption has a model (x = oo, x = zoo, x = 0 for log), so it
    # must not raise, and positive(x) is false in those models.
    for assumption in (
            ~Q.finite(exp(x)), ~Q.finite(Abs(x)), ~Q.finite(re(x)),
            ~Q.finite(im(x)), ~Q.finite(Abs(log(x))), ~Q.complex(exp(x)),
            ~Q.complex(Abs(x)), ~Q.complex(re(x)), ~Q.real(re(x))):
        assert satask(Q.positive(x), assumption) is not True


def test_infinite_base_negative_exponent_is_zero() -> None:
    # xi = oo, yi = -1 gives oo**-1 == 0.
    assert satask(Q.zero(xi**yi)) is True
    assert satask(Q.rational(xi**yi)) is not False


def test_pow_zero_exponent_is_one() -> None:
    # oo**0 == 1, so the power is complex and rational but not zero.
    assumptions = Q.infinite(x) & Q.zero(y)
    assert satask(Q.zero(x**y), assumptions) is False
    assert satask(Q.complex(x**y), assumptions) is not False
    assert satask(Q.rational(x**y), assumptions) is not False

    assert satask(Q.complex(Pow(oo, 0, evaluate=False))) is not False
    assert satask(Q.real(Pow(S(2), S.Zero, evaluate=False))) is not False


def test_zero_base_pow_values_are_not_refuted() -> None:
    # 0**oo == 0, 0**(1+I) == 0 and oo**-1 == 0.
    assert satask(Q.zero(Pow(S.Zero, oo, evaluate=False))) is not False
    assert satask(Q.zero(Pow(S.Zero, 1 + I, evaluate=False))) is not False
    assert satask(Q.zero(Pow(oo, -1, evaluate=False))) is True


def test_finite_nonzero_pow_stays_nonzero() -> None:
    # The zero equivalence was replaced by guarded directions; the nonzero
    # base direction still refutes a zero power.
    assert satask(Q.zero(x**y), Q.finite(x) & ~Q.zero(x) & Q.finite(y)) is False
    assert satask(Q.zero(x**y), Q.zero(x)) is None


def test_zero_product_requires_finite_factors() -> None:
    # oo*0 == nan, so a zero factor only makes the product zero when the
    # other factors are finite; the converse still refutes a zero factor
    # from a nonzero product.
    assert satask(Q.zero(x*y), Q.zero(y) & Q.infinite(x)) is None
    assert satask(Q.zero(x*y), Q.zero(y) & Q.finite(x)) is True
    assert satask(Q.zero(x) | Q.zero(y), Q.nonzero(x*y)) is False


def test_pow_antihermitian_parity_needs_nonzero_base() -> None:
    # x = 0 is antihermitian and 0**2 == 0 is antihermitian too.
    assert satask(Q.antihermitian(x**2), Q.antihermitian(x)) is None
    assert satask(Q.antihermitian(x**2),
                  Q.antihermitian(x) & Not(Q.zero(x))) is False


def test_pow_complex_closure_needs_a_positive_integer_exponent() -> None:
    # oo**0 == 1 and oo**-1 == 0 are complex, while oo**2 is not.
    assert satask(Q.complex(Pow(oo, 0, evaluate=False))) is not False
    assert satask(Q.complex(Pow(oo, 2, evaluate=False))) is False
    assert satask(Q.complex(x**2), ~Q.complex(x)) is False
