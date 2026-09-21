# Agent report: would expanding sathandlers pass more validation tests?

- **Date:** 2026-09-21
- **Status:** investigation complete, no source changes made
- **Scope:** `validation/test_query.py` + `validation/test_matrices.py` against pinned
  SymPy `ddbb536d` (1.15.0.dev)
- **Read this if:** you are editing `reasoning/sathandlers.py`, the known-facts import
  in `reasoning/sympy_adapter.py`, or trying to raise the validation pass rate
- **Stale after:** any change to `sathandlers.py`, `sympy_adapter.py`, the SymPy pin,
  or the validation results
- **TL;DR:** Yes. About 59 of the 68 failures are blocked only on missing
  per-expression-class facts; about 9 need non-handler infrastructure.
  Baseline: reasoning 26/104, SymPy `satask` 24/104, full SymPy `ask` 94/104.

## What was run

```
.venv/bin/python validation/compare_backends.py --verbose
.venv/bin/python -m pytest validation/test_query.py validation/test_matrices.py -q --tb=line
.venv/bin/python -m pytest <upstream suite copy> -q   # SymPy's own ask: 94 passed, 10 failed
```

## Findings

- Reasoning currently passes 26/104, upstream `satask` 24/104, full `ask` 94/104.
  `compare_backends.py` exits 1: it treats "reasoning passes, SymPy satask fails" as an
  outcome mismatch. It already flags `test_composite_proposition` and `test_issue_3906`.
- The adapter already imports SymPy's complete known predicate facts
  (`get_all_known_number_facts`, `get_all_known_matrix_facts`), so predicate-to-predicate
  relations are not the gap. I verified the encoding polarity in `_known_template` is
  correct; an apparent inversion was a false alarm about `Literal.is_Not` semantics.
- Failures by first failing assertion, roughly:
  - **~59 class-fact addressable:** number getters (`antihermitian`, `algebraic`,
    `commutative`, `hermitian`, `transcendental`, ...); Add/Mul/Pow structural facts
    (parity, sign, real/complex/finite/rational closure); elementary-function handlers
    (`sin`, `cos`, `exp`, `log`, `atan`, `re`, `im`, ...); all 16 matrix tests
    (MatrixSymbol/MatMul/MatPow/Transpose/Trace/Determinant/MatrixSlice/BlockMatrix/
    element sets); a `Symbol` handler reading old assumptions.
  - **~9 not handler-addressable:** `context=` kwarg (`test_custom_context`),
    `global_assumptions` (`test_global`), custom predicate/handler registration
    (`test_key_extensibility`, `test_type_extensibility`, `test_custom_AskHandler`,
    `test_polyadic_predicate`), relational predicate mapping (`test_relational`,
    `test_issue_28127`), numeric evaluation (`test_Add_queries`).
- Monkeypatched extra number getters fixed `test_zero_0` and `test_nan` outright. For
  nonzero reals, `expr.is_antihermitian` is `None`, so `antihermitian(1) -> False` needs
  a derived fact (e.g. real & nonzero implies not antihermitian, or antihermitian is
  equivalent to imaginary-or-zero for numbers).
- Known facts contain `zero -> hermitian | antihermitian` but not the converse, so
  `Q.hermitian(I)` cannot be refuted from `imaginary(I)` + `antihermitian(I)`; a handler
  fact is required. This was initially suspected to be a propagation bug; it is not.

## Suggested next steps

1. Extend the number handler first (cheap, fixes ~12 tests): getters for
   `antihermitian`, `hermitian`, `algebraic`, `transcendental`, `commutative`,
   `extended_real`, `finite`, plus derived number facts.
2. Add Add/Mul/Pow structural facts (parity, sign, closure), then elementary-function
   handlers, then matrix-expression handlers (largest group, 16 tests).
3. Decide whether beating upstream `satask` should keep failing
   `compare_backends.py`; otherwise every improvement will be reported as a mismatch.
