# Agent report: why the Pow closure soundness bug slipped through

- **Date:** 2026-09-22
- **Status:** investigation complete; regression tests and this report landed on
  `test/sathandlers-regressions` (base `a4f6e44`, merge of `main` +
  `feature/sathandlers`). No product code was changed here; the fix is owned by
  the `fix/sathandlers-soundness` agent.
- **Scope:** `reasoning/sathandlers.py` `_pow_closure_facts` /
  `_pow_algebraic_facts` (git history only), new
  `reasoning/tests/test_soundness_singularities.py`, run records in
  `tools/check_soundness.py`; no edit to any handler.
- **Read this if:** you are fixing the zero-base Pow guards, adding closure rules
  to `sathandlers.py` / `functionfacts.py`, wiring the soundness fuzzer into CI,
  or updating the validation triage expectations.
- **Stale after:** the two closure rules gain a domain guard, the fuzzer becomes
  a CI gate, or `validation/test_query.py`'s expectations for
  `test_complex:1301` / `test_algebraic:2220` change.
- **TL;DR:** `3840c36` (tilorc-bot, 2026-09-21) added thirteen Pow rules at once
  and guarded the `extended_real` and `finite` closures with
  `OR(NOT(Q.zero(base)), NOT(Q.negative(exp)))`, but left the `complex` and
  `algebraic` closures unguarded. Both are unsound at `0**negative = zoo`. The
  port followed SymPy's zero-blind *assumption handlers* instead of the guarded
  core evaluators (`Pow._eval_is_complex` calls `_eval_is_finite`;
  `Pow._eval_is_algebraic` handles `base.is_zero` first). No test ever asked a
  closure question with a possibly-zero base, the upstream validation suite
  actually asserts the unsound closure as `True`, and `tools/check_soundness.py`
  was never a CI gate. The finding was already documented in the fuzzer report
  (`agent-reports/2026-09-22-soundness-fuzzer.md`, "Next steps") before the
  branch merged, but the branch merged anyway. Four new regression tests fail
  on the unfixed tip and all eight pass with the two known guards applied.

## Findings

### 1. Code: the guard convention existed, two closure rules did not get it

`git blame` shows every line of the two rules is still from `3840c36`
("Add Add/Mul/Pow structural facts", tilorc-bot, 2026-09-21 23:25:03 +0000):

- `_pow_closure_facts` (sathandlers.py:431-441):
  - `extended_real` arm (line 439) *does* carry the guard, via a local
    `defined = OR(NOT(Q.zero(base)), NOT(Q.negative(exp)))` (line 433).
  - `complex` arm (line 436) has no guard.
- `_pow_algebraic_facts` (sathandlers.py:592-602): the
  `algebraic(base) & rational(exp) -> algebraic(expr)` rule (line 595) has no
  guard and the function does not even compute `defined`.

The same commit and its neighbors already used the guard pattern in five other
places, so this was an omission, not a missing concept:

| Rule | Guard | Line |
|---|---|---|
| `_pow_closure_facts` extended_real | `OR(NOT zero(base), NOT negative(exp))` | 439 |
| `_pow_finite_fact` | same | 610 |
| `_pow_real_facts` | same | 452-454 |
| `_pow_rational_facts` | `NOT zero(base)` / `OR(zero, positive(exp))` | 521-526 |
| `_pow_sign_facts` | `OR(NOT zero(base), positive(exp))` | 502-504 |

Later commits added guards only reactively, one fuzzer/validation finding at a
time: `26df87a` (Pow imaginary-exponent realness), `15a4338` + `a629d94` (Mul
hermitian/antihermitian zero products), `98b1d61` (sin/cos realness), `fe333b3`
(`0**negative` realness). `fe333b3` is the smoking gun: it explicitly reasons
about `0**negative` being complex infinity and patches `Q.real` only, leaving
the `complex` and `algebraic` closures untouched (and consistent with the
upstream even-denominator rule it mentions in its comment).

### 2. Why the singularity class was missed

**Transcription source.** SymPy has two layers. The core evaluators guard the
domain:

- `sympy/core/power.py:567-573` `Pow._eval_is_complex`: requires
  `self._eval_is_finite()`.
- `sympy/core/power.py:633-637` `Pow._eval_is_finite`: `exp.is_negative and
  base.is_zero -> False`.
- `sympy/core/power.py:1279-1287` `Pow._eval_is_algebraic`: `base.is_zero` is
  handled before the algebraic closure.

The *assumption handlers* do not: `ComplexPredicate` (sets.py:516) is a bare
`test_closed_group`, and `AlgebraicPredicate` (sets.py:785) returns `True` for
`base_algebraic & exp_algebraic & exp_rational` with no zero check. The port
copied the handler shape, so it inherited the handler's zero blindness and lost
the core evaluator's guard. `ask` is therefore unsound for the same queries
(`ask(Q.complex(1/x), Q.complex(x))` is `True`), which is exactly why the
oracle-only part of the fuzzer suppressed the closure rule and only the
*derived* query surfaced.

