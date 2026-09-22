# Agent report: closing the soundness fuzzer's blind spots

- **Date:** 2026-09-22
- **Status:** branch `agent/fuzz-coverage` on top of `main` `b07b332` (the
  merged fuzzer from #8); tool-only, no handler code touched
- **Scope:** `tools/check_soundness.py` and
  `reasoning/tests/test_check_soundness.py`
- **Read this if:** you are fixing the remaining adversarial regressions, or
  you want the fuzzer to explore a query class it previously missed
- **Stale after:** changes to the model pools, the handler grammar, or PR #9's
  adversarial suite
- **TL;DR:** the fuzzer now generates declared symbols, infinities/undefined
  values, `evaluate=False` powers, extended-real predicates, `acos`,
  `factorial`, and matrix expressions, and expands matrix element predicates
  itself. On PR #9's tip it found a new crash: `satask` raises
  `TypeError: Invalid NaN comparison` for any unevaluated power with a `nan`
  exponent. The matrix fix branch (`cd0a061`) verifies clean.

## What changed

The adversarial report from PR #9 listed the fuzzer's blind spots; each is now
covered:

| Blind spot | Coverage |
|---|---|
| No `oo`/`zoo`/`nan` in `SCALAR_VALUES` | Added, plus `oo`/`-oo`/`zoo` to `CONSTANTS` and the extended-real predicates |
| No declared symbols | Added `n` (integer), `ni` (integer negative), `xi` (infinite); models are drawn from per-symbol pools filtered by the declared assumptions |
| Only plain `MatrixSymbol` subjects | Added `MatMul`, `MatPow`, `HadamardProduct`, `Transpose`, `MatrixSlice` and `ZeroMatrix`, plus the element predicates |
| `ask` cannot decide element predicates | `atom_truth` expands concrete matrices with `as_explicit` and asks about each element; only then falls back to `ask` |
| No `acos`/`factorial`/`evaluate=False` | Added to both the stdlib and Hypothesis grammars |

Assumptions are still satisfied by construction: the model is drawn first and
each generated literal is emitted with the polarity that makes it true.

## New finding: `nan` exponent crashes `_pow_real_facts`

Found by the random engine on PR #9's tip (`924c4a9`, `--engine random
--seed 1 --cases 500`), reduced to:

```python
satask(Q.algebraic(Pow(2, nan, evaluate=False)))  # TypeError, was None on main
satask(Q.real(Pow(x, nan, evaluate=False)))       # TypeError, was None on main
sympy.ask(Q.algebraic(Pow(2, nan, evaluate=False)))  # None
```

Root cause is `reasoning/sathandlers.py:468`:

```python
if (isinstance(exp, Number) and exp < 0
```

`S.NaN` is a `Number`, and `nan < 0` raises `TypeError: Invalid NaN
comparison`. The comparison needs a realness guard (or a `nan` short-circuit).
`main` returns `None` for these queries, so this is a regression from the new
Pow facts, and `sympy.ask` answers `None` rather than raising. The curated list
now includes `algebraic(Pow(2, nan, evaluate=False))`; it passes on `main` and
reports the crash on `924c4a9` and `cd0a061`.

## Verification runs

| Checkout | Run | Result |
|---|---|---|
| `main` `b07b332` | curated | 0 findings |
| PR #9 tip `924c4a9` | curated | 1 finding (the `nan` crash) |
| PR #9 tip | 150 Hypothesis examples | 0 findings |
| PR #9 tip | 500 random cases, seed 1 | 1 finding (the `nan` crash) |
| `fix/sathandlers-matrixfacts` `cd0a061` | adversarial + matrixfacts suites | 21 passed, 9 xfailed (scalar) |
| `fix/sathandlers-matrixfacts` | curated + 200 Hypothesis examples | only the `nan` crash; no matrix findings |

The 500-case random run takes about 11 minutes with the expanded grammar (the
infinities and undefined values make some `ask` calls slower); the Hypothesis
engine is much faster and is the better fit for quick checks.

## Notes

- The advisory old-assumptions scan gains four `keyword` findings from the
  declared symbols in the tool, matching the five PR #9 adds in its adversarial
  test file; the scan remains advisory and exits 0.
- `fix/sathandlers-scalar` owns the file with the `nan` crash. Once it lands,
  rerun `tools/check_soundness.py` against it and remove the curated case's
  finding from the remaining list.
- The curated list still tracks the Pow `~complex(1/x)` case, which is fixed on
  PR #9 and passes there.
