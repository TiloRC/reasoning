"""Facts about matrix expressions from direct structural inspection.

This module extends :mod:`reasoning.numberfacts` and
:mod:`reasoning.functionfacts` from scalars to the matrix expression classes.
Like those modules it never reads SymPy's old assumptions: the class of an
expression selects a rule, and each rule is a lightweight formula over
predicate applications whose arguments the discovery loop can visit.  Rules
that mention a structural subexpression (a transpose argument, a power base, a
block or a slice parent) hand that subexpression to the discovery loop as a new
subject, so the facts about it are found in a later round.

Some facts are deliberately omitted where the pinned query suite expects an
unknown answer: non-square slices do not report their shape as square, because
``symmetric`` would then be forced to ``False`` through the imported known
facts; sums of orthogonal or unitary matrices get no closure rule; and
``fullrank`` is not reported for a non-square ``MatrixSymbol``.
"""
from __future__ import annotations

from typing import Callable, Iterable

from sympy.core.numbers import Integer, Number
from sympy.matrices import MatrixBase
from sympy.matrices.expressions import (
    BlockDiagMatrix, BlockMatrix, Determinant, DiagMatrix, DiagonalMatrix,
    HadamardProduct, Identity, Inverse, MatAdd, MatMul, MatPow, MatrixExpr,
    MatrixSlice, MatrixSymbol, OneMatrix, Trace, Transpose, ZeroMatrix,
)
from sympy.matrices.expressions.factorizations import Factorization
from sympy.matrices.expressions.fourier import DFT
from sympy.matrices.expressions.matexpr import MatrixElement

from reasoning.clauses import AND, EQUIVALENT, IMPLIES, NOT, OR
from reasoning.predicates import Q
from reasoning.registry import ClassFactRegistry
from reasoning.sympy_types import SymPyExpr

PredicateCall = Callable[[SymPyExpr], object]

_ELEMENT_PREDICATES = (
    (Q.real_elements, Q.real),
    (Q.complex_elements, Q.complex),
    (Q.integer_elements, Q.integer),
)

_MATPOW_PREDICATES = (
    Q.symmetric, Q.upper_triangular, Q.lower_triangular, Q.diagonal,
    Q.orthogonal, Q.unitary, Q.fullrank, Q.invertible,
)

_IDENTITY_PREDICATES = (
    Q.square, Q.invertible, Q.fullrank, Q.symmetric, Q.diagonal,
    Q.upper_triangular, Q.lower_triangular, Q.triangular, Q.unit_triangular,
    Q.integer_elements, Q.positive_definite, Q.orthogonal, Q.unitary,
)

_ZERO_PREDICATES = (
    Q.square, Q.symmetric, Q.diagonal, Q.upper_triangular,
    Q.lower_triangular, Q.triangular, Q.integer_elements,
)

_ZERO_NEGATED = (
    Q.invertible, Q.fullrank, Q.positive_definite, Q.orthogonal, Q.unitary,
)

_TRANSFER_PREDICATES = (
    Q.symmetric, Q.invertible, Q.fullrank, Q.unitary, Q.orthogonal,
    Q.diagonal, Q.positive_definite,
)


def _all(predicate: PredicateCall, args: Iterable[SymPyExpr]) -> object:
    return AND(*(predicate(arg) for arg in args))


def _any(predicate: PredicateCall, args: Iterable[SymPyExpr]) -> object:
    return OR(*(predicate(arg) for arg in args))


def _allargs(predicate: PredicateCall, expr: SymPyExpr) -> object:
    return _all(predicate, expr.args)


def _anyarg(predicate: PredicateCall, expr: SymPyExpr) -> object:
    return _any(predicate, expr.args)


def _closed(predicate: PredicateCall, expr: SymPyExpr) -> list[object]:
    return [
        IMPLIES(_allargs(predicate, expr), predicate(expr)),
        IMPLIES(_anyarg(lambda arg: NOT(predicate(arg)), expr),
                NOT(predicate(expr))),
    ]


def _closed_positive(predicate: PredicateCall, expr: SymPyExpr) -> list[object]:
    return [IMPLIES(_allargs(predicate, expr), predicate(expr))]


def _square(expr: SymPyExpr) -> bool:
    return bool(expr.shape[0] == expr.shape[1])


def _shape_facts(expr: SymPyExpr) -> list[object]:
    if _square(expr):
        return [Q.square(expr)]
    return [NOT(Q.square(expr))]


def _empty_or_1x1(expr: SymPyExpr) -> bool:
    return bool(expr.shape in ((0, 0), (1, 1)))


def _matrixsymbol_facts(expr: SymPyExpr) -> list[object]:
    facts = _shape_facts(expr)
    if _empty_or_1x1(expr):
        facts.append(Q.diagonal(expr))
    return facts


