"""Select backend comparisons by normalized test identity, not speed markers.

Loaded explicitly by compare_backends; plain pytest validation still runs the
complete upstream suites.
"""
import pytest

from .compare_backends import CONTROL_TESTS, comparison_key


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    selected, deselected = [], []
    for item in items:
        if comparison_key(item.nodeid) in CONTROL_TESTS:
            deselected.append(item)
        else:
            selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
