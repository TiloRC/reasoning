"""Advisory checker for reliance on SymPy's old assumptions system.

SymPy keeps assumptions in two places.  The *old* system attaches them to
objects and exposes them as ``is_<assumption>`` attributes::

    x = Symbol("x", positive=True)
    x.is_positive          # True

The *new* system queries predicates without attaching anything::

    ask(Q.positive(x))

This script parses every Python file under the given paths with :mod:`ast` and
reports code that reads old assumptions:

* attribute reads such as ``x.is_positive`` and ``x.assumptions0``
* assumption keywords such as ``Symbol("x", positive=True)``
* ``getattr``/``hasattr`` lookups that name an assumption attribute, including
  names built at runtime (``getattr(x, "is_" + name)``) that a plain ``grep``
  would miss
* ``is_``-prefixed string literals, so strings that escape through variables
  are still visible

The scan is advisory: it prints ``file:line:column: [category] detail`` lines
and a summary, and always exits 0.  Known limitations: ``getattr`` with a name
that cannot be traced to a string literal or a tracked variable is not
reported, and attribute names are matched against SymPy's fixed vocabulary
(``zero``, ``positive``, ``extended_real``, ...), so custom predicate names are
not detected.

Usage::

    python tools/check_old_assumptions.py [paths ...]

Directories are scanned recursively; ``.git``, ``.venv``, caches, and the
vendored ``sympy`` tree are skipped.  The checker skips its own file so that its
pattern tables do not show up as findings.
"""
from __future__ import annotations

import argparse
import ast
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

ASSUMPTION_NAMES = frozenset({
    "algebraic", "antihermitian", "commutative", "complex", "composite",
    "even", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero", "extended_positive",
    "extended_real", "finite", "hermitian", "imaginary", "infinite",
    "integer", "irrational", "negative", "nonnegative", "nonpositive",
    "nonzero", "odd", "positive", "prime", "rational", "real",
    "transcendental", "zero",
})

ASSUMPTION_STRINGS = ASSUMPTION_NAMES | {"is_" + name for name in ASSUMPTION_NAMES}

_ASSUMPTION_ATTRIBUTE = re.compile(r"^is_[a-z_]+$")

_SELF = Path(__file__).resolve()

SKIP_DIRS = frozenset({
    ".git", ".mypy_cache", ".pytest_cache", ".venv", "__pycache__",
    "node_modules", "reasoning.egg-info", "sympy",
})


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    category: str
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: [{self.category}] {self.detail}"


def _is_assumption_like(value: str) -> bool:
    return (value == "is_"
            or value in ASSUMPTION_STRINGS
            or _ASSUMPTION_ATTRIBUTE.match(value) is not None)


def _string_constant(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _mentions_assumption(node: ast.AST) -> bool:
    return any(
        isinstance(part, ast.Constant)
        and isinstance(part.value, str)
        and _is_assumption_like(part.value)
        for part in ast.walk(node)
    )


def _tracked_names(tree: ast.AST) -> set[str]:
    """Names assigned an assumption-like string, e.g. ``prefix = "is_"``."""
    tracked: set[str] = set()
    for node in ast.walk(tree):
        targets: Sequence[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if value is None or not _mentions_assumption(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                tracked.add(target.id)
    return tracked


class OldAssumptionVisitor(ast.NodeVisitor):
    def __init__(self, path: str, tracked: set[str]) -> None:
        self.path = path
        self.tracked = tracked
        self.findings: list[Finding] = []
        self._handled: set[int] = set()

    def _report(self, node: ast.expr, category: str, detail: str) -> None:
        self.findings.append(Finding(
            self.path, node.lineno, node.col_offset + 1, category, detail))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = node.attr
        if name in ("assumptions", "assumptions0"):
            self._report(node, "assumptions", f"reads .{name}")
        elif name.startswith("is_") and name[3:] in ASSUMPTION_NAMES:
            self._report(node, "attribute", f"reads .{name}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("getattr", "hasattr"):
            self._check_lookup(node)
        for keyword in node.keywords:
            if keyword.arg in ASSUMPTION_NAMES:
                self._report(
                    keyword.value, "keyword",
                    f"passes assumption keyword {keyword.arg}=")
        self.generic_visit(node)

    def _check_lookup(self, node: ast.Call) -> None:
        if len(node.args) < 2:
            return
        name_arg = node.args[1]
        text = _string_constant(name_arg)
        if text is not None:
            if _is_assumption_like(text):
                self._handled.add(id(name_arg))
                self._report(
                    node, "getattr",
                    f"looks up {ast.unparse(node.func)} for {text!r}")
            return
        if _mentions_assumption(name_arg):
            self._handled.update(
                id(part) for part in ast.walk(name_arg)
                if isinstance(part, ast.Constant))
            self._report(
                node, "dynamic-getattr",
                f"builds an assumption name: {ast.unparse(node)}")
            return
        if isinstance(name_arg, ast.Name) and name_arg.id in self.tracked:
            self._report(
                node, "dynamic-getattr",
                f"looks up tracked name {name_arg.id!r}: {ast.unparse(node)}")

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._handled:
            return
        value = node.value
        if isinstance(value, str) and (value == "is_"
                                       or _ASSUMPTION_ATTRIBUTE.match(value)):
            self._report(node, "string", f"assumption-name string {value!r}")


def check_file(path: Path) -> list[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        return [Finding(str(path), error.lineno or 0, error.offset or 0,
                        "parse-error", str(error))]
    display = _display_path(path)
    visitor = OldAssumptionVisitor(display, _tracked_names(tree))
    visitor.visit(tree)
    return visitor.findings


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def iter_python_files(paths: Sequence[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_file():
            if path.suffix == ".py":
                yield path
            continue
        for candidate in sorted(path.rglob("*.py")):
            if SKIP_DIRS.intersection(candidate.parts):
                continue
            if candidate.resolve() == _SELF:
                continue
            yield candidate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="files or directories to scan (default: the repository root)")
    arguments = parser.parse_args(argv)
    roots: list[Path] = list(arguments.paths) or [_SELF.parent.parent]
    files = list(iter_python_files(roots))
    findings: list[Finding] = []
    for path in files:
        findings.extend(check_file(path))
    findings.sort(key=lambda finding: (finding.path, finding.line, finding.column))
    for finding in findings:
        print(finding.format())
    counts = Counter(finding.category for finding in findings)
    breakdown = ", ".join(
        f"{category}: {count}" for category, count in sorted(counts.items()))
    print(f"\n{len(findings)} finding(s) in {len({f.path for f in findings})} "
          f"of {len(files)} file(s)"
          + (f" ({breakdown})" if breakdown else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
