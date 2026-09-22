"""Soundness regressions for the structural matrix facts.

Each guard is paired with the positive rule it must keep, so dropping a guard
or removing the sound direction fails here:

* ``ZeroMatrix`` only reports the shape-dependent predicates when it is square.
* ``MatPow`` keeps ``integer_elements`` for nonnegative integer exponents and
  drops it for negative ones (``diag(2, 1)**-2 == diag(1/4, 1)``).
* ``MatAdd``, ``MatMul`` and ``HadamardProduct`` only close the element
  predicates in the positive direction (sums and products can cancel
  fractional or imaginary parts).
* A proper principal submatrix inherits the size-independent predicates but
  not the rank-like ones: ``[[0]]`` is the leading slice of the full-rank,
  invertible, orthogonal ``[[0, 1], [1, 0]]``.  A slice covering the whole
  parent keeps them.
"""
from __future__ import annotations

from sympy import Q, Symbol
from sympy.matrices.expressions import (
    HadamardProduct, MatPow, MatrixSlice, MatrixSymbol, ZeroMatrix,
)

from reasoning.satask import satask

A = MatrixSymbol("A", 2, 2)
B = MatrixSymbol("B", 2, 2)
M = MatrixSymbol("M", 4, 4)


def test_zeromatrix_shape_dependent_predicates_need_square() -> None:
    assert satask(Q.square(ZeroMatrix(2, 3))) is False
    assert satask(Q.symmetric(ZeroMatrix(2, 3))) is False
    assert satask(Q.invertible(ZeroMatrix(2, 3))) is False
    assert satask(Q.fullrank(ZeroMatrix(2, 3))) is False
    # Entry predicates do not depend on the shape.
    assert satask(Q.integer_elements(ZeroMatrix(2, 3))) is True


def test_zeromatrix_square_facts_are_kept() -> None:
    assert satask(Q.square(ZeroMatrix(3, 3))) is True
    assert satask(Q.symmetric(ZeroMatrix(3, 3))) is True
    assert satask(Q.diagonal(ZeroMatrix(3, 3))) is True
    assert satask(Q.upper_triangular(ZeroMatrix(3, 3))) is True
    assert satask(Q.lower_triangular(ZeroMatrix(3, 3))) is True
    assert satask(Q.integer_elements(ZeroMatrix(3, 3))) is True


def test_matpow_negative_integer_exponent_drops_integer_elements() -> None:
    assumptions = Q.integer_elements(A) & Q.invertible(A)
    assert satask(Q.integer_elements(MatPow(A, -2)), assumptions) is None
    e = Symbol("e")
    assert satask(Q.integer_elements(MatPow(A, e)),
                  assumptions & Q.integer(e) & Q.negative(e)) is None
    # Inversion still preserves real and complex elements.
    assert satask(Q.real_elements(MatPow(A, -2)),
                  Q.real_elements(A) & Q.invertible(A)) is True
    assert satask(Q.complex_elements(MatPow(A, -2)),
                  Q.complex_elements(A) & Q.invertible(A)) is True


def test_matpow_nonnegative_integer_exponent_keeps_integer_elements() -> None:
    e = Symbol("e")
    assert satask(Q.integer_elements(MatPow(A, 2)),
                  Q.integer_elements(A)) is True
    assert satask(Q.integer_elements(MatPow(A, e)),
                  Q.integer_elements(A) & Q.integer(e)
                  & Q.nonnegative(e)) is True


def test_matmul_element_closures_keep_only_positive_direction() -> None:
    assert satask(Q.integer_elements(A*B), ~Q.integer_elements(A)) is None
    assert satask(Q.real_elements(A*B),
                  ~Q.real_elements(A) & ~Q.real_elements(B)) is None
    assert satask(Q.integer_elements(A*B),
                  Q.integer_elements(A) & Q.integer_elements(B)) is True
    assert satask(Q.real_elements(A*B),
                  Q.real_elements(A) & Q.real_elements(B)) is True
    assert satask(Q.complex_elements(A*B),
                  Q.complex_elements(A) & Q.complex_elements(B)) is True


def test_matadd_element_closures_keep_only_positive_direction() -> None:
    assert satask(Q.integer_elements(A + B),
                  ~Q.integer_elements(A) & ~Q.integer_elements(B)) is None
    assert satask(Q.real_elements(A + B),
                  ~Q.real_elements(A) & ~Q.real_elements(B)) is None
    assert satask(Q.integer_elements(A + B),
                  Q.integer_elements(A) & Q.integer_elements(B)) is True
    assert satask(Q.real_elements(A + B),
                  Q.real_elements(A) & Q.real_elements(B)) is True
    assert satask(Q.complex_elements(A + B),
                  Q.complex_elements(A) & Q.complex_elements(B)) is True


def test_hadamard_element_closures_keep_only_positive_direction() -> None:
    assert satask(Q.integer_elements(HadamardProduct(A, B)),
                  ~Q.integer_elements(A)) is None
    assert satask(Q.real_elements(HadamardProduct(A, B)),
                  ~Q.real_elements(A) & ~Q.real_elements(B)) is None
    assert satask(Q.integer_elements(HadamardProduct(A, B)),
                  Q.integer_elements(A) & Q.integer_elements(B)) is True
    assert satask(Q.real_elements(HadamardProduct(A, B)),
                  Q.real_elements(A) & Q.real_elements(B)) is True


def test_proper_principal_slice_does_not_inherit_rank_predicates() -> None:
    slice_ = MatrixSlice(A, slice(0, 1), slice(0, 1))
    assert satask(Q.fullrank(slice_), Q.fullrank(A)) is None
    assert satask(Q.fullrank(slice_), Q.invertible(A)) is None
    assert satask(Q.invertible(slice_), Q.invertible(A)) is None
    assert satask(Q.unitary(slice_), Q.unitary(A)) is None
    assert satask(Q.orthogonal(slice_), Q.orthogonal(A)) is None


def test_proper_principal_slice_keeps_size_independent_predicates() -> None:
    slice_ = M[1:3, 1:3]
    assert satask(Q.symmetric(slice_), Q.symmetric(M)) is True
    assert satask(Q.diagonal(slice_), Q.diagonal(M)) is True
    assert satask(Q.upper_triangular(slice_), Q.upper_triangular(M)) is True
    assert satask(Q.lower_triangular(slice_), Q.lower_triangular(M)) is True
    assert satask(Q.positive_definite(slice_),
                  Q.positive_definite(M)) is True
    assert satask(Q.integer_elements(slice_), Q.integer_elements(M)) is True


def test_full_parent_slice_keeps_rank_predicates() -> None:
    slice_ = MatrixSlice(A, slice(0, 2), slice(0, 2))
    assert satask(Q.fullrank(slice_), Q.fullrank(A)) is True
    assert satask(Q.invertible(slice_), Q.invertible(A)) is True
    assert satask(Q.unitary(slice_), Q.unitary(A)) is True
    assert satask(Q.orthogonal(slice_), Q.orthogonal(A)) is True
