"""Adversarial soundness tests for the ``satask`` handler facts.

Every test here encodes a query whose definite ``satask`` answer is contradicted
by a concrete model, found either by ``tools/check_soundness.py`` or by
targeted probing of the handler fact families.  The assertions check the
*sound* answer (``None`` when both polarities have a model, otherwise the
direction the models force), so most tests are expected to fail until the
underlying facts are fixed.  Models and the value each expression takes are
listed in the comments.

Sections
--------
* ``Findings``: definite answers that ``sympy.ask`` does not share, so the
  soundness fuzzer reports them without ``--strict``.
* ``Spurious inconsistencies``: satisfiable assumptions that make ``satask``
  raise ``Inconsistent assumptions``.
* ``Matrix facts``: concrete-matrix counterexamples.  ``sympy.ask`` does not
  decide element predicates of explicit matrices, so these models were checked
  by evaluating the substituted expression directly.
* ``Upstream-shared blind spots``: counterexamples that ``sympy.ask`` happens
  to share (reported by ``tools/check_soundness.py --strict``) but that a fix
  for the two known Pow rules leaves in place.
"""
from __future__ import annotations

from sympy import (
    Abs, E, I, Pow, Q, Rational, S, acos, exp, factorial, im, log, oo, re,
    symbols,
)
from sympy.matrices.expressions import HadamardProduct, MatPow, MatrixSlice
from sympy.matrices.expressions.matexpr import MatrixSymbol
from sympy.matrices.expressions.special import ZeroMatrix

from reasoning.satask import satask

x, y, z = symbols("x y z")
n = symbols("n", integer=True)
xi = symbols("xi", infinite=True)
yi = symbols("yi", integer=True, negative=True)
A, B = MatrixSymbol("A", 2, 2), MatrixSymbol("B", 2, 2)


# --------------------------------------------------------------------------
# Findings: sympy.ask does not share the definite answer
# --------------------------------------------------------------------------

def test_imaginary_sum_cancellation_does_not_imply_not_real() -> None:
    # x = I, y = -I satisfies the assumptions and x + y = 0, which is real,
    # extended real, integer, rational, zero, even, nonnegative and
    # nonpositive; x = y = I gives 2*I, so the opposite answers are unsound
    # too.  The ``imaginary(x + y)`` conclusion is upstream-shared, but these
    # consequences are not.
    assumptions = Q.imaginary(x) & Q.imaginary(y)
    assert satask(Q.real(x + y), assumptions) is None
    assert satask(Q.extended_real(x + y), assumptions) is None
    assert satask(Q.integer(x + y), assumptions) is None
    assert satask(Q.rational(x + y), assumptions) is None
    assert satask(Q.zero(x + y), assumptions) is None
    assert satask(Q.even(x + y), assumptions) is None
    assert satask(Q.nonnegative(x + y), assumptions) is None
    assert satask(Q.nonpositive(x + y), assumptions) is None


def test_acos_positivity_interval_excludes_one() -> None:
    # x = 1 satisfies Q.zero(x - 1), and acos(1) == 0 is not positive.
    assert satask(Q.positive(acos(x)), Q.zero(x - 1)) is not True


def test_factorial_integer_needs_nonnegative_argument() -> None:
    # n = -1 gives factorial(-1) == zoo, which is not an integer; n = 2 gives
    # 2, so the answer is undetermined.
    assert satask(Q.integer(factorial(n)), Q.integer(n)) is None


def test_finite_of_unbounded_arguments() -> None:
    # x = oo gives exp(x) == oo and re(x) == oo, neither finite; x = -oo gives
    # exp(-oo) == 0, and im(zoo) == nan, so those queries are undetermined.
    assert satask(Q.finite(exp(x)), Q.infinite(x)) is None
    assert satask(Q.finite(E**x), Q.infinite(x)) is None
    assert satask(Q.finite(re(x)), Q.infinite(x)) is not True
    assert satask(Q.finite(im(x)), Q.infinite(x)) is None


