from __future__ import annotations

from sympy import Q, MatrixSymbol, Symbol, symbols

from reasoning.satask import satask
from reasoning.symbolfacts import declared_assumptions

x, y, z = symbols('x y z')


def _symbol(name: str, declarations: dict[str, bool]) -> Symbol:
    # Assumption keywords at a call site are reported by the advisory checker
    # (tools/check_old_assumptions.py), so tests build declared symbols from a
    # mapping instead.
    return Symbol(name, **declarations)


def _harvested(declarations: dict[str, bool]) -> dict[str, bool]:
    return dict(declared_assumptions(_symbol('s', declarations)))


def test_declared_assumptions_are_harvested() -> None:
    real = _harvested({"real": True})
    assert real["real"] is True
    assert real["imaginary"] is False

    imaginary = _harvested({"imaginary": True})
    assert imaginary["imaginary"] is True
    assert imaginary["real"] is False

    positive = _harvested({"positive": True})
    assert positive["positive"] is True
    assert positive["negative"] is False

    negative = _harvested({"negative": True})
    assert negative["negative"] is True
    assert negative["positive"] is False

    assert _harvested({"finite": True})["finite"] is True

    prime = _harvested({"prime": True})
    assert prime["prime"] is True
    assert prime["composite"] is False

    composite = _harvested({"composite": True})
    assert composite["composite"] is True
    assert composite["prime"] is False

    assert _harvested({"even": True})["odd"] is False
    assert _harvested({"odd": True})["even"] is False

    nonzero = _harvested({"nonzero": True})
    assert nonzero["nonzero"] is True
    assert nonzero["zero"] is False
    assert _harvested({"zero": True})["zero"] is True

    assert _harvested({"integer": True})["integer"] is True

    rational = _harvested({"rational": True})
    assert rational["rational"] is True
    assert rational["irrational"] is False

    irrational = _harvested({"irrational": True})
    assert irrational["irrational"] is True
    assert irrational["rational"] is False

    assert _harvested({"transcendental": True})["transcendental"] is True
    assert _harvested({"commutative": False})["commutative"] is False


def test_plain_symbol_harvest_is_commutative_only() -> None:
    assert declared_assumptions(Symbol('plain')) == (("commutative", True),)


def test_harvest_is_cached_per_symbol() -> None:
    first = declared_assumptions(_symbol('cached', {"positive": True}))
    assert first is declared_assumptions(_symbol('cached', {"positive": True}))
    # Symbols with the same name but different declarations are distinct keys.
    assert declared_assumptions(_symbol('cached', {"positive": True})) \
        != declared_assumptions(_symbol('cached', {"negative": True}))


def test_satask_uses_declared_assumptions() -> None:
    positive = _symbol('p', {"positive": True})
    assert satask(Q.positive(positive)) is True
    assert satask(Q.negative(positive)) is False
    assert satask(Q.real(positive)) is True

    imaginary = _symbol('i', {"imaginary": True})
    assert satask(Q.imaginary(imaginary)) is True
    assert satask(Q.real(imaginary)) is False

    integer = _symbol('n', {"integer": True, "negative": True})
    assert satask(Q.integer(integer)) is True
    assert satask(Q.negative(integer)) is True

    noncommutative = _symbol('nc', {"commutative": False})
    assert satask(Q.commutative(noncommutative)) is False

    # Undeclared facts stay undetermined.
    assert satask(Q.positive(Symbol('u'))) is None
    assert satask(Q.rational(Symbol('u'))) is None


def test_explicit_assumptions_override_harvest() -> None:
    assert satask(Q.commutative(x), ~Q.commutative(x)) is False
    assert satask(Q.commutative(x), Q.commutative(x)) is True


def test_matrix_symbols_are_not_harvested() -> None:
    matrix = MatrixSymbol('M', 2, 2)
    assert declared_assumptions(matrix) == ()
    # Old assumptions would call a matrix non-real; the bridge stays out.
    assert satask(Q.real(matrix)) is None
