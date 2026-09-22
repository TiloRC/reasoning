# Agent report: adversarial soundness hunt for the sathandlers facts

- **Date:** 2026-09-22
- **Status:** tests + report on branch `test/sathandlers-adversarial` (merge of
  `main` + `feature/sathandlers`); no product code touched
- **Scope:** `reasoning/tests/test_soundness_adversarial.py` and this report
- **Read this if:** you are fixing the known `~Q.complex(1/x)` Pow bug and want
  to know which other facts are still unsound after the two proposed Pow guards
- **Stale after:** changes to `reasoning/sathandlers.py`,
  `reasoning/functionfacts.py`, `reasoning/matrixfacts.py`, the known-fact
  template, or `tools/check_soundness.py`'s model pools
- **TL;DR:** 20 adversarial tests pin soundness bugs that are *not* the known
  `1/x` case.  On the unfixed tip all 20 fail.  With the two proposed Pow guards
  applied locally, 19 still fail; the guards only fix the zero-base
  algebraic/complex closure test.  The fuzzer itself found two of the findings
  with the guards applied (`--engine random --cases 500 --seed 1` and
  `--no-matrices --cases 1000 --engine random --seed 7`); the rest are outside
  the fuzzer's grammar or model pools.

## Method

Worktree `/tmp/opencode/test-adversarial`, `PYTHONPATH` pointed at it so the
fuzzer imports its handlers.  Three passes:

1. **Fuzzer baseline** (`tools/check_soundness.py` on the unfixed tip): curated
   cases, Hypothesis engine, random engine seeds 1-7, `--strict`, and the
   no-matrix 1000-case run.
2. **Targeted probing** of the families named in the task: Pow singularities,
   Mul with zero/infinity, Add imaginary/sign cancellation, Abs/sign,
   functionfacts at `0` and at infinities, matrix expression facts, and
   declared symbol assumptions.  Each candidate was checked with a concrete
   model (substitution plus `ask` on ground atoms, or direct evaluation for
   matrices) and with `sympy.ask` on the original query.
3. **Shallow-fix experiment.**  The two guards from the other agents'
   hypothesis were applied locally (uncommitted): `_pow_closure_facts` gets
   `AND(_allargs(Q.complex, expr), defined)` on the complex closure, and
   `_pow_algebraic_facts` gets `OR(NOT(Q.zero(base)), NOT(Q.negative(exp)))` on
   the algebraic closure.  The fuzzer and the probes were re-run; the local
   edit was reverted before committing.

## Fuzzer results

| Run | Findings | Upstream-shared |
|---|---|---|
| tip, curated + 60 Hypothesis | 1 (`zero(x) \| ~complex(1/x)`) | 2 |
| tip, `--engine random --cases 500 --seed 1` | 2 (`zero(x) \| ~complex(1/x)`, antihermitian composite) | 2 |
| tip, `--strict`, curated + 60 Hypothesis | 3 (incl. `imaginary(x + y)` closed group) | 0 |
| tip, `--no-matrices --cases 1000 --engine random --seed 7` | 2 (`zero(x) \| ~complex(1/x)`, spurious inconsistency) | 2 |
| guards, curated + 60 Hypothesis | 0 | 1 |
| guards, seeds 1-5, 500 random each | seed 1: antihermitian composite; seeds 2-5: 0 | 1 per run |
| guards, `--no-matrices --cases 1000 --engine random --seed 7` | 1 (spurious inconsistency) | 1 |

An additional audit with `use_lra_theory=True` (150 random cases, seed 3) found
nothing.

The fuzzer's model pools explain most of the blind spots: `SCALAR_VALUES` has
no `oo`/`zoo`/`nan`, `hypothesis_cases` never uses declared symbols, matrix
atoms are always plain `MatrixSymbol`s (never `A**-2`, `A*B`, slices), and the
scalar grammar has no `acos`, `factorial`, or `evaluate=False` nodes.

## Findings and minimal reproductions

All line references are to the tip.  "Sound" is the answer a complete sound
solver would give; "actual" is the tip's answer.  Every finding below survives
the two known Pow guards (verified in step 3), except where noted.

### 1. Imaginary-sum cancellation makes real predicates `False`

`_extra_predicate_facts` (sympy_adapter.py:137) adds
`imaginary(subject) -> ~extended_real(subject)` for every non-`Add` subject,
but `_add_imaginary_facts` derives `imaginary(x + y)` from
`imaginary(x) & imaginary(y)` even when the sum cancels.  The consequence
chain reaches every real predicate.