def test_infinite_base_negative_integer_exponent_is_zero() -> None:
    # xi = oo and yi = -1 satisfy the declared assumptions and xi**yi == 0,
    # so the expression is both zero and rational.
    assert satask(Q.zero(xi**yi)) is not False
    assert satask(Q.rational(xi**yi)) is not False


# --------------------------------------------------------------------------
# Spurious inconsistencies
# --------------------------------------------------------------------------

def test_unbounded_function_arguments_do_not_make_assumptions_inconsistent() -> None:
    # x = oo satisfies each assumption below (exp(oo) == oo, re(oo) == oo,
    # im(zoo) == nan, Abs(oo) == oo, Abs(log(0)) == oo, ...), so raising
    # ``Inconsistent assumptions`` is a bug; positive(x) is false for every
    # satisfying model because positive implies finite.
    assumptions = [
        ~Q.finite(exp(x)),
        ~Q.finite(Abs(x)),
        ~Q.finite(re(x)),
        ~Q.finite(im(x)),
        ~Q.finite(Abs(log(x))),
        ~Q.complex(exp(x)),
        ~Q.complex(Abs(x)),
        ~Q.complex(re(x)),
        ~Q.real(re(x)),
    ]
    for assumption in assumptions:
        assert satask(Q.positive(x), assumption) is not True


def test_infinite_base_zero_exponent_does_not_raise() -> None:
    # x = oo, y = 0 satisfies the assumptions and x**y == 1, so the query is
    # complex and rational but not zero.  ``Q.rational(x**y)`` is provable
    # from ``_pow_rational_facts`` while ``_pow_closure_facts`` claims the
    # expression is not complex, which makes the whole fact set inconsistent.
    assumptions = Q.infinite(x) & Q.zero(y)
    assert satask(Q.complex(x**y), assumptions) is not False
    assert satask(Q.rational(x**y), assumptions) is not False
    assert satask(Q.zero(x**y), assumptions) is False


def test_unevaluated_pow_zero_exponent_does_not_raise() -> None:
    # oo**0 == 1 and 2**0 == 1.
    assert satask(Q.complex(Pow(oo, 0, evaluate=False))) is not False
    assert satask(Q.real(Pow(S(2), S.Zero, evaluate=False))) is not False


# --------------------------------------------------------------------------
# Matrix facts
# --------------------------------------------------------------------------

def test_zeromatrix_shape_is_not_always_square() -> None:
    # ZeroMatrix(2, 3) is not square; sympy.ask agrees.
    assert satask(Q.square(ZeroMatrix(2, 3))) is not True


def test_matpow_negative_exponent_does_not_preserve_integer_elements() -> None:
    # A = [[2, 0], [0, 1]] has integer elements and is invertible, but
    # A**-2 == [[1/4, 0], [0, 1]] is not integral.  A = I is integral, so the
    # answer is undetermined.
    assert satask(Q.integer_elements(MatPow(A, -2)),
                  Q.integer_elements(A) & Q.invertible(A)) is None


def test_matmul_element_predicates_are_not_closed_under_negation() -> None:
    # A = diag(1/2, 1), B = diag(2, 1): A*B == I has integer elements even
    # though A does not, so the negative direction is unsound.
    assert satask(Q.integer_elements(A*B), ~Q.integer_elements(A)) is None
    # A = i*I, B = [[0, i], [-i, 0]]: A*B == [[0, -1], [1, 0]] is real even
    # though neither factor has real elements.
    assert satask(Q.real_elements(A*B),
                  ~Q.real_elements(A) & ~Q.real_elements(B)) is None


def test_matadd_element_predicates_are_not_closed_under_negation() -> None:
    # A = B = diag(1/2, 1) gives A + B == diag(1, 2), which is integral even
    # though neither summand is; A = i*I, B = -i*I gives A + B == 0, real.
    assert satask(Q.integer_elements(A + B),
                  ~Q.integer_elements(A) & ~Q.integer_elements(B)) is None
    assert satask(Q.real_elements(A + B),
                  ~Q.real_elements(A) & ~Q.real_elements(B)) is None


