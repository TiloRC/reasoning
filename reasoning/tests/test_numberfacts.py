from __future__ import annotations

import importlib

import pytest
from sympy.assumptions.ask import Q
from sympy.core.numbers import E, Float, Integer, Rational
from sympy.core.singleton import S

from reasoning.clauses import Formula, iter_atoms
from reasoning.numberfacts import number_facts
from reasoning.predicates import AppliedPredicate as LocalAppliedPredicate
from reasoning.satask import satask
from reasoning.sathandlers import class_fact_registry

I = S.ImaginaryUnit
nan = S.NaN
oo = S.Infinity
pi = S.Pi
zoo = S.ComplexInfinity


def test_integer_facts() -> None:
    assert satask(Q.positive(3)) is True
    assert satask(Q.negative(3)) is False
    assert satask(Q.negative(-3)) is True
    assert satask(Q.zero(0)) is True
    assert satask(Q.zero(3)) is False
    assert satask(Q.nonzero(0)) is False
    assert satask(Q.nonzero(3)) is True
    assert satask(Q.nonnegative(-3)) is False
    assert satask(Q.nonpositive(-3)) is True
    assert satask(Q.integer(3)) is True
    assert satask(Q.rational(3)) is True
    assert satask(Q.irrational(3)) is False
    assert satask(Q.even(12)) is True
    assert satask(Q.odd(12)) is False
    assert satask(Q.even(-2)) is True
    assert satask(Q.odd(-3)) is True
    assert satask(Q.prime(11)) is True
    assert satask(Q.composite(11)) is False
    assert satask(Q.composite(12)) is True
    assert satask(Q.prime(1)) is False
    assert satask(Q.composite(1)) is False
    assert satask(Q.algebraic(2)) is True
    assert satask(Q.transcendental(2)) is False
    assert satask(Q.hermitian(1)) is True
    assert satask(Q.antihermitian(1)) is False
    assert satask(Q.antihermitian(0)) is True


def test_rational_number_facts() -> None:
    assert satask(Q.positive(Rational(3, 4))) is True
    assert satask(Q.negative(Rational(3, 4))) is False
    assert satask(Q.positive(Rational(-3, 4))) is False
    assert satask(Q.negative(Rational(-5, 3))) is True
    assert satask(Q.zero(Rational(3, 4))) is False
    assert satask(Q.nonzero(Rational(3, 4))) is True
    assert satask(Q.integer(Rational(3, 4))) is False
    assert satask(Q.rational(Rational(3, 4))) is True
    assert satask(Q.irrational(Rational(3, 4))) is False
    assert satask(Q.even(Rational(3, 4))) is False
    assert satask(Q.odd(Rational(3, 4))) is False
    assert satask(Q.prime(Rational(3, 4))) is False
    assert satask(Q.composite(Rational(3, 4))) is False
    assert satask(Q.algebraic(Rational(3, 4))) is True
    assert satask(Q.hermitian(Rational(3, 4))) is True
    assert satask(Q.antihermitian(Rational(3, 4))) is False


def test_float_facts_are_tri_state() -> None:
    assert satask(Q.integer(Float(1.0))) is None
    assert satask(Q.rational(Float(1.0))) is None
    assert satask(Q.irrational(Float(1.0))) is None
    assert satask(Q.algebraic(Float(1.0))) is None
    assert satask(Q.transcendental(Float(1.0))) is None
    assert satask(Q.even(Float(1.0))) is None
    assert satask(Q.odd(Float(1.0))) is None
    assert satask(Q.prime(Float(1.0))) is None
    assert satask(Q.composite(Float(1.0))) is None
    assert satask(Q.positive(Float(1.0))) is True
    assert satask(Q.negative(Float(1.0))) is False
    assert satask(Q.zero(Float(1.0))) is False
    assert satask(Q.real(Float(1.0))) is True
    assert satask(Q.complex(Float(1.0))) is True
    assert satask(Q.finite(Float(1.0))) is True
    assert satask(Q.hermitian(Float(1.0))) is True
    assert satask(Q.antihermitian(Float(1.0))) is False
    assert satask(Q.antihermitian(Float(0.0))) is True

    assert satask(Q.integer(Float(7.2123))) is False
    assert satask(Q.even(Float(7.2123))) is False
    assert satask(Q.odd(Float(7.2123))) is False
    assert satask(Q.prime(Float(7.2123))) is False
    assert satask(Q.composite(Float(7.2123))) is False
    assert satask(Q.rational(Float(7.2123))) is None
    assert satask(Q.irrational(Float(7.2123))) is None
    assert satask(Q.transcendental(Float(7.2123))) is None
    assert satask(Q.negative(Float(7.2123))) is False
    assert satask(Q.negative(Float(-7.2123))) is True


