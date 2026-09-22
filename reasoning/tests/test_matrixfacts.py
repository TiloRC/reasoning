from __future__ import annotations

import importlib

import pytest
from sympy.assumptions.ask import Q
from sympy.matrices import Matrix
from sympy.matrices.expressions import (
    BlockDiagMatrix, BlockMatrix, Determinant, Identity, MatrixSymbol,
    OneMatrix, Trace, ZeroMatrix,
)
from sympy.matrices.expressions.fourier import DFT

from reasoning.clauses import Formula, iter_atoms
from reasoning.matrixfacts import register_matrix_facts
from reasoning.predicates import AppliedPredicate as LocalAppliedPredicate
from reasoning.predicates import Q as LocalQ
from reasoning.registry import ClassFactRegistry
from reasoning.satask import satask
from reasoning.sathandlers import class_fact_registry

X = MatrixSymbol('X', 2, 2)
Y = MatrixSymbol('Y', 2, 3)
Z = MatrixSymbol('Z', 2, 2)
V1 = MatrixSymbol('V1', 2, 1)
A1x1 = MatrixSymbol('A1x1', 1, 1)
C0x0 = MatrixSymbol('C0x0', 0, 0)


def test_square_and_invertible_facts() -> None:
    assert satask(Q.square(X)) is True
    assert satask(Q.square(Y)) is False
    assert satask(Q.square(Y*Y.T)) is True
    assert satask(Q.square(A1x1)) is True
    assert satask(Q.square(C0x0)) is True

    assert satask(Q.invertible(X)) is None
    assert satask(Q.invertible(Y)) is False
    assert satask(Q.invertible(X*Y), Q.invertible(X)) is False
    assert satask(Q.invertible(X*Z), Q.invertible(X)) is None
    assert satask(Q.invertible(X*Z), Q.invertible(X) & Q.invertible(Z)) is True
    assert satask(Q.invertible(X.T)) is None
    assert satask(Q.invertible(X.T), Q.invertible(X)) is True
    assert satask(Q.invertible(X.I)) is True
    assert satask(Q.invertible(Identity(3))) is True
    assert satask(Q.invertible(ZeroMatrix(3, 3))) is False
    assert satask(Q.invertible(OneMatrix(1, 1))) is True
    assert satask(Q.invertible(OneMatrix(3, 3))) is False
    assert satask(Q.invertible(Matrix([[1, 2], [3, 4]]))) is True
    assert satask(Q.invertible(Matrix([[1, 2], [3, 6]]))) is False
    assert satask(Q.invertible(Matrix([[1, 2, 3], [3, 5, 4]]))) is False


def test_symmetric_diagonal_triangular_facts() -> None:
    assert satask(Q.symmetric(Y)) is False
    assert satask(Q.symmetric(Y*Y.T)) is True
    assert satask(Q.symmetric(Y.T*X*Y)) is None
    assert satask(Q.symmetric(Y.T*X*Y), Q.symmetric(X)) is True
    assert satask(Q.symmetric(X*Z), Q.symmetric(X)) is None
    assert satask(Q.symmetric(X*Z), Q.symmetric(X) & Q.symmetric(Z)) is True
    assert satask(Q.symmetric(X + Z), Q.symmetric(X) & Q.symmetric(Z)) is True
    assert satask(Q.symmetric(X**10), Q.symmetric(X)) is True
    assert satask(Q.symmetric(A1x1)) is True
    assert satask(Q.symmetric(V1.T*V1)) is True

    assert satask(Q.diagonal(X + Z.T + Identity(2)),
                  Q.diagonal(X) & Q.diagonal(Z)) is True
    assert satask(Q.diagonal(C0x0)) is True
    assert satask(Q.diagonal(A1x1)) is True
    assert satask(Q.diagonal(OneMatrix(1, 1))) is True
    assert satask(Q.diagonal(OneMatrix(3, 3))) is False
    assert satask(Q.diagonal(X**3), Q.diagonal(X)) is True

    assert satask(Q.upper_triangular(X + Z.T + Identity(2)),
                  Q.upper_triangular(X) & Q.lower_triangular(Z)) is True
    assert satask(Q.upper_triangular(X*Z.T),
                  Q.upper_triangular(X) & Q.lower_triangular(Z)) is True
    assert satask(Q.lower_triangular(Identity(3))) is True
    assert satask(Q.upper_triangular(ZeroMatrix(3, 3))) is True
    assert satask(Q.triangular(X), Q.unit_triangular(X)) is True


