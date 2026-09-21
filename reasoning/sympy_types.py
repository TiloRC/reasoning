"""A name for values that are SymPy expressions.

SymPy is excluded from type checking (``follow_imports = "skip"`` in
``pyproject.toml``), so its classes are otherwise seen as bare ``Any``.
``SymPyExpr`` names those values at the boundary, giving the annotations a
single place to tighten if SymPy's own stubs improve.
"""
from sympy.core.basic import Basic

SymPyExpr = Basic

__all__ = ["SymPyExpr"]
