# Agent report: a soundness fuzzer for satask handlers

- **Date:** 2026-09-22
- **Status:** tool implemented on branch `agent/handler-fuzzer` (based on `main`
  `29cca2e`); no handler code touched
- **Scope:** `tools/check_soundness.py`, `reasoning/tests/test_check_soundness.py`
- **Read this if:** you are adding or auditing handler facts and want to know
  whether a definite `satask` answer is true, not just whether it matches a
  validation expectation
- **Stale after:** changes to `reasoning/satask.py`'s answer semantics, the
  model value pools, or the curated regression list
- **TL;DR:** the validation suites measure how many queries get answered; this
  tool checks whether the answers are sound. It catches the T1 and T2
  unsoundness on `cde5c70`, and is clean on `agent/tail-audits` across the
  curated regressions plus 470 random queries (with matrices). One upstream-shared
  counterexample (the `imaginary` closed-group rule) is reported only under
  `--strict`.

## What it does

`tools/check_soundness.py` generates queries (a curated regression list plus
random propositions and assumptions) and checks each definite answer against
two oracles:

1. **Concrete models.** Each symbol is assigned a value, the assumptions are
   evaluated with `sympy.ask` on the ground atoms, and only satisfying
   assignments are kept. A definite answer contradicted by any model is
   unsound.
2. **`sympy.ask`.** When `ask` returns a definite answer for the same query and
   `satask` returns the opposite, the result is reported.

It also reports assumptions that raise `Inconsistent assumptions` even though a
model exists, and propositions whose negation gets the same definite answer.
Missing deductions (`None` where `ask` is definite) are expected while handlers
are being added and are not findings.

Some handlers deliberately mirror SymPy rules that a concrete model can
contradict, such as the closed-group rule that a sum of imaginary arguments is
imaginary even when the sum cancels. A model counterexample is therefore only
reported when `sympy.ask` does not return the same definite answer; `--strict`
reports those upstream-shared counterexamples as well.

## Usage

The script imports `reasoning` from the environment, so point `PYTHONPATH` at a
checkout to audit its handlers:

```console
.venv/bin/python tools/check_soundness.py
PYTHONPATH=/path/to/worktree .venv/bin/python tools/check_soundness.py \
    --seed 11 --cases 100 --model-tries 400
```

Exit status is 1 when a finding is reported. `--early-return` also audits
`early_return=True` answers, `--no-oracle` drops the `ask` comparison, and
`--no-matrices` / `--no-relations` narrow the generator.

## Results

| Checkout | Queries | Findings | Upstream-shared |
|---|---|---|---|
| `cde5c70` (pre T1/T2 fix), curated | 10 | 2 (T1, T2) | 1 |
| `main` `29cca2e`, curated | 10 | 0 | 0 |
| `agent/tail-audits` `67fb3ed`, curated | 10 | 0 | 1 |
| `agent/tail-audits`, seeds 2-5, 100 random each | 440 | 0 | 1 per run |
| `agent/tail-audits`, seed 21 with matrices | 70 | 0 | 1 |

The T1 and T2 findings on `cde5c70` are exactly the bugs fixed by
`agent/tail-hermitian` and `agent/tail-positive`: `satask` returned `False` for
`Q.hermitian(x + I)` under `Q.imaginary(x)` (witness `x = -I`) and for
`Q.positive(x**I)` under `Q.positive(x)` (witness `x = exp(2*pi)`). T3
(`algebraic(exp(x)) | algebraic(x)`) is not flagged because plain `satask`
already returns `None`; the bug only appears under the validation harness's
`_exp_is_pow(True)` mode, which the fuzzer does not set.

The one upstream-shared counterexample is
`imaginary(x + y) | imaginary(x) & imaginary(y)` with witness `x = -I, y = I`;
`ask` answers `True` as well, and the T1 audit explicitly preserved that rule.

## Caveats

- Model coverage is finite. The value pools include the witnesses for the known
  bugs (`-I`, `exp(2*pi)`, `0`), but a new bug whose only witness is outside the
  pool will be missed.
- Cases whose assumptions have no model in the pool, or whose ground atoms are
  unknown to `ask`, are skipped and counted in the summary. The default
  `--model-tries 200` skips roughly half of the random queries; raise it for
  better coverage.
- Relation assumptions are restricted to real operands, so complex comparisons
  do not abort model search.

## Next steps

- Run the fuzzer against each tail/matrix worktree before merging handler
  changes; `--strict` gives the upstream-shared list for review.
- A fixed-seed, small-case run could gate CI once its runtime is acceptable
  (about 40s for 70 queries on this machine).
- The generator could grow function families and LRA relation patterns once the
  handler set stabilizes.