**No singularity test matrix.** `reasoning/tests/test_structural_facts.py`
(added in `82e4186`, the companion test commit to `3840c36`) exercises Pow
closure only through generic symbols: realness/parity/imaginary rules plus
`0**negative` for `Q.real`. There is no `complex(x**...)` or `algebraic(x**...)`
test at all, and no closure test where the base may be zero in the same test
file. A grep for `complex(x**` / `algebraic(x**` across `reasoning/tests/`
returns nothing.

**The validation suite asserts the unsound rule.** Upstream's own tests encode
the zero-blind behavior:

- `test_query.py:1301`: `Q.complex(x**y), Q.complex(x) & Q.complex(y)` is
  `True`.
- `test_query.py:2220`: `Q.algebraic(x**y), Q.algebraic(x) & Q.rational(y)` is
  `True`.

So the validation harness could never catch it: passing more of this suite and
being sound are in tension here. `test_bounded:1130`
(`Q.finite(x**y), Q.zero(x) & Q.negative(y)` is `False`) is the one upstream
expectation the current code satisfies only via the unsound complex chain, as
the guard experiment below shows.

**The fuzzer was not a gate.** `.github/workflows/ci.yml` at `a4f6e44` runs
unit tests, mypy, the known-facts regeneration check, the old-assumptions scan,
and the (informational) validation comparison. It has no `check_soundness`
step; the README documents the tool as a manual audit. PR #8 landed the fuzzer
on `main` (`b07b332`) with the `~complex(1/x)` finding already written up, and
its "Next steps" said to fix the closure before gating CI on it. The
`feature/sathandlers` work then merged into `merge-test/sathandlers2` as
`a4f6e44` with the fuzzer red, and CI was green because nothing ran it.

### 3. Fuzzer findings on `a4f6e44`

Reproductions (all run with `PYTHONPATH` pointed at this worktree):

| # | Query | satask | ask | status |
|---|---|---|---|---|
| 1 | `satask(Q.zero(x), ~Q.complex(1/x))` | `False` | `None` | reported; `x = 0` makes it `True` |
| 2 | `satask(Q.zero(x), ~Q.algebraic(1/x))` | `False` | `None` | same root cause |
| 3 | `satask(Q.complex(1/x), Q.complex(x))` | `True` | `True` | model counterexample, upstream-shared |
| 4 | `satask(Q.algebraic(1/x), Q.algebraic(x))` | `True` | `True` | model counterexample, upstream-shared |
| 5 | `satask(Q.finite(1/x), Q.zero(x))` | `True` | `False` | new in this audit; same complex->finite chain |
| 6 | `satask(Q.infinite(1/x), Q.zero(x))` | `False` | `True` | new; same chain |
| 7 | `satask(Q.finite(x**y), Q.zero(x) & Q.negative(y))` | `True` | `False` | same chain; hurts `test_bounded:1130` |
| 8 | `satask(~Q.prime(pi) ^ Q.antihermitian(re(z)**2))` | `True` | `None` | separate rule bug, see below |

Runs: default Hypothesis (1 finding + 2 upstream-shared), `--engine random
--cases 300..800 --seed 1..24`, six 500-example and six 1000-example Hypothesis
runs. Finding 8 appeared once (random-98 of seed 1) and finding 5 appeared once
(one Hypothesis run); finding 6 was only confirmed by direct query afterwards.
Everything else the runs reported was finding 1, which the curated list already
contained. Findings 5-7 are one root cause: `complex(1/x)` plus the known fact
`complex -> finite` was the only route to `finite(1/x)`.

**Finding 8 is a different rule and is not fixed by the two guards.**
`_pow_antihermitian_facts` (sathandlers.py:633-635) infers
`hermitian(base) & integer(exp) -> ~antihermitian(base**exp)`. At `base = 0`
with positive integer `exp` the power is `0`, which *is* antihermitian, so the
rule is unsound; the Mul analogue was guarded with `NOT(Q.zero(expr))` in
`15a4338`/`a629d94`, the Pow one was not. The atom-level claim is
upstream-shared (`ask(Q.antihermitian(re(z)**2))` is also `False`), but the
XOR query is a definite wrong answer that `ask` refuses to take a position on,
so the fuzzer reports it. Minimal repro:

```python
satask(~Q.prime(pi) ^ Q.antihermitian(re(z)**2))  # True
# z = I: re(z)**2 = 0 is antihermitian and ~prime(pi) is True, so the XOR is False
ask(~Q.prime(pi) ^ Q.antihermitian(re(z)**2))     # None
```

