# Agent report: would expanding sathandlers pass more validation tests?

- **Date:** 2026-09-22 (final update - audit and tail work merged to `main`)
- **Status:** investigation complete; all four planned units landed on `main` (merge
  `4ceae4b` of branch `agent/tail-audits`, tip `9320542`, pushed to the `bot` remote).
  Earlier stages: number facts landed directly on `main`; the 2a/2b structural and
  function work landed as branch `agent/add-mul-pow-and-function-facts` (`cde5c70`),
  later folded into `agent/tail-audits`.
- **Scope:** `validation/test_query.py` + `validation/test_matrices.py` against pinned
  SymPy `ddbb536d` (1.15.0.dev)
- **Read this if:** you are editing `reasoning/sathandlers.py`, `reasoning/functionfacts.py`,
  `reasoning/matrixfacts.py`, `reasoning/symbolfacts.py`, `reasoning/numberfacts.py`, the
  known-facts layer in `reasoning/knownfacts.py` / `reasoning/sympy_adapter.py`, or trying
  to raise the validation pass rate beyond **79/104**.
- **Stale after:** any change to those modules, the comparison policy in
  `validation/compare_backends.py`, the SymPy pin, or the validation results
- **TL;DR:** `main` now reaches **79/104** on the two validation suites (40/104 when this
  investigation started; 52/104 when the 2a/2b branch was first measured). SymPy full
  `ask` is 94/104, SymPy `satask` 24/104. The remaining 15 failures are capped: 4 are
  proven terminal or impossible in a global SAT fact base, 2 need upstream's
  handler-local zero-blindness, and 9 are non-handler/API features.

## Final results

| Gate | Result |
|---|---|
| `validation/test_query.py` + `test_matrices.py` | **79 passed / 15 failed / 2 xfailed / 8 xpassed** |
| `test_matrices.py` alone | 19 passed / 0 failed / 2 xfailed / 3 xpassed |
| `pytest reasoning/tests` on `main` | 180 passed / 1 xfailed |
| `mypy` (strict) | clean, 46 source files |
| `tools/check_old_assumptions.py reasoning` | 0 findings from this work; 2 pre-existing findings in `reasoning/lra_adapter.py` (LRA work already on `main`) |

## What landed

- **Number facts** (`198df09`) and the old-assumption checker (`bbe3031`) on `main`.
- **2a Add/Mul/Pow structural facts** (`3840c36`, `82e4186`) and **2b elementary
  functions** (`fc0e6c6`, `3b34d49`), merged as `cde5c70`; net +12 tests over `main`.
- **Four over-inference audits** appended to that branch:
  - `8a1dba6` (T1): scope `imaginary -> ~hermitian` away from `Add` subjects.
  - `26df87a` (T2): guard the Pow imaginary-exponent realness rule with
    `NOT(Q.positive(base))`, plus a rational-base rule keeping `positive(2**I)` False.
  - `98b1d61` (T4): stop emitting `real(sin/cos(arg))` for `Number` args. This is a
    **workaround**: the root cause is the cancellation-unsound `_add_imaginary_facts`
    closed-group rule (`allargs(imaginary) -> imaginary(Add)`); revert T4 if that rule
    ever gets a cancellation guard.
  - `15a4338` (T3-A): `NOT(Q.zero(expr))` guards on the parity-negative inferences in
    `_mul_hermitian_facts`; narrower alternative `a629d94` (T3-B) left unmerged.
- **Gap P** (`fe333b3`): Pow/Mul tails - `test_real_pow`, `test_nonzero`.
- **Gap F** (`b011b70`, `a4603ab`): Add finite closure, same-sign unboundedness, function
  value-at-zero facts, `complex(exp(x))`, `real(exp(x)**x)`.
- **Bounded audit** (`3eb3232`, test-only): proves `test_bounded:1108` is *forced* by
  earlier assertions 1076/1081/1094; upstream's `None` comes from a handler-local bail
  that a monotone fact base cannot express.
- **Matrix core** (`5c1356c`): new `reasoning/matrixfacts.py` (~450 lines) covering
  MatrixSymbol, Identity/Zero/One, explicit matrices (numeric `det()`), MatAdd, MatMul,
  MatPow, Transpose, Inverse, MatrixSlice, BlockMatrix, BlockDiagMatrix,
  Determinant/Trace, HadamardProduct, Factorization, DFT, MatrixElement. Matrix suite
  went 2P/17F -> 18P/1F.