def _identity_facts(expr: SymPyExpr) -> list[object]:
    return [predicate(expr) for predicate in _IDENTITY_PREDICATES]


def _zeromatrix_facts(expr: SymPyExpr) -> list[object]:
    return (
        [predicate(expr) for predicate in _ZERO_PREDICATES]
        + [NOT(predicate(expr)) for predicate in _ZERO_NEGATED]
    )


def _onematrix_facts(expr: SymPyExpr) -> list[object]:
    one_by_one = expr.shape == (1, 1)
    facts = _shape_facts(expr)
    facts.append(EQUIVALENT(Q.symmetric(expr), Q.square(expr)))
    for predicate in (Q.invertible, Q.fullrank, Q.positive_definite,
                      Q.diagonal, Q.upper_triangular, Q.lower_triangular):
        facts.append(predicate(expr) if one_by_one else NOT(predicate(expr)))
    facts.append(Q.integer_elements(expr))
    return facts


def _explicit_invertible(expr: SymPyExpr) -> object:
    if not all(isinstance(entry, Number) for entry in expr):
        return None
    determinant = expr.det()
    if not isinstance(determinant, Number):
        return None
    return determinant != 0


def _matrixbase_facts(expr: SymPyExpr) -> list[object]:
    facts = _shape_facts(expr)
    if not _square(expr):
        return facts
    invertible = _explicit_invertible(expr)
    if invertible is not None:
        facts.append(Q.invertible(expr) if invertible else NOT(Q.invertible(expr)))
    elif expr.shape == (1, 1) and isinstance(expr[0, 0], MatrixExpr):
        facts.append(EQUIVALENT(Q.invertible(expr), Q.invertible(expr[0, 0])))
    return facts


def _matadd_facts(expr: SymPyExpr) -> list[object]:
    facts = _shape_facts(expr)
    for predicate in (Q.symmetric, Q.diagonal, Q.upper_triangular,
                      Q.lower_triangular, Q.positive_definite):
        facts.extend(_closed_positive(predicate, expr))
    for predicate, _scalar in _ELEMENT_PREDICATES:
        facts.extend(_closed(predicate, expr))
    return facts


def _matmul_facts(expr: SymPyExpr) -> list[object]:
    facts = _shape_facts(expr)
    matrices = [arg for arg in expr.args if isinstance(arg, MatrixExpr)]
    scalars = [arg for arg in expr.args if not isinstance(arg, MatrixExpr)]
    if not matrices:
        return facts
    square_factors = _all(Q.square, matrices)
    facts.append(IMPLIES(
        square_factors,
        EQUIVALENT(Q.invertible(expr), _all(Q.invertible, matrices))))
    facts.append(IMPLIES(
        AND(square_factors,
            _any(lambda arg: NOT(Q.invertible(arg)), matrices)),
        NOT(Q.invertible(expr))))
    facts.append(IMPLIES(_all(Q.fullrank, matrices), Q.fullrank(expr)))
    coefficient = expr.as_coeff_mmul()[0]
    for predicate in (Q.orthogonal, Q.unitary):
        if coefficient == 1:
            facts.append(IMPLIES(_all(predicate, matrices), predicate(expr)))
        facts.append(IMPLIES(
            AND(square_factors,
                _any(lambda arg: NOT(Q.invertible(arg)), matrices)),
            NOT(predicate(expr))))
    facts.append(IMPLIES(
        AND(Q.positive(coefficient), _all(Q.positive_definite, matrices)),
        Q.positive_definite(expr)))
    if len(matrices) >= 2 and matrices[0] == matrices[-1].T:
        if len(matrices) == 2:
            facts.append(IMPLIES(
                AND(Q.positive(coefficient), Q.square(matrices[0]),
                    Q.fullrank(matrices[0])),
                Q.positive_definite(expr)))
            facts.append(Q.symmetric(expr))
        else:
            middle = MatMul(*matrices[1:-1])
            facts.append(IMPLIES(
                AND(Q.positive(coefficient), Q.fullrank(matrices[0]),
                    Q.positive_definite(middle)),
                Q.positive_definite(expr)))
            facts.append(IMPLIES(
                Q.symmetric(middle), Q.symmetric(expr)))
    for predicate in (Q.symmetric, Q.upper_triangular, Q.lower_triangular):
        facts.append(IMPLIES(_all(predicate, matrices), predicate(expr)))
    if _empty_or_1x1(expr):
        facts.append(Q.diagonal(expr))
    else:
        facts.append(IMPLIES(_all(Q.diagonal, matrices), Q.diagonal(expr)))
    for predicate, scalar_predicate in _ELEMENT_PREDICATES:
        terms = ([scalar_predicate(arg) for arg in scalars]
                 + [predicate(arg) for arg in matrices])
        facts.append(IMPLIES(AND(*terms), predicate(expr)))
        facts.append(IMPLIES(
            OR(*(NOT(term) for term in terms)), NOT(predicate(expr))))
    return facts


