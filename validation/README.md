# validation

This directory is an unbiased way to evaluate progress in the project. The test
suite comes from the SymPy commit pinned by the `sympy` extra in
`pyproject.toml`, so it should not be edited here.

`test_query.py` re-exports SymPy's `assumptions/tests/test_query.py` with `ask`
and `_ask_recursive` bound to `reasoning.satask.satask`, and refuses to run
against a different SymPy install. Install the pinned version with
`pip install -e '.[sympy,dev]'`.

`compare_backends.py` runs the suite against this checkout's `satask` and
against SymPy's unmodified `satask`, then compares per-test outcomes.