def test_nan_facts() -> None:
    assert satask(Q.commutative(nan)) is True
    for predicate in (
        Q.integer, Q.rational, Q.algebraic, Q.real, Q.extended_real, Q.complex,
        Q.irrational, Q.imaginary, Q.positive, Q.negative, Q.zero, Q.nonzero,
        Q.even, Q.odd, Q.finite, Q.infinite, Q.prime, Q.composite, Q.hermitian,
        Q.antihermitian, Q.transcendental,
    ):
        assert satask(predicate(nan)) is None


def test_infinity_facts() -> None:
    assert satask(Q.infinite(oo)) is True
    assert satask(Q.finite(oo)) is False
    assert satask(Q.extended_real(oo)) is True
    assert satask(Q.real(oo)) is False
    assert satask(Q.complex(oo)) is False
    assert satask(Q.extended_positive(oo)) is True
    assert satask(Q.extended_negative(oo)) is False
    assert satask(Q.positive(oo)) is False
    assert satask(Q.negative(oo)) is False
    assert satask(Q.zero(oo)) is False
    assert satask(Q.nonzero(oo)) is False
    assert satask(Q.integer(oo)) is False
    assert satask(Q.rational(oo)) is False
    assert satask(Q.algebraic(oo)) is False
    assert satask(Q.transcendental(oo)) is False
    assert satask(Q.hermitian(oo)) is False
    assert satask(Q.antihermitian(oo)) is False
    assert satask(Q.positive_infinite(oo)) is True
    assert satask(Q.negative_infinite(oo)) is False
    assert satask(Q.extended_nonzero(oo)) is True
    assert satask(Q.extended_nonnegative(oo)) is True
    assert satask(Q.nonnegative(oo)) is False
    assert satask(Q.commutative(oo)) is True


def test_negative_infinity_facts() -> None:
    mm = S.NegativeInfinity
    assert satask(Q.infinite(mm)) is True
    assert satask(Q.finite(mm)) is False
    assert satask(Q.extended_real(mm)) is True
    assert satask(Q.extended_positive(mm)) is False
    assert satask(Q.extended_negative(mm)) is True
    assert satask(Q.positive_infinite(mm)) is False
    assert satask(Q.negative_infinite(mm)) is True
    assert satask(Q.extended_nonnegative(mm)) is False
    assert satask(Q.extended_nonpositive(mm)) is True
    assert satask(Q.positive(mm)) is False
    assert satask(Q.negative(mm)) is False
    assert satask(Q.zero(mm)) is False
    assert satask(Q.commutative(mm)) is True


def test_complex_infinity_facts() -> None:
    assert satask(Q.infinite(zoo)) is True
    assert satask(Q.finite(zoo)) is False
    assert satask(Q.extended_real(zoo)) is False
    assert satask(Q.real(zoo)) is False
    assert satask(Q.complex(zoo)) is False
    assert satask(Q.extended_positive(zoo)) is False
    assert satask(Q.extended_negative(zoo)) is False
    assert satask(Q.zero(zoo)) is False
    assert satask(Q.nonzero(zoo)) is False
    assert satask(Q.rational(zoo)) is False
    assert satask(Q.algebraic(zoo)) is False
    assert satask(Q.transcendental(zoo)) is False
    assert satask(Q.positive_infinite(zoo)) is False
    assert satask(Q.negative_infinite(zoo)) is False
    assert satask(Q.hermitian(zoo)) is False
    assert satask(Q.antihermitian(zoo)) is False
    assert satask(Q.commutative(zoo)) is True