def _matpow_facts(expr: SymPyExpr) -> list[object]:
    base, exponent = expr.base, expr.exp
    facts = _shape_facts(expr)
    if isinstance(exponent, Integer) and exponent >= 0:
        for predicate in _MATPOW_PREDICATES:
            facts.append(IMPLIES(predicate(base), predicate(expr)))
        for predicate, _scalar in _ELEMENT_PREDICATES:
            facts.append(IMPLIES(predicate(base), predicate(expr)))
    elif isinstance(exponent, Integer):
        facts.append(IMPLIES(Q.invertible(base), Q.invertible(expr)))
        for predicate in (Q.symmetric, Q.upper_triangular, Q.lower_triangular,
                          Q.diagonal):
            facts.append(IMPLIES(
                AND(Q.invertible(base), predicate(base)), predicate(expr)))
        for predicate in (Q.orthogonal, Q.unitary):
            facts.append(IMPLIES(predicate(base), predicate(expr)))
        for predicate, _scalar in _ELEMENT_PREDICATES:
            facts.append(IMPLIES(
                AND(Q.invertible(base), predicate(base)), predicate(expr)))
    else:
        integer_nonnegative = AND(Q.integer(exponent),
                                  NOT(Q.negative(exponent)))
        for predicate in (Q.symmetric, Q.upper_triangular, Q.lower_triangular,
                          Q.diagonal, Q.invertible):
            facts.append(IMPLIES(
                AND(integer_nonnegative, predicate(base)), predicate(expr)))
        for predicate, _scalar in _ELEMENT_PREDICATES:
            facts.append(IMPLIES(
                AND(integer_nonnegative, predicate(base)), predicate(expr)))
    facts.append(IMPLIES(Q.positive_definite(base), Q.positive_definite(expr)))
    return facts


def _transpose_facts(expr: SymPyExpr) -> list[object]:
    arg = expr.arg
    facts = _shape_facts(expr)
    for predicate in _TRANSFER_PREDICATES:
        facts.append(EQUIVALENT(predicate(expr), predicate(arg)))
    facts.append(EQUIVALENT(Q.upper_triangular(expr), Q.lower_triangular(arg)))
    facts.append(EQUIVALENT(Q.lower_triangular(expr), Q.upper_triangular(arg)))
    for predicate, _scalar in _ELEMENT_PREDICATES:
        facts.append(EQUIVALENT(predicate(expr), predicate(arg)))
    return facts


def _inverse_facts(expr: SymPyExpr) -> list[object]:
    arg = expr.arg
    facts = _shape_facts(expr)
    facts.append(Q.invertible(expr))
    for predicate in (Q.symmetric, Q.unitary, Q.orthogonal, Q.diagonal,
                      Q.positive_definite):
        facts.append(EQUIVALENT(predicate(expr), predicate(arg)))
    facts.append(EQUIVALENT(Q.upper_triangular(expr), Q.upper_triangular(arg)))
    facts.append(EQUIVALENT(Q.lower_triangular(expr), Q.lower_triangular(arg)))
    facts.append(IMPLIES(Q.complex_elements(arg), Q.complex_elements(expr)))
    facts.append(IMPLIES(
        AND(Q.invertible(arg), Q.real_elements(arg)), Q.real_elements(expr)))
    return facts


def _matrixslice_facts(expr: SymPyExpr) -> list[object]:
    facts: list[object] = []
    if _empty_or_1x1(expr):
        facts.append(Q.diagonal(expr))
    if expr.on_diag:
        for predicate in _TRANSFER_PREDICATES + (Q.upper_triangular,
                                                 Q.lower_triangular):
            facts.append(IMPLIES(predicate(expr.parent), predicate(expr)))
    for predicate, _scalar in _ELEMENT_PREDICATES:
        facts.append(IMPLIES(predicate(expr.parent), predicate(expr)))
    return facts