```python
x, y = symbols("x y")
satask(Q.real(x + y), Q.imaginary(x) & Q.imaginary(y))          # False, sound None
satask(Q.extended_real(x + y), Q.imaginary(x) & Q.imaginary(y)) # False, sound None
satask(Q.integer(x + y), ...)                                   # False, sound None
satask(Q.rational(x + y), ...)                                  # False, sound None
satask(Q.zero(x + y), ...)                                      # False, sound None
satask(Q.even(x + y), ...)                                      # False, sound None
satask(Q.nonnegative(x + y), ...)                               # False, sound None
satask(Q.nonpositive(x + y), ...)                               # False, sound None
```

Model `x = I, y = -I`: `x + y = 0`, so all eight propositions are true.
`sympy.ask` returns `None` for all eight (it only shares the
`imaginary(x + y)` conclusion itself).  The fuzzer can generate this class
(both `I` and `-I` are in the pool) but did not in seeds 1-7.

### 2. `positive(acos(x))` under `zero(x - 1)`

`_acos_facts` (functionfacts.py:100) derives `positive(acos(x))` from
`nonnegative(x + 1) & nonpositive(x - 1)`, but `acos(1) = 0`.

```python
satask(Q.positive(acos(x)), Q.zero(x - 1))  # True, sound False (or None)
```

`x = 1` satisfies the assumption and `acos(1) == 0`; `ask` returns `None`.

### 3. `integer(factorial(n))` for negative integers

`_factorial_facts` (functionfacts.py:212) has no nonnegativity guard, but
`factorial(-1) = zoo`.

```python
n = symbols("n", integer=True)
satask(Q.integer(factorial(n)), Q.integer(n))  # True, sound None
```

`n = -1` gives `zoo`; `n = 2` gives `2`.  `ask` returns `None`.

### 4. Function values at infinities claim to be finite

`_exp_facts` and `_sin_cos_facts` assert `Q.complex(expr)` unconditionally, and
`complex -> finite`; `_re_facts`/`_im_facts` do the same.

```python
satask(Q.finite(exp(x)), Q.infinite(x))  # True, sound None (x = -oo -> 0)
satask(Q.finite(E**x), Q.infinite(x))    # True, sound None
satask(Q.finite(re(x)), Q.infinite(x))   # True, sound False (re(oo) == oo)
satask(Q.finite(im(x)), Q.infinite(x))   # True, sound None (im(oo) == 0, im(zoo) == nan)
```

For `exp` and `E**x`, `sympy.ask` returns `False`, so these are
oracle-disagreements as well as model counterexamples.

### 5. Infinite base with a negative integer exponent is not zero/rational

`_pow_facts` (`zero(expr) <-> zero(base) & positive(exp)`) and
`_pow_rational_facts` rule 6 (`~algebraic(base) & integer(exp)` gives
`rational(expr) <-> zero(exp)`) both miss `oo**-1 = 0`.

```python
xi = symbols("xi", infinite=True)
yi = symbols("yi", integer=True, negative=True)
satask(Q.zero(xi**yi))      # False, sound True  (ask True -> oracle disagreement)
satask(Q.rational(xi**yi))  # False, sound True  (ask None)
```

`xi = oo, yi = -1` gives `0`.

### 6. Spurious inconsistencies on satisfiable assumptions

All of these raise `ValueError: Inconsistent assumptions` although a model
exists, because an unconditional function fact contradicts the assumption.

```python
satask(Q.positive(x), ~Q.finite(exp(x)))          # raises; x = oo works
satask(Q.positive(x), ~Q.finite(Abs(x)))          # raises; x = oo works
satask(Q.positive(x), ~Q.finite(re(x)))           # raises; x = oo works
satask(Q.positive(x), ~Q.finite(im(x)))           # raises; x = zoo works
satask(Q.positive(x), ~Q.finite(Abs(log(x))))     # raises; x = 0 works
satask(Q.positive(x), ~Q.complex(exp(x)))         # raises; x = oo works
satask(Q.positive(x), ~Q.complex(Abs(x)))         # raises; x = oo works
satask(Q.positive(x), ~Q.complex(re(x)))          # raises; x = oo works
satask(Q.positive(x), ~Q.real(re(x)))             # raises; x = oo works
```

The fuzzer found this family independently with the guards applied:
`--no-matrices --cases 1000 --engine random --seed 7` reports `random-417`,
`~Q.finite(Abs(log(x)))` with model `{x: 0, y: 1/2, z: exp(2*pi)}` (the
minimal query above is `~Q.finite(Abs(log(x)))` alone).

A second inconsistency: with `infinite(x) & zero(y)`, `_pow_closure_facts`
claims `~complex(x**y)` (because the base is not complex) while
`_pow_rational_facts` claims `rational(x**y)` (because `~algebraic(base)` and
`integer(exp)`), and `rational -> complex`.  `x = oo, y = 0` gives `1`.

