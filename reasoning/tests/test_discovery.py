import subprocess
import sys
from collections import Counter
from typing import Hashable

from reasoning.clauses import ClauseDB, OR
from reasoning.discovery import discover_facts, relevant_subjects


class Adapter:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()

    def relevance_keys(self, atom: str) -> set[Hashable]:
        return set(atom)

    def subjects(self, atom: str) -> tuple[str, ...]:
        return (atom,)

    def fact_subjects(self, atom: str) -> tuple[str, ...]:
        return (atom,)

    def facts_for(self, subject: str) -> list[str]:
        self.calls[subject] += 1
        return {'a': ['b'], 'b': ['a']}[subject]


def test_discovery_cycles_and_rounds() -> None:
    adapter = Adapter()
    assert discover_facts({'a'}, ClauseDB(), adapter) == {'a', 'b'}
    assert adapter.calls == {'a': 1, 'b': 1}
    adapter = Adapter()
    assert discover_facts({'a'}, ClauseDB(), adapter, 1) == {'a'}
    assert adapter.calls == {'a': 1}
    assert discover_facts({'a'}, ClauseDB(), adapter, 0) == set()


def test_relevance_transitive_closure() -> None:
    assert relevant_subjects('a', OR('ab', 'bc', 'z'), Adapter()) == {'a', 'ab', 'bc'}


def test_core_works_with_sympy_imports_blocked() -> None:
    code = '''
import sys
class BlockSympy:
    def find_spec(self, fullname, *args):
        if fullname == 'sympy' or fullname.startswith('sympy.'):
            raise ImportError('SymPy is unavailable')
sys.meta_path.insert(0, BlockSympy())
from reasoning.clauses import ClauseDB, IMPLIES, assert_formula, compile_formula
from reasoning.engine import ReasoningEngine
from reasoning.discovery import discover_facts
from reasoning.registry import ClassFactRegistry
db = ClauseDB()
assert_formula('a', db)
assert_formula(IMPLIES('a', 'b'), db)
query = compile_formula('b', db)
assert ReasoningEngine(db).ask(query) is True
assert not any(name == 'sympy' or name.startswith('sympy.') for name in sys.modules)
'''
    subprocess.run([sys.executable, '-c', code], check=True)
