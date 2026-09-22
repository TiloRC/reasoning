"""Soundness regressions for zero-base power singularities.

The Pow class facts used to close ``complex`` and ``algebraic`` over every
complex/algebraic base and rational exponent:

* ``complex(base) -> complex(base**exp)`` in ``_pow_closure_facts``
* ``algebraic(base) & rational(exp) -> algebraic(base**exp)`` in
  ``_pow_algebraic_facts``

Both are unsound when the base can be zero and the exponent negative:
``0**-1`` is ``zoo``, which is neither complex nor algebraic.  The sound
form adds the same definedness guard the ``extended_real`` rule in
``_pow_closure_facts`` already used::

    OR(NOT(Q.zero(base)), NOT(Q.negative(exp)))

The counterexample that exposed this is ``satask(Q.zero(x), ~Q.complex(1/x))``
returning ``False``: the unguarded closure derives ``complex(x) -> complex(1/x)``,
contraposition gives ``~complex(1/x) -> ~complex(x)``, and ``zero -> complex``
turns that into ``~zero(x)``.  ``x = 0`` satisfies the assumption (``1/0 = zoo``
is not complex) and makes ``Q.zero(x)`` true, so the answer was unsound.

These tests pin both directions: no inference may pass through the
singularity, and the inference must still fire for zero and positive rational
exponents, where ``0**0 == 1`` and ``0**(p/q) == 0`` are defined.  See
``agent-reports/2026-09-22-sathandlers-soundness-root-cause.md``.
"""
from __future__ import annotations

from sympy import Pow, Q, Rational, symbols

from reasoning.satask import satask

x = symbols('x')


def test_reciprocal_counterexample_is_not_refuted() -> None:
    # Fuzzer counterexample: x = 0 satisfies ~complex(1/x) and is zero.
    # The unguarded closure answered False for Q.zero(x).
    assert satask(Q.zero(x), ~Q.complex(1/x)) is None
    assert satask(Q.zero(x), ~Q.algebraic(1/x)) is None


def test_complex_closure_needs_a_defined_power() -> None:
    # 0**-1 and 0**-2 are zoo, so the closure must stay undecided for a base
    # that may be zero.
    assert satask(Q.complex(1/x), Q.complex(x)) is None
    assert satask(Q.complex(x**-2), Q.complex(x)) is None


def test_algebraic_closure_needs_a_defined_power() -> None:
    assert satask(Q.algebraic(1/x), Q.algebraic(x)) is None
    assert satask(Q.algebraic(x**-2), Q.algebraic(x)) is None


def test_nonnegative_rational_exponents_still_close() -> None:
    # 0**(1/2) == 0 and 0**(3/2) == 0 are defined, so the guard must allow
    # nonnegative exponents even when the base can be zero.
    assert satask(Q.complex(x**Rational(1, 2)), Q.complex(x)) is True
    assert satask(Q.complex(x**Rational(3, 2)), Q.complex(x)) is True
    assert satask(Q.algebraic(x**Rational(1, 2)), Q.algebraic(x)) is True
    assert satask(Q.algebraic(x**Rational(3, 2)), Q.algebraic(x)) is True


def test_zero_exponent_is_defined_for_every_base() -> None:
    # 0**0 == 1, so an explicit zero exponent must not be treated as a
    # singularity.
    zero_power = Pow(x, 0, evaluate=False)
    assert satask(Q.complex(zero_power), Q.complex(x)) is True
    assert satask(Q.algebraic(zero_power), Q.algebraic(x)) is True


def test_nonzero_base_still_closes() -> None:
    assert satask(Q.complex(1/x), Q.complex(x) & ~Q.zero(x)) is True
    assert satask(Q.complex(x**-2), Q.complex(x) & Q.nonzero(x)) is True
    assert satask(Q.algebraic(1/x), Q.algebraic(x) & ~Q.zero(x)) is True
    assert satask(Q.algebraic(x**-2), Q.algebraic(x) & ~Q.zero(x)) is True


def test_nonreal_nonzero_base_still_closes() -> None:
    # The guard has to be ``~Q.zero``, not ``Q.nonzero``: an imaginary base
    # is not "nonzero" in SymPy's sense, but ``1/I == -I`` is still complex.
    assert satask(Q.complex(1/x), Q.imaginary(x) & ~Q.zero(x)) is True


def test_finiteness_does_not_leak_through_the_closure() -> None:
    # Same chain: complex(1/x) would imply finite(1/x), but 1/0 is zoo, which
    # is infinite.  These are soundness assertions, not exact answers.
    assert satask(Q.finite(1/x), Q.zero(x)) is not True
    assert satask(Q.infinite(1/x), Q.zero(x)) is not False