def test_hadamard_element_predicates_are_not_closed_under_negation() -> None:
    # A = diag(1/2, 1), B = diag(2, 1): the Hadamard product is I, integral
    # even though A is not.
    assert satask(Q.integer_elements(HadamardProduct(A, B)),
                  ~Q.integer_elements(A)) is None


def test_matrix_slice_does_not_transfer_fullrank() -> None:
    # A = [[0, 1], [1, 0]] is full rank, but its leading 1x1 slice [[0]] is
    # not; A = I gives a full rank slice, so the answer is undetermined.
    slice_ = MatrixSlice(A, slice(0, 1), slice(0, 1))
    assert satask(Q.fullrank(slice_), Q.fullrank(A)) is None


def test_antihermitian_pow_with_zero_capable_hermitian_base() -> None:
    # z = I gives re(z)**2 == 0, which is antihermitian, while z = 1 gives 1,
    # which is not; the local rule claims False.  ``sympy.ask`` shares the
    # atomic answer, but not the composite one the fuzzer shrank to.
    assert satask(Q.antihermitian(re(z)**2)) is None
    proposition = ~Q.prime(S.Pi) ^ Q.antihermitian(re(z)**2)
    assert satask(proposition, Q.algebraic(0)) is None


def test_zero_symbol_pow_does_not_raise() -> None:
    # xz**3 == 0 is antihermitian, and 1/xz == zoo is not; the mixed
    # hermitian/antihermitian Pow rules make the fact set inconsistent.
    xz = symbols("xz", zero=True)
    assert satask(Q.antihermitian(xz**3)) is not False
    assert satask(Q.antihermitian(1/xz)) is not True


# --------------------------------------------------------------------------
# Zero-base Pow singularities beyond the known 1/x case
# --------------------------------------------------------------------------

def test_zero_base_negative_exponent_is_not_algebraic_or_complex() -> None:
    # x**(-1) == zoo is neither algebraic nor complex when x = 0, and the same
    # holds for a negative exponent or a negative even root.
    assert satask(Q.algebraic(x**-1), Q.zero(x)) is not True
    assert satask(Q.complex(x**-1), Q.zero(x)) is not True
    assert satask(Q.complex(x**y), Q.zero(x) & Q.negative(y)) is not True
    assert satask(Q.algebraic(x**Rational(-1, 2)), Q.zero(x)) is not True


def test_zero_base_pow_values_are_not_answered_false() -> None:
    # 0**oo == 0, 0**(1+I) == 0 and oo**-1 == 0, so none of these is not zero.
    assert satask(Q.zero(Pow(S.Zero, oo, evaluate=False))) is not False
    assert satask(Q.zero(Pow(S.Zero, 1 + I, evaluate=False))) is not False
    assert satask(Q.zero(Pow(oo, -1, evaluate=False))) is not False


# --------------------------------------------------------------------------
# Upstream-shared blind spots: --strict reports these; a narrow Pow guard
# (complex closure + algebraic closure) does not remove any of them.
# --------------------------------------------------------------------------

def test_narrow_guard_blind_spots_for_zero_base() -> None:
    # 0**I == nan is not complex, real or finite; 0**(-1) == zoo is not
    # hermitian.  The complex closure guard only excludes real negative
    # exponents, and the other rules have no singularity guard at all.
    assert satask(Q.complex(x**I), Q.zero(x)) is not True
    assert satask(Q.real(x**Rational(-1, 2)), Q.zero(x)) is not True
    assert satask(Q.finite(x**I), Q.zero(x)) is not True
    assert satask(Q.hermitian(x**-1), Q.zero(x)) is not True


def test_narrow_guard_blind_spots_for_mul_and_pow_parity() -> None:
    # x = oo, y = 0 gives x*y == nan, which is not zero, and x = 0 with
    # x antihermitian gives x**2 == 0, which is antihermitian; both answers
    # are shared with sympy.ask.
    assert satask(Q.zero(x*y), Q.zero(y) & Q.infinite(x)) is not True
    assert satask(Q.antihermitian(x**2), Q.antihermitian(x)) is None