def test_fullrank_and_positive_definite_facts() -> None:
    assert satask(Q.fullrank(X**2), Q.fullrank(X)) is True
    assert satask(Q.fullrank(X.T), Q.fullrank(X)) is True
    assert satask(Q.fullrank(Y)) is None
    assert satask(Q.fullrank(Identity(3))) is True
    assert satask(Q.fullrank(ZeroMatrix(3, 3))) is False
    assert satask(Q.fullrank(OneMatrix(1, 1))) is True
    assert satask(Q.fullrank(OneMatrix(3, 3))) is False
    assert satask(Q.invertible(X), ~Q.fullrank(X)) is False

    assert satask(Q.positive_definite(X.T), Q.positive_definite(X)) is True
    assert satask(Q.positive_definite(X.I), Q.positive_definite(X)) is True
    assert satask(Q.positive_definite(Y)) is False
    assert satask(Q.positive_definite(X)) is None
    assert satask(Q.positive_definite(X + Z),
                  Q.positive_definite(X) & Q.positive_definite(Z)) is True
    assert satask(Q.positive_definite(-X), Q.positive_definite(X)) is None
    assert satask(Q.positive_definite(ZeroMatrix(3, 3))) is False
    assert satask(Q.positive_definite(OneMatrix(1, 1))) is True
    assert satask(Q.positive(X[1, 1]), Q.positive_definite(X)) is True


def test_orthogonal_and_unitary_facts() -> None:
    assert satask(Q.orthogonal(X.T), Q.orthogonal(X)) is True
    assert satask(Q.unitary(X.T), Q.unitary(X)) is True
    assert satask(Q.orthogonal(X.I), Q.orthogonal(X)) is True
    assert satask(Q.unitary(X**2), Q.unitary(X)) is True
    assert satask(Q.orthogonal(Y)) is False
    assert satask(Q.unitary(X)) is None
    assert satask(Q.unitary(X), ~Q.invertible(X)) is False
    assert satask(Q.unitary(X*Z*X), Q.unitary(X) & Q.unitary(Z)) is True
    assert satask(Q.unitary(Identity(3))) is True
    assert satask(Q.unitary(ZeroMatrix(3, 3))) is False
    assert satask(Q.invertible(X), Q.orthogonal(X)) is True
    assert satask(Q.orthogonal(X + Z),
                  Q.orthogonal(X) & Q.orthogonal(Z)) is None
    assert satask(Q.unitary(X), Q.orthogonal(X)) is True
    assert satask(Q.unitary(DFT(3))) is True


def test_element_facts() -> None:
    M = MatrixSymbol('M', 4, 4)
    assert satask(Q.real(M[1, 2]), Q.real_elements(M)) is True
    assert satask(Q.integer(M[1, 2]), Q.integer_elements(M)) is True
    assert satask(Q.complex(M[1, 2]), Q.complex_elements(M)) is True
    assert satask(Q.integer_elements(Identity(3))) is True
    assert satask(Q.integer_elements(ZeroMatrix(3, 3))) is True
    assert satask(Q.integer_elements(OneMatrix(3, 3))) is True
    assert satask(Q.complex_elements(DFT(3))) is True

    assert satask(Q.integer_elements(M[:, 3]), Q.integer_elements(M)) is True
    assert satask(Q.integer_elements(BlockMatrix([[M], [M]])),
                  Q.integer_elements(M)) is True
    assert satask(Q.integer(Determinant(M)), Q.integer_elements(M)) is True
    assert satask(Q.integer(Trace(M)), Q.integer_elements(M)) is True
    assert satask(Q.real_elements(Trace(M)), Q.real_elements(M)) is True
    assert satask(Q.real_elements(M.T), Q.real_elements(M)) is True
    assert satask(Q.real_elements(M.I),
                  Q.real_elements(M) & Q.invertible(M)) is True
    assert satask(Q.integer_elements(M.I), Q.integer_elements(M)) is None