def test_imaginary_unit_facts() -> None:
    assert satask(Q.imaginary(I)) is True
    assert satask(Q.real(I)) is False
    assert satask(Q.complex(I)) is True
    assert satask(Q.algebraic(I)) is True
    assert satask(Q.transcendental(I)) is False
    assert satask(Q.finite(I)) is True
    assert satask(Q.infinite(I)) is False
    assert satask(Q.zero(I)) is False
    assert satask(Q.nonzero(I)) is False
    assert satask(Q.positive(I)) is False
    assert satask(Q.negative(I)) is False
    assert satask(Q.rational(I)) is False
    assert satask(Q.integer(I)) is False
    assert satask(Q.hermitian(I)) is False
    assert satask(Q.antihermitian(I)) is True
    assert satask(Q.commutative(I)) is True


def test_number_symbol_facts() -> None:
    assert satask(Q.irrational(pi)) is True
    assert satask(Q.algebraic(pi)) is False
    assert satask(Q.transcendental(pi)) is True
    assert satask(Q.rational(pi)) is False
    assert satask(Q.integer(pi)) is False
    assert satask(Q.positive(pi)) is True
    assert satask(Q.finite(pi)) is True
    assert satask(Q.commutative(pi)) is True

    assert satask(Q.irrational(E)) is True
    assert satask(Q.algebraic(E)) is False
    assert satask(Q.transcendental(E)) is True
    assert satask(Q.positive(E)) is True

    assert satask(Q.algebraic(S.GoldenRatio)) is True
    assert satask(Q.transcendental(S.GoldenRatio)) is False
    assert satask(Q.irrational(S.GoldenRatio)) is True

    assert satask(Q.algebraic(S.TribonacciConstant)) is True
    assert satask(Q.transcendental(S.TribonacciConstant)) is False
    assert satask(Q.positive(S.TribonacciConstant)) is True


def test_unknown_number_symbols_emit_nothing() -> None:
    assert satask(Q.algebraic(S.EulerGamma)) is None
    assert satask(Q.positive(S.EulerGamma)) is None
    assert satask(Q.irrational(S.Catalan)) is None


def test_number_facts_register_local_predicate_formulas() -> None:
    facts = number_facts(zoo)
    assert facts
    assert all(isinstance(fact, Formula) for fact in facts)
    for fact in facts:
        for atom in iter_atoms(fact):
            assert isinstance(atom, LocalAppliedPredicate)
            assert atom.arguments == (zoo,)

    registered = class_fact_registry(zoo)
    assert registered == set(facts)


def test_int_valued_float_omits_integer_facts() -> None:
    names: set[str] = set()
    for fact in number_facts(Float(1.0)):
        for atom in iter_atoms(fact):
            assert isinstance(atom, LocalAppliedPredicate)
            names.add(atom.name)
    assert "integer" not in names
    assert "even" not in names
    assert "odd" not in names
    assert "prime" not in names
    assert "composite" not in names
    assert "positive" in names


def test_number_facts_do_not_query_old_assumptions(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assumptions = importlib.import_module("sympy.core.assumptions")

    def fail(fact: str, obj: object) -> bool:
        raise AssertionError(f"old assumptions queried for {fact!r}")

    monkeypatch.setattr(assumptions, "_ask", fail)

    assert satask(Q.positive(3)) is True
    assert satask(Q.hermitian(1)) is True
    assert satask(Q.positive_infinite(oo)) is True
    assert satask(Q.algebraic(pi)) is False
    assert satask(Q.commutative(I)) is True
    assert satask(Q.antihermitian(1)) is False
    assert satask(Q.integer(Integer(12))) is True
    assert satask(Q.prime(Integer(11))) is True