```python
satask(Q.complex(x**y), Q.infinite(x) & Q.zero(y))   # raises; sound True
satask(Q.rational(x**y), Q.infinite(x) & Q.zero(y))  # raises; sound True (ask True)
satask(Q.zero(x**y), Q.infinite(x) & Q.zero(y))      # raises; sound False
```

A third: a declared zero symbol makes the mixed hermitian/antihermitian Pow
rules inconsistent (`_pow_hermitian_fact` says the odd power is hermitian,
`_pow_antihermitian_facts` rule 3 says it is antihermitian, and 0 is both but
rule 1 says it is neither).  `xz**3 == 0` is antihermitian.

```python
xz = symbols("xz", zero=True)
satask(Q.antihermitian(xz**3))   # raises; sound True
satask(Q.antihermitian(1/xz))    # raises; sound False (zoo is not antihermitian)
```

### 7. Unevaluated Pow values answered wrongly

The `_pow_facts` zero equivalence and the `Pow(2, 0)` rules disagree with the
actual values when `evaluate=False` is used.

```python
satask(Q.zero(Pow(S.Zero, oo, evaluate=False)))       # False, ask True (0**oo == 0)
satask(Q.zero(Pow(S.Zero, 1 + I, evaluate=False)))    # False, ask True (== 0)
satask(Q.zero(Pow(oo, -1, evaluate=False)))           # False, ask True (== 0)
satask(Q.complex(Pow(oo, 0, evaluate=False)))         # raises (== 1)
satask(Q.real(Pow(S(2), S.Zero, evaluate=False)))     # raises (== 1)
```

### 8. Matrix facts with concrete counterexamples

`sympy.ask` does not decide element predicates of explicit matrices, so these
were checked by substituting the model and evaluating the result.

```python
A, B = MatrixSymbol("A", 2, 2), MatrixSymbol("B", 2, 2)

satask(Q.square(ZeroMatrix(2, 3)))                    # True, ask False
satask(Q.integer_elements(MatPow(A, -2)),
       Q.integer_elements(A) & Q.invertible(A))       # True; A = diag(2, 1)
satask(Q.integer_elements(A*B), ~Q.integer_elements(A))
                                                      # False; A = diag(1/2, 1), B = diag(2, 1)
satask(Q.real_elements(A*B),
       ~Q.real_elements(A) & ~Q.real_elements(B))     # False; A = i*I, B = [[0, i], [-i, 0]]
satask(Q.integer_elements(A + B),
       ~Q.integer_elements(A) & ~Q.integer_elements(B))
                                                      # False; A = B = diag(1/2, 1)
satask(Q.real_elements(A + B),
       ~Q.real_elements(A) & ~Q.real_elements(B))     # False; A = i*I, B = -i*I
satask(Q.integer_elements(HadamardProduct(A, B)),
       ~Q.integer_elements(A))                        # False; A = diag(1/2, 1), B = diag(2, 1)
satask(Q.fullrank(MatrixSlice(A, slice(0, 1), slice(0, 1))),
       Q.fullrank(A))                                 # True; A = [[0, 1], [1, 0]]
```

The root causes are `_zeromatrix_facts` asserting `Q.square` unconditionally,
the negative exponent branch of `_matpow_facts` reusing the element-predicate
rule without an invertibility caveat for `integer_elements`, the negative
direction of `_matmul_facts` / `_matadd_facts` / `_hadamard_facts`, and
`_matrixslice_facts` transferring `fullrank` (and `invertible`, `unitary`,
`orthogonal`) to diagonal slices.

### 9. Antihermitian Pow with a zero-capable hermitian base

`_pow_antihermitian_facts` rule 1 says `hermitian(base) & integer(exp)` makes
the power not antihermitian, but `re(z) = 0` makes `re(z)**2 = 0`, which is
antihermitian.  `sympy.ask` shares the atomic answer, so this is
`--strict`-only at the atom level, but the fuzzer reported the composite with
`--engine random --cases 500 --seed 1` on both the tip and with the guards:

```python
satask(Q.antihermitian(re(z)**2))                       # False, sound None
satask(~Q.prime(pi) ^ Q.antihermitian(re(z)**2), Q.algebraic(0))
                                                        # True, sound None (z = I)
```

## What the two known guards miss

The guards only touch the complex closure and the algebraic closure of `Pow`.
They fix exactly one test in the new file
(`test_zero_base_negative_exponent_is_not_algebraic_or_complex`); everything
else survives:

- The `_pow_closure_facts` **exactly-one-argument** direction has no guard at
  all, which is what makes `Pow(oo, 0, evaluate=False)` and
  `Pow(2, 0, evaluate=False)` inconsistent.