def _blockmatrix_facts(expr: SymPyExpr) -> list[object]:
    facts = _shape_facts(expr)
    blocks = list(expr.blocks)
    if expr.blockshape == (1, 1):
        facts.append(EQUIVALENT(Q.invertible(expr), Q.invertible(blocks[0])))
    elif blocks and all(isinstance(block, MatrixBase) for block in blocks):
        explicit = expr.as_explicit()
        invertible = _explicit_invertible(explicit)
        if invertible is not None:
            facts.append(Q.invertible(expr) if invertible
                         else NOT(Q.invertible(expr)))
    for predicate, _scalar in _ELEMENT_PREDICATES:
        facts.append(IMPLIES(
            AND(*(predicate(block) for block in blocks)), predicate(expr)))
        facts.append(IMPLIES(
            OR(*(NOT(predicate(block)) for block in blocks)),
            NOT(predicate(expr))))
    return facts


def _blockdiag_facts(expr: SymPyExpr) -> list[object]:
    if expr.rowblocksizes != expr.colblocksizes:
        return [NOT(Q.square(expr))]
    facts: list[object] = [Q.square(expr)]
    diagonal = list(expr.diag)
    if diagonal:
        facts.append(EQUIVALENT(
            Q.invertible(expr),
            AND(*(Q.invertible(block) for block in diagonal))))
    return facts


def _determinant_facts(expr: SymPyExpr) -> list[object]:
    arg = expr.args[0]
    return [
        IMPLIES(Q.positive_definite(arg), Q.positive(expr)),
        IMPLIES(Q.real_elements(arg), Q.real_elements(expr)),
        IMPLIES(Q.complex_elements(arg), Q.complex_elements(expr)),
        IMPLIES(Q.integer_elements(arg), Q.integer_elements(expr)),
        IMPLIES(Q.integer_elements(arg), Q.integer(expr)),
    ]


def _trace_facts(expr: SymPyExpr) -> list[object]:
    arg = expr.args[0]
    return [
        IMPLIES(Q.positive_definite(arg), Q.positive(expr)),
        IMPLIES(Q.real_elements(arg), Q.real_elements(expr)),
        IMPLIES(Q.complex_elements(arg), Q.complex_elements(expr)),
        IMPLIES(Q.integer_elements(arg), Q.integer_elements(expr)),
        IMPLIES(Q.integer_elements(arg), Q.integer(expr)),
    ]


def _hadamard_facts(expr: SymPyExpr) -> list[object]:
    return [fact for predicate, _scalar in _ELEMENT_PREDICATES
            for fact in _closed(predicate, expr)]


def _factorization_facts(expr: SymPyExpr) -> list[object]:
    return [fact for predicate in (Q.real_elements, Q.complex_elements)
            for fact in _closed(predicate, expr)]


def _dft_facts(expr: SymPyExpr) -> list[object]:
    return [Q.square(expr), Q.unitary(expr), Q.complex_elements(expr)]


def _diagonal_matrix_facts(expr: SymPyExpr) -> list[object]:
    return [Q.diagonal(expr)]


def _matrixelement_facts(expr: SymPyExpr) -> list[object]:
    args = expr.args
    parent = args[0]
    facts = [
        IMPLIES(Q.real_elements(parent), Q.real(expr)),
        IMPLIES(Q.complex_elements(parent), Q.complex(expr)),
        IMPLIES(Q.integer_elements(parent), Q.integer(expr)),
    ]
    if len(args) == 3 and args[1] == args[2]:
        facts.append(IMPLIES(Q.positive_definite(parent), Q.positive(expr)))
    return facts


def register_matrix_facts(registry: ClassFactRegistry) -> None:
    """Attach the matrix-expression handlers to a fact registry."""
    registry.multiregister(MatrixSymbol)(_matrixsymbol_facts)
    registry.multiregister(Identity)(_identity_facts)
    registry.multiregister(ZeroMatrix)(_zeromatrix_facts)
    registry.multiregister(OneMatrix)(_onematrix_facts)
    registry.multiregister(MatrixBase)(_matrixbase_facts)
    registry.multiregister(MatAdd)(_matadd_facts)
    registry.multiregister(MatMul)(_matmul_facts)
    registry.multiregister(MatPow)(_matpow_facts)
    registry.multiregister(Transpose)(_transpose_facts)
    registry.multiregister(Inverse)(_inverse_facts)
    registry.multiregister(MatrixSlice)(_matrixslice_facts)
    registry.multiregister(BlockMatrix)(_blockmatrix_facts)
    registry.multiregister(BlockDiagMatrix)(_blockdiag_facts)
    registry.multiregister(Determinant)(_determinant_facts)
    registry.multiregister(Trace)(_trace_facts)
    registry.multiregister(HadamardProduct)(_hadamard_facts)
    registry.multiregister(Factorization)(_factorization_facts)
    registry.multiregister(DFT)(_dft_facts)
    registry.multiregister(DiagMatrix, DiagonalMatrix)(_diagonal_matrix_facts)
    registry.multiregister(MatrixElement)(_matrixelement_facts)


__all__ = ["register_matrix_facts"]
