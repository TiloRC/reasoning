"""Registry for facts associated with expression classes.

The registry deliberately knows nothing about SymPy or the representation of a
fact.  Handlers can therefore return lightweight Boolean formulas as well as
other fact objects.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable

SingleHandler = Callable[[Any], object]
MultiHandler = Callable[[Any], Iterable[object]]


class ClassFactRegistry:
    """Register fact-producing functions against expression classes.

    ``register`` handlers return one fact and ``multiregister`` handlers
    return an iterable of facts.  Handlers registered for base classes apply
    to subclasses too.
    """

    def __init__(self) -> None:
        self.singlefacts: defaultdict[type[Any], frozenset[SingleHandler]] = (
            defaultdict(frozenset))
        self.multifacts: defaultdict[type[Any], frozenset[MultiHandler]] = (
            defaultdict(frozenset))

    def register(self, cls: type[Any]) -> Callable[[SingleHandler], SingleHandler]:
        def decorator(func: SingleHandler) -> SingleHandler:
            self.singlefacts[cls] |= {func}
            return func
        return decorator

    def multiregister(self, *classes: type[Any]) -> Callable[[MultiHandler], MultiHandler]:
        def decorator(func: MultiHandler) -> MultiHandler:
            for cls in classes:
                self.multifacts[cls] |= {func}
            return func
        return decorator

    def __getitem__(self, key: type[Any]) -> tuple[
        frozenset[SingleHandler], frozenset[MultiHandler],
    ]:
        singles = self.singlefacts[key]
        multiples = self.multifacts[key]
        for registered, handlers in self.singlefacts.items():
            if issubclass(key, registered):
                singles |= handlers
        for registered, handlers in self.multifacts.items():
            if issubclass(key, registered):
                multiples |= handlers
        return singles, multiples

    def __call__(self, expr: Any) -> set[object]:
        singles, multiples = self[type(expr)]
        facts: set[object] = {handler(expr) for handler in singles}
        for handler in multiples:
            facts.update(handler(expr))
        return facts