- **Symbol bridge** (`8773c97`): new `reasoning/symbolfacts.py` harvests *declared* symbol
  assumptions through the public new-assumptions API (`sympy.assumptions.ask.ask`), with a
  per-symbol cache; `sympy_adapter.add_known_facts` asserts them as local premises unless
  the query mentions the same predicate explicitly. This keeps
  `tools/check_old_assumptions.py` at 0 findings (no `.is_*`/`.assumptions0` reads in
  reasoning code); compound expressions are still never probed with old assumptions.
- **Matrix dense** (`b3337be`): explicit dense/Sparse hermitian/antihermitian via
  pairwise `entry - conjugate(mirror)` checks (refutation gated to symbol-free
  differences so the complex `z` cases stay `None`), plus MatPow
  `integer(e) & negative(e) & invertible(X) & real_elements(X) -> real_elements(X**e)`.
  Combined with the bridge this also flipped matrix-suite `test_field_assumptions`.

Merges: `ebe3162` (audits), `e533b38` (gap F), `e533b38`..`67fb3ed` (matrix core),
`9320542` (matrix dense), then `main` at `4ceae4b`. The only merge conflict was the
`knownfacts` import in `sympy_adapter.py` after PR #3's sympy-free known-facts refactor.

## Remaining 15 failures by group

| Group | Count | Tests and why they are capped |
|---|---|---|
| Terminal tails | 4 | `test_I` (upstream `ask` itself returns None; needs old-assumption `is_integer`), `test_bounded` (line 1108 forced by 1076/1081/1094), `test_hermitian` + `test_imaginary` (global-SAT `Exclusive(real, imaginary)` versus `test_real_pow:2057`; upstream answers each test inconsistently via handler short-circuiting) |
| Old-assumption-flavored | 2 | `test_integer` (`integer(sqrt(2)*x)` -> False) and `test_prime` (`prime(4*x)` -> False); upstream's handlers ignore the `x = 0` case |
| Non-handler/API | 9 | `test_global` (`global_assumptions`), `test_custom_context` (`context=` kwarg), `test_key_extensibility`, `test_type_extensibility`, `test_custom_AskHandler`, `test_polyadic_predicate` (custom predicate/handler registration), `test_relational` (relational predicates), `test_Add_queries` (numeric evaluation), `test_issue_28127` |

## Findings that still hold

- The adapter imports SymPy's complete known predicate facts, so predicate-to-predicate
  relations are mostly not the gap. The encoding polarity in the known-facts template is
  correct.
- Handler work also requires curating the known-fact layer for clauses class facts cannot
  express; the branch adds the `_extra_predicate_facts` table in `sympy_adapter.py`.
- The fundamental ceiling is architectural: upstream `ask` is handler-local and
  short-circuits on the expression class, so it can return mutually inconsistent answers
  across tests (documented for `imaginary`/`hermitian`, `finite(exp(x))` versus
  `complex(exp(x))`, and the Mul finite bail). A monotone global SAT fact base cannot
  reproduce those inconsistencies; each was a deliberate trade-off choice, documented in
  `/tmp/opencode/agent-notes/cross-findings.md`.
- Full `ask` passes every test still failing here, so the suite itself is not the ceiling;
  the gap is the handler/old-assumption machinery `ask` has and `satask` does not.

## Next steps (remaining ~15 tests, all non-structural)

| Unit | Status | Remaining work | Test payoff |
|---|---|---|---|
| 3a. Context/global assumptions | not started | accept and honor the `context=` kwarg; merge `sympy.assumptions.assume.global_assumptions` into the premise set (the symbol bridge is the template) | 2 |
| 3b. Extensibility | not started | custom predicate registration (`key_extensibility`, `type_extensibility`, `custom_AskHandler`, `polyadic_predicate`) via the local registry | 4 |
| 3c. Relational and numeric | not started | `test_relational` and `test_Add_queries` need relational-predicate facts and numeric evaluation paths in `satask` | 2 |
| 3d. Old-assumption-flavored | deliverable unlikely | matching upstream requires porting its zero-blind Mul handlers | 2 |
| - | terminal | the four capped tails above | 4 |

Projected total if 3a-3c land: **~89/104**; 3d would push to ~91/104 at the cost of
soundness that earlier audits deliberately restored.

Calibration: `numberfacts` was ~320 fact lines plus ~270 test lines and netted 14 tests;
the full 2a-2d arc added 2113 lines across 11 files (facts, matrix support, the symbol
bridge and tests) and netted 27 tests over the 2a/2b branch's own 12. Tests are
all-or-nothing, so a single missing rule keeps a whole test red; the payoffs above are
per-unit ceilings.