def test_slice_and_block_facts() -> None:
    M = MatrixSymbol('M', 4, 4)
    B = M[1:3, 1:3]
    C = M[0:3, 1:3]
    assert satask(Q.symmetric(B), Q.symmetric(M)) is True
    assert satask(Q.invertible(B), Q.invertible(M)) is True
    assert satask(Q.diagonal(B), Q.diagonal(M)) is True
    assert satask(Q.orthogonal(B), Q.orthogonal(M)) is True
    assert satask(Q.upper_triangular(B), Q.upper_triangular(M)) is True
    assert satask(Q.symmetric(C), Q.symmetric(M)) is None
    assert satask(Q.invertible(C), Q.invertible(M)) is None
    assert satask(Q.diagonal(C), Q.diagonal(M)) is None
    assert satask(Q.orthogonal(C), Q.orthogonal(M)) is None
    assert satask(Q.upper_triangular(C), Q.upper_triangular(M)) is None

    assert satask(Q.invertible(BlockMatrix([Identity(3)]))) is True
    assert satask(Q.invertible(BlockMatrix([ZeroMatrix(3, 3)]))) is False
    assert satask(Q.invertible(BlockDiagMatrix(Identity(3), Identity(5)))) is True
    assert satask(Q.invertible(
        BlockDiagMatrix(ZeroMatrix(3, 3), Identity(5)))) is False
    assert satask(Q.invertible(
        BlockDiagMatrix(Identity(3), OneMatrix(5, 5)))) is False


def test_trace_and_determinant_positivity() -> None:
    M = MatrixSymbol('M', 4, 4)
    assert satask(Q.positive(Trace(M)), Q.positive_definite(M)) is True
    assert satask(Q.positive(Determinant(M)), Q.positive_definite(M)) is True


def test_matrix_facts_register_local_predicate_formulas() -> None:
    expression = Y*Y.T
    registry = ClassFactRegistry()
    register_matrix_facts(registry)
    registered = registry(expression)
    assert registered
    for fact in registered:
        assert isinstance(fact, (Formula, LocalAppliedPredicate))
        for atom in iter_atoms(fact):
            assert isinstance(atom, LocalAppliedPredicate)
    assert registered <= class_fact_registry(expression)

    atoms = [atom for fact in registered for atom in iter_atoms(fact)]
    assert LocalQ.square(expression) in atoms
    assert LocalQ.invertible(expression) in atoms


def test_matrix_facts_do_not_query_old_assumptions(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assumptions = importlib.import_module("sympy.core.assumptions")

    def fail(fact: str, obj: object) -> bool:
        raise AssertionError(f"old assumptions queried for {fact!r}")

    monkeypatch.setattr(assumptions, "_ask", fail)

    assert satask(Q.square(X)) is True
    assert satask(Q.invertible(Y)) is False
    assert satask(Q.invertible(Matrix([[1, 2], [3, 4]]))) is True
    assert satask(Q.invertible(Matrix([[1, 2], [3, 6]]))) is False
    assert satask(Q.symmetric(Y*Y.T)) is True
    assert satask(Q.diagonal(X + Z.T + Identity(2)),
                  Q.diagonal(X) & Q.diagonal(Z)) is True
    assert satask(Q.real_elements(X.T), Q.real_elements(X)) is True
    assert satask(Q.positive(Trace(X)), Q.positive_definite(X)) is True
