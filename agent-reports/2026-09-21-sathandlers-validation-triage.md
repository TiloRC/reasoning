# Agent report: would expanding sathandlers pass more validation tests?

- **Date:** 2026-09-21 (updated same day after commits `bbe3031`, `198df09`)
- **Status:** investigation complete; the first recommended milestone (number facts) has
  already landed, so the numbers and plan below are newer than the original version
- **Scope:** `validation/test_query.py` + `validation/test_matrices.py` against pinned
  SymPy `ddbb536d` (1.15.0.dev)
- **Read this if:** you are editing `reasoning/sathandlers.py`, `reasoning/numberfacts.py`,
  the known-facts import in `reasoning/sympy_adapter.py`, or trying to raise the
  validation pass rate
- **Stale after:** any change to `sathandlers.py`, `numberfacts.py`, `sympy_adapter.py`,
  the comparison policy in `validation/compare_backends.py`, the SymPy pin, or the
  validation results
- **TL;DR:** Yes, but "expand sathandlers" is 3-4 commits, not one. Current:
  reasoning **40/104**, SymPy `satask` 24/104, full SymPy `ask` 94/104. Of the 54
  remaining failures, ~45 are handler-addressable but split into matrix (18),
  Add/Mul/Pow closure (18), elementary functions (6), 2 old-assumption-flavored cases,
  and a Symbol bridge (1); 9 need non-handler infrastructure. Projected landing after
  all handler work: **~73-78/104**.

## Current results

```
.venv/bin/python validation/compare_backends.py --timings 0   # exit 0
.venv/bin/python -m pytest validation/test_query.py validation/test_matrices.py -q --tb=line
.venv/bin/python -m pytest reasoning/tests -q                 # 74 passed, 1 xfailed
```

- `compare_backends.py` now exits 0 under the updated policy (working-tree change,
  possibly uncommitted when you read this): "reasoning passes, SymPy does not" is an
  improvement, not a mismatch; "same outcome, different failure" is informational.
  Exit 1 only when SymPy passes a test reasoning fails, or another non-improvement
  outcome disagreement. It reports 16 improvements.
- Since the original report, `198df09` replaced the old-assumption number getters with
  `reasoning/numberfacts.py` (static per-class tables plus `isprime`, no `is_*` reads),
  and `bbe3031` added `tools/check_old_assumptions.py`, an advisory AST checker that
  flags reliance on old assumptions (`is_*`, `assumptions0`, assumption keywords).
  Result: 26 -> 40 passed; all 14 number-class failures named in the original version
  now pass.

## Remaining 54 failures by group

| Group | Count | Notes |
|---|---|---|
| Matrix expressions | 18 | 17 `test_matrices.py` tests plus `test_matrix` |
| Add/Mul/Pow structural | 18 | parity, sign, closure, commutativity, algebraic/transcendental; e.g. `test_pi` now stops at `Q.algebraic(pi + 1)`, `test_I` at `Q.commutative(1 + I)` |
| Function-dependent | 6 | `test_bounded`, `test_positive`, `test_real_functions`, `test_algebraic`, `test_issue_5833` (`log`), `test_issue_7246` (inverse trig) |
| Old-assumption-flavored | 2 | `test_integer` (`integer(sqrt(2)*x)` -> False), `test_prime` (`prime(4*x)` -> False); upstream likely answers via old assumptions |
| Symbol old-assumption bridge | 1 | `test_check_old_assumption`; `tools/check_old_assumptions.py` flags exactly this |
| Non-handler / API | 9 | `context=` kwarg, `global_assumptions`, custom predicate/handler registration (4), relational predicates (2), `test_Add_queries` numeric evaluation |

## Findings that still hold

- The adapter already imports SymPy's complete known predicate facts, so
  predicate-to-predicate relations are mostly not the gap. The encoding polarity in
  `_known_template` is correct; an apparent inversion was a false alarm about
  `Literal.is_Not` semantics.
- Not a propagation bug: the earlier `Q.hermitian(I)` mystery was missing facts (known
  facts carry `zero -> hermitian | antihermitian`, not the converse), and `numberfacts`
  now supplies the missing number facts directly.
- Handler work also requires curating the known-fact layer for clauses class facts
  cannot express (e.g. `hermitian & imaginary -> ~hermitian`).
- Full `ask` passes every test still failing here, so the suite itself is not the
  ceiling; the gap is the handler/old-assumption machinery `ask` has and `satask` does
  not.

## Properly scoped next steps (the old "step 2" was too broad)

| Unit | What it needs | Rough size | Test payoff |
|---|---|---|---|
| 2a. Add/Mul/Pow closure | ~20-30 facts over sign, parity, real/complex/finite/extended_real/algebraic/transcendental/imaginary/hermitian | one file, `numberfacts` scale | ~14-16 |
| 2b. Elementary functions | `sin/cos/tan/cot/asin/acos/atan/acot/exp/log/Abs/re/im/factorial`, several predicates each, plus branch semantics for `log` and fractional powers | comparable to 2x `numberfacts` | ~4-5 standalone, also unblocks assertions inside 2a tests |
| 2c. Matrix expressions | ~20 matrix classes x ~15 predicates (invertible, fullrank, symmetric, orthogonal, unitary, positive_definite, triangular, diagonal, element sets, ...) | largest unit; SymPy's matrix handler is several hundred dispatch rules | ~15-17 |
| 2d. Symbol old-assumption bridge | read `Symbol('x', real=True)` etc. | small | 1, but flagged by `tools/check_old_assumptions.py` |

Calibration: `numberfacts` was ~320 fact lines plus ~270 test lines and netted 14
tests. Expect 2a about that size, 2b somewhat larger, 2c larger still. Tests are
all-or-nothing, so a single missing rule keeps a whole test red; the payoffs above are
per-unit ceilings, not additive guarantees. Projected total: 40 + 33-38 = **~73-78/104**.
