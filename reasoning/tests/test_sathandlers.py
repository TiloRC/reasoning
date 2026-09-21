from sympy import Q, symbols
from sympy.core import Add
from sympy.functions.elementary.complexes import Abs

from reasoning.clauses import Formula
from reasoning.registry import ClassFactRegistry
from reasoning.sathandlers import allargs, anyarg, class_fact_registry, exactlyonearg


def test_legacy_argument_helpers_remain_sympy_expressions() -> None:
    x, y = symbols('x y')
    expression = x*y

    assert allargs(x, Q.real(x), expression) == Q.real(x) & Q.real(y)
    assert anyarg(x, Q.real(x), expression) == Q.real(x) | Q.real(y)
    assert exactlyonearg(x, Q.real(x), expression) == (
        Q.real(x) & ~Q.real(y) | Q.real(y) & ~Q.real(x)
    )


def test_registered_handlers_emit_lightweight_formulas() -> None:
    x, y = symbols('x y')
    facts = class_fact_registry(x + y)

    assert facts
    assert any(isinstance(fact, Formula) for fact in facts)
    assert all(isinstance(fact, Formula) for fact in facts)


def test_registry_applies_base_class_handlers_and_combines_results() -> None:
    registry = ClassFactRegistry()

    @registry.register(Add)
    def one(expr: object) -> object:
        return ('one', expr)

    @registry.multiregister(Add)
    def many(expr: object) -> list[object]:
        return [('many', expr)]

    x, y = symbols('x y')
    expression = x + y
    assert registry(expression) == {('one', expression), ('many', expression)}


def test_abs_facts_contain_no_sympy_boolean_connectives() -> None:
    x = symbols('x')
    facts = class_fact_registry(Abs(x))
    assert any(isinstance(fact, Formula) for fact in facts)
    assert Q.nonnegative(Abs(x)) in facts