Same class of neighbor, upstream-shared, worth an audit when the complex guard
lands: `_pow_closure_facts`' "exactly one non-complex arg" arm
(sathandlers.py:437-438) answers `False` for `Q.complex(1/x)` under
`~Q.complex(x)`, but `oo**-1 == 0` is complex. `ask` gives the same `False`, so
it is suppressed by default.

### 4. The two guards fix the closure findings and one validation test regresses

Applying only the two known guards locally (adding `defined` to the complex arm
and to the algebraic rule, then reverting):

- New tests: 8/8 pass (4 fail on the unfixed tip).
- `tools/check_soundness.py --engine random --cases 300`: **0 findings**
  (1 upstream-shared).
- `reasoning/tests`: 209 passed, 1 xfailed; mypy strict clean.
- Validation: **77 passed / 17 failed** (was 79/15). The two new failures are
  `test_complex` at `test_query.py:1301` and `test_algebraic` at
  `test_query.py:2220`, i.e. the upstream assertions that encode the unsound
  rule. `test_bounded` was already failing.
- `satask(Q.finite(x**y), Q.zero(x) & Q.negative(y))` becomes `None` instead of
  the upstream-expected `False`; recovering that needs a separate
  `zero(base) & negative(exp) -> ~finite(expr)` rule (optional, out of scope).

## Regression tests added

`reasoning/tests/test_soundness_singularities.py`:

- `test_reciprocal_counterexample_is_not_refuted`: both `Q.zero(x)` queries.
- `test_complex_closure_needs_a_defined_power`: `1/x` and `x**-2`.
- `test_algebraic_closure_needs_a_defined_power`: same for algebraic.
- `test_nonnegative_rational_exponents_still_close`: `x**(1/2)`, `x**(3/2)`
  must still answer `True`, pinning the guard as `negative(exp)`, not
  `nonzero(base)` or `integer(exp)`.
- `test_zero_exponent_is_defined_for_every_base`: `Pow(x, 0, evaluate=False)`.
- `test_nonzero_base_still_closes`: `~Q.zero(x)` and `Q.nonzero(x)` cases.
- `test_nonreal_nonzero_base_still_closes`: `1/x` under `imaginary(x) &
  ~zero(x)`, pinning `~Q.zero` rather than `Q.nonzero`.
- `test_finiteness_does_not_leak_through_the_closure`: the `finite`/`infinite`
  consequences, asserted as "not a wrong definite answer" rather than an exact
  value.

## What to do differently

1. **Pair every closure rule with its domain guard in the same commit.** Add a
   shared `_power_defined(base, exp)` helper and use it in all
   closure/arithmetic rules, so a new rule cannot silently omit it.
2. **Port from `Expr.is_*`, not only from the assumption handlers.** When a
   rule mirrors `sympy/assumptions/handlers/`, check the core evaluator
   (`_eval_is_*`) for conditions the handler omits; the `complex` and
   `algebraic` gaps are exactly `_eval_is_finite()` / `is_zero` checks.
3. **Keep a singularity test matrix for every Pow/function rule:** base in
   {zero, may be zero, nonzero} x exponent in {negative int, negative rational,
   0, positive int, positive rational, symbolic}, with assertions for both
   directions (no definite answer through the singularity; inference still
   fires when the guard is satisfied). The new file is the Pow instance of that
   matrix.
4. **Run the fuzzer before merge and then gate on it.** Wire
   `tools/check_soundness.py` (curated + `--engine random --seed 30222 --cases
   300`, or a fixed-seed Hypothesis run) into CI as soon as the guards land.
   A documented "Next steps" fix must be a merge blocker: this finding was
   written up in the fuzzer report before `a4f6e44` merged.
5. **Treat `ask` as a secondary oracle.** Upstream shares the complex/algebraic
   closure unsoundness, so oracle-only comparison suppresses it. Concrete
   models (and the `--strict` shared list) are the primary signal, and a
   derived query such as `~complex(1/x) -> ~zero(x)` is often the unshared
   consequence that exposes a shared bad rule.
6. **Do not use the validation pass rate as a soundness gate.** Two upstream
   tests assert the unsound closure. When the guards land, move
   `test_complex:1301` and `test_algebraic:2220` into the documented
   known-mismatch set instead of weakening the guard, and update
   `agent-reports/2026-09-21-sathandlers-validation-triage.md`'s 79/104
   baseline accordingly.
7. **Audit the rest of the zero-blind family while here.** Known leftovers:
   `_pow_antihermitian_facts` (finding 8), the `~complex(x) -> ~complex(1/x)`
   arm (`oo**-1 == 0`), and the upstream-shared even-denominator realness rule
   for `0**negative-rational`, which `fe333b3` deliberately mirrored.
