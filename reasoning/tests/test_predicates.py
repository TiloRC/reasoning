import pytest

from reasoning.predicates import (
    AppliedPredicate, Predicate, PredicateNamespace, Q,
)


def test_predicates_are_named_and_structural() -> None:
    assert Q.real is Q.real
    assert Q.real == Predicate("real")
    assert Q.real != Q.positive
    assert repr(Q.real) == "Q.real"
    assert hash(Q.real) == hash(Predicate("real"))


def test_applied_predicates_compare_structurally() -> None:
    assert Q.real(1) == Q.real(1)
    assert Q.real(1) != Q.real(2)
    assert Q.real(1) != Q.positive(1)
    assert hash(Q.real(1)) == hash(Q.real(1))
    assert Q.real(1).name == "real"
    assert Q.real(1).arguments == (1,)
    assert repr(Q.real(1)) == "Q.real(1)"
    assert repr(Q.eq(1, 2)) == "Q.eq(1, 2)"


def test_namespace_rejects_unknown_names() -> None:
    with pytest.raises(AttributeError):
        Q.nonexistent
    with pytest.raises(KeyError):
        Q["nonexistent"]
    assert "real" in Q
    assert "nonexistent" not in Q


def test_of_returns_known_and_unknown_predicates() -> None:
    assert Q.of("real") is Q.real
    assert Q.of("custom") == Predicate("custom")
    assert "custom" not in Q
    with pytest.raises(KeyError):
        Q["custom"]


def test_custom_namespace_controls_the_vocabulary() -> None:
    namespace = PredicateNamespace(["foo"])
    assert isinstance(namespace.foo(1), AppliedPredicate)
    assert namespace.foo(1).name == "foo"
    assert namespace.names() == ["foo"]
    with pytest.raises(AttributeError):
        namespace.bar