- The closure guard uses `NOT(Q.negative(exp))`, so non-real exponents with a
  zero base (`0**I = nan`, `0**(-I) = zoo`) still pass: `complex(x**I)`,
  `real(x**(-1/2))`, `finite(x**I)`, `hermitian(x**-1)` under `zero(x)` stay
  wrong.
- `_pow_facts`, `_pow_rational_facts`, `_pow_finite_fact`, `_pow_sign_facts`,
  `_pow_hermitian_fact`, `_pow_antihermitian_facts` are untouched.
- All `Add`, `Mul`, function, matrix, and symbol-fact families are untouched.

Upstream-shared blind spots (reported only by `--strict`, but still missed by a
narrow guard) include the zero-base non-real-exponent cases above,
`zero(x*y)` under `zero(y) & infinite(x)` (`0 * oo = nan`), and
`antihermitian(x**2)` under `antihermitian(x)`.

## Tests added

`reasoning/tests/test_soundness_adversarial.py`, 20 tests.  Status on the
unfixed tip: **20 failed** (plus the pre-existing `201 passed, 1 xfailed`).
Status with the two local guards: **19 failed, 1 passed**
(`test_zero_base_negative_exponent_is_not_algebraic_or_complex` is the one the
guards fix).

| Test | Tip | Guards |
|---|---|---|
| `test_imaginary_sum_cancellation_does_not_imply_not_real` | fail | fail |
| `test_acos_positivity_interval_excludes_one` | fail | fail |
| `test_factorial_integer_needs_nonnegative_argument` | fail | fail |
| `test_finite_of_unbounded_arguments` | fail | fail |
| `test_infinite_base_negative_integer_exponent_is_zero` | fail | fail |
| `test_unbounded_function_arguments_do_not_make_assumptions_inconsistent` | fail | fail |
| `test_infinite_base_zero_exponent_does_not_raise` | fail | fail |
| `test_unevaluated_pow_zero_exponent_does_not_raise` | fail | fail |
| `test_zeromatrix_shape_is_not_always_square` | fail | fail |
| `test_matpow_negative_exponent_does_not_preserve_integer_elements` | fail | fail |
| `test_matmul_element_predicates_are_not_closed_under_negation` | fail | fail |
| `test_matadd_element_predicates_are_not_closed_under_negation` | fail | fail |
| `test_hadamard_element_predicates_are_not_closed_under_negation` | fail | fail |
| `test_matrix_slice_does_not_transfer_fullrank` | fail | fail |
| `test_antihermitian_pow_with_zero_capable_hermitian_base` | fail | fail |
| `test_zero_symbol_pow_does_not_raise` | fail | fail |
| `test_zero_base_negative_exponent_is_not_algebraic_or_complex` | fail | **pass** |
| `test_zero_base_pow_values_are_not_answered_false` | fail | fail |
| `test_narrow_guard_blind_spots_for_zero_base` | fail | fail |
| `test_narrow_guard_blind_spots_for_mul_and_pow_parity` | fail | fail |

The tests assert the sound answer rather than the current one, so the file is
expected to stay red until the underlying facts are fixed.  The matrix tests
document the concrete model in a comment because `sympy.ask` cannot check
element predicates of explicit matrices.

## Recommended follow-ups

- Add a nonzero-base guard to the exactly-one direction of
  `_pow_closure_facts` and to `_pow_facts`'s zero equivalence.
- Give `_pow_rational_facts` rule 6 and `_pow_antihermitian_facts` the same
  kind of singularity guard the algebraic rule is getting.
- Do not assert `Q.complex`/`Q.real`/`Q.finite` unconditionally for
  `exp`, `re`, `im`, `Abs`, `sin`, `cos`; gate them on the argument being
  finite (or on the function value being defined).
- Add `~Q.zero(base)` (or `Q.nonzero(expr)`) to the hermitian Pow rules.
- Gate the negative direction of the element-predicate closures in
  `_matmul_facts`, `_matadd_facts`, `_hadamard_facts`, and the `MatPow`
  negative-exponent branch on the result's structure, not just the factors'.
- Restrict `_matrixslice_facts` transfers to the predicates a principal
  submatrix actually preserves.

## Caveats

- The fuzzer's model pool has no `oo`, `zoo`, or `nan`, no declared symbols,
  and no matrix expressions; five of the findings here need one of those.
  Widening `SCALAR_VALUES` and the atom strategy would let the fuzzer catch
  the infinite-base and function-at-infinity families automatically.
- `evaluate=False` Pow inputs are unusual, but they are accepted by `satask`
  and the resulting inconsistencies show the fact set is not just incomplete
  but contradictory.
- `sympy.ask` shares several of the counterexamples (noted per finding), so
  `--strict` should be consulted before deciding whether to fix upstream-shared
  rules or only the non-shared consequences.
- No LRA-specific unsoundness was found, but the LRA audit was small (150
  random cases).
