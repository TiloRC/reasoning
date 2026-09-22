# Agent report: unary known-fact theory for the reasoning core

- **Date:** 2026-09-22
- **Status:** prototype implemented and measured on branch
  `investigate/unary-known-facts` (nothing committed); no behavior change
  unless `satask(..., use_unary_theory=True)` is passed
- **Scope:** replacing the per-subject known-fact materialization in
  `SympyAdapter.add_known_facts` with a forward-chaining-style unary theory in
  the style of sympy/sympy#27835 (`facts2.py` / `forward_chaining_theory.py`),
  plus the `theory_prop`-style solver hook that turned out to be required
- **Read this if:** you are deciding whether to land a theory layer for the
  predicate facts, want to shrink the clause database, or are extending the
  four-method `TheorySolver` protocol
- **Stale after:** changes to `reasoning/unary_theory.py`,
  `reasoning/unary_adapter.py`, `reasoning/solver.py`,
  `reasoning/sympy_adapter.py` (`_known_template`), the `_known_template`
  selection in `add_known_facts`, or the pinned SymPy's
  `ask_generated.py`
- **TL;DR:** yes, it helps. The per-subject known-fact template disappears
  from the clause database (sum10: 1161→270 clauses, 367→92 variables; 891
  known-fact clauses removed) and the answers are unchanged (2500-query
  randomized differential: 0 disagreements; pinned validation suites: same
  40/54/8/2 outcomes). Check-only is *complete* but search-fragile: on the
  `nested` benchmark it is ~1.9x **slower** than baseline, and it is sensitive
  to Python's hash randomization (3.4–18.5 ms across processes before fixing
  the subject order). A `theory_prop`-style hook in `_simplify`, with
  explanation clauses, is required for a robust win: all five benchmark cases
  are then 1.35–3.5x faster than baseline and run-to-run stable. Non-Horn
  clauses are handled exactly by the template's model masks; dropping them for
  Horn-only forward chaining loses answers (58/600 random queries went from a
  definite answer to `None`).

## 1. What was built

Three new modules, an optional protocol extension, and wiring:

| File | Contents |
|---|---|
| `reasoning/unary_theory.py` | SymPy-free theory: `CompiledTemplate` (CNF over predicate indices → independent components + model bitmasks), `UnaryTheory` (`assert_lit`/`check`/`push_level`/`pop_level` + `propagate`) |
| `reasoning/unary_adapter.py` | SymPy-facing: rebuilds `add_known_facts`'s subject/kind selection, compiles the template once per `(numbers, matrices)` pair, maps materialized predicate atoms to solver variables |
| `reasoning/tests/test_unary_theory.py` | 23 tests: template compilation, propagation cores, level undo, solver/engine integration, default-vs-theory answer parity, clause-count pin |
| `reasoning/theory.py` | new `PropagatingTheory` protocol (optional `propagate()`); `TheorySolver` unchanged |
| `reasoning/solver.py` | `_theory_propagate()` called from `_simplify` (solver.py:662, 837) |
| `reasoning/satask.py` | `use_unary_theory: bool = False` (satask.py:32); `get_facts_and_subjects` (satask.py:118) returns the exact `subjects | visited` set `add_known_facts` receives |
| `benchmarks/satask.py` | `--unary` flag and a `theory_build_ms` phase |

The default path is untouched: no theory is built, `_known_template` and
`add_known_facts` are still used, and the only core change is the no-op
`_theory_propagate()` call when no theory is registered. The pinned
`benchmarks.satask` baseline is within noise of the pre-change run
(7.08 ms vs 7.17 ms for sum10).

## 2. How theory atoms appear in the solver (Q1, part 1)

`SATSolver` cannot gain variables after construction (`add()` rejects
literals above `len(variable_set)`, solver.py:491-494), so the theory is built
**after** discovery, assumption assertion, and query compilation, from the
finished `ClauseDB`:

```
db, known_subjects = get_facts_and_subjects(prop, assump, iterations)  # no known facts
assert_formula(assump, db)
query = compile_formula(prop, db)
unary = build_unary_theory(db, known_subjects)   # satask.py:61-79
```

This ordering is load-bearing: assumption/query atoms such as `Q.positive(x)`
are not necessarily allocated during discovery, so building the theory
earlier leaves them unmapped. `build_unary_theory` looks up
`db.encoding[Q.<pred>(subject)]` for all 31/17/48 template predicates per
subject (unary_adapter.py:31); predicates the database never allocated are
simply absent and the solver never hears about them. Explanation clauses are
built only from mapped variables, so the `add()` restriction is respected.
For sum10, 66 of the 341 template atoms are materialized and 275 are
suppressed; the solver shrinks from 367 to 92 variables.

The theory never needs `theory_prop` to be *correct*: `check()` is called at
every model yield (solver.py:650-660) and rejects assignments that cannot be
extended to a template model. `check` is exact because the template's model
set is enumerated once (64 number models, 400 matrix models) and a partial
assignment is consistent iff the intersection of the corresponding model
bitmasks is non-empty. This is what lets the per-subject clauses vanish.

## 3. Why check-only is not enough (Q1, part 2, measured)

`use_unary_theory` uses propagation; `build_unary_theory(..., 
enable_propagation=False)` gives the check-only comparison. Medians of 15–25
runs, one process per row:

| case | default total | check-only total | propagating total |
|---|---:|---:|---:|
| simple | 0.399 ms | 0.130 ms | 0.109 ms |
| nested | 2.45 ms | 4.7–5.4 ms | 2.06–2.11 ms |
| sum10 | 7.52 ms | 3.54–3.66 ms | 5.16–5.78 ms |
| matrix | 0.21 ms | 0.125 ms | 0.112 ms |

Check-only is complete but the DPLL search has to enumerate theory-inconsistent
total assignments; one explanation clause is learned per conflicting model. On
`nested` (`Q.zero(x*(x+y))` under `Q.positive(x) & Q.positive(y)`) that is
331 decisions vs 14 in the default path, and the check-only mode is ~1.9x
slower than baseline even though it has 132 clauses instead of 456.

It is also order-sensitive: when the theory subjects were built from the
`subjects` **set**, Python's per-process hash randomization changed the
propagation list order enough to swing `nested` between 3.4 ms and 18.5 ms
across processes. `unary_adapter.py:45` now sorts the subjects by `str`;
after that the spread is 4.7–5.4 ms. The propagating mode was 2.06–2.11 ms in
the same runs.

The hook: theories opt in by defining `propagate()`; `_theory_propagate`
(solver.py:662) adds the entailed clause `[literal, *explanation]` with
`_simple_add_learned_clause` and queues `literal` for unit propagation. A
conflict is reported as a pair whose literal is already false (the first
element of the conflict clause), which drives the existing `is_unsatisfied`
path. `UnaryTheory.propagate` (unary_theory.py:317) computes, per subject and
component, the models still consistent with the assignment; a predicate whose
bitmask excludes them all is forced, and its explanation is a deletion-
minimized core of the assigned literals. Propagating made every benchmark
case faster than baseline:

| case | default total | unary total (`--unary`) | ratio | clauses | vars |
|---|---:|---:|---:|---:|---:|
| simple | 0.379 ms | 0.119 ms | 3.19x | 82→1 | 31→2 |
| nested | 2.736 ms | 1.998 ms | 1.37x | 456→132 | 159→73 |
| sum10 | 7.084 ms | 5.247 ms | 1.35x | 1161→270 | 367→92 |
| matrix | 0.221 ms | 0.127 ms | 1.74x | 26→2 | 17→3 |
| contradiction | 0.326 ms | 0.094 ms | 3.45x | 83→2 | 31→1 |

(`benchmarks.satask --repeat 25`, median; the per-case saved clauses are
81/324/891/24/81, i.e. `subjects × template size`.)

This differs from #27835's experience where `theory_prop` was disabled as
slower. Differences worth noting: the core removes the known-fact variables
too, the masks are 64/400-model bitmasks rather than per-literal implication
chains, only materialized predicates are reported, and the explanation cores
are minimized. Upstream's comparison also ran against a different base
formula and solver.

## 4. Non-Horn clauses (Q2)

Counts from `_known_template`: the **number** template has 81 clauses, 66 Horn
and **15 multi-positive** (touching 27 of 31 predicates); the **matrix**
template has 24 clauses, 22 Horn and **2 multi-positive**
(`lower_triangular | ~triangular | upper_triangular` and
`singular | invertible`, touching 5 of 17 predicates). Examples:
`prime & ~composite` can split into `even | odd`/`positive | ...`, matrix
`diagonal` facts come from `triangular -> lower | upper`.

The prototype keeps **none** of them per subject: the model masks are computed
over the full template, so non-Horn case splits are enforced exactly. A
Horn-only fallback would change answers. Patching `_known_template` to keep
only clauses with at most one positive literal (everything else dropped) and
running the 600-query random differential:

- 61 mismatches vs the full template; 58 of them turned a definite
  `True`/`False` into `None` (the other 3: one `ValueError` became `None`,
  2 others).
- Concrete examples: `satask(Q.zero(x), Q.nonnegative(x) & Q.nonpositive(x))`
  (needs `~nonnegative | positive | zero`) True→None;
  `satask(Q.singular(A), ~Q.invertible(A))` (needs `singular | invertible`)
  True→None; `satask(Q.real(Abs(x)))` (needs
  `~nonnegative | positive | zero` plus `positive -> real`,
  `zero -> real`) True→None.

So "keep the 15+2 encoded and forward-chain the rest" is the sound Horn-only
design, but it only removes 66/81 clauses per number subject while still
allocating 27/31 predicates, and it reintroduces a per-subject clause class
that the mask approach avoids for free. Recommendation: handle non-Horn
clauses inside the theory; only fall back to materialization if model
enumeration ever becomes infeasible (see risks).

## 5. Behavior-preservation checklist (Q3)

The full unit suite was also run with `use_unary_theory` forced on for every
internal call (one-line local default flip, reverted afterwards; the committed
default is `False`): **158 passed, 1 xfailed**, identical to the default run.
The named tests were exercised in that run:

- `test_disconnected_assumptions_still_checked` (test_satask.py:462): the
  `~Q.positive(y) & Q.positive(y)` contradiction becomes an empty clause in
  `assert_formula`, so `ReasoningEngine.__init__` raises before the theory is
  consulted (verified directly with the flag on).
- `test_satask_early_return` (test_satask.py:432): with the hook, root-level
  theory implications are re-derived during the root `propagate()` and
  materialized as unit clauses, so `fixed()` still sees `Q.real(x)` under
  `Q.positive(x)`, and the query conjunction (`Q.real(x) & Q.nonzero(x)`)
  is still root-forced. All eight assertions match.
- `test_python_boolean_constants_and_zero_iterations` (:451):
  `iterations=0` still supplies `known_subjects` from `relevant_subjects`
  (discovery is what is limited, not the subject set); `Q.nonnegative(Abs(x))`
  with `iterations=0` is `None`, `iterations=1` is `True`, and
  `Q.real(x)` under `Q.positive(x)` is `True` via theory propagation.
  Python constants and `satask(True, False)` value errors are unchanged.
- `test_issue_27467` (:397): counts `class_fact_registry(s)` clauses only; no
  known-fact involvement.
- `test_get_relevant_clsfacts` (:383): `get_relevant_clsfacts` never adds
  known facts, so the pinned clause output is unchanged (suite green).
- `use_known_facts=False`: `use_unary_theory` is a no-op and no theory is
  built (satask.py:61-62), verified with `satask(Q.real(x), Q.positive(x),
  use_known_facts=False, use_unary_theory=True) is None`.
- Kind selection: `build_unary_theory` recomputes the same
  `NumberKind/UndefinedKind` and `MatrixKind(NumberKind)` flags from the same
  `subjects | visited` set (unary_adapter.py:42-51 vs sympy_adapter.py:149-150).
  The combined case is a disjoint union; the compiler splits it into
  components `[64, 400]` instead of enumerating 25600 product models
  (`test_combined_template_keeps_components_separate`).
- Subjects: `get_facts_and_subjects` (satask.py:118) returns exactly
  `subjects | visited`, the argument `add_known_facts` used to receive.

Validation (`pytest validation/test_query.py validation/test_matrices.py -q`,
pinned SymPy):

| mode | outcome | wall |
|---|---|---|
| default | 40 passed, 54 failed, 8 xfailed, 2 xpassed | 54.01 s |
| unary forced | 40 passed, 54 failed, 8 xfailed, 2 xpassed | 53.30 s |

No test changed outcome; wall time is within noise.

Randomized differential (fresh queries, both modes, 2500 combinations of 27
predicates over `x, y, z, x+y, x*y, x**2, Abs(x)` with `&`, `|`, `~`, `>>`):
**0 answer mismatches, 0 errors**, including `ValueError` comparison. The
only anomalies were isolated >30 ms spikes in both directions (4 default, 5
theory) that did not reproduce warm (e.g. `Q.integer(x)`: 0.13 ms theory vs
0.54 ms default when measured in isolation).

## 6. Risks and open items

1. **Template-selection duplication.** `unary_adapter.py` re-implements the
   `numbers`/`matrices` logic and the subject set comes from a new discovery
   helper. Any future change to `add_known_facts`/`discover_facts` can drift.
   Factor `_select_template` into `sympy_adapter` or keep the differential
   tests mandatory if the two paths are expected to agree.
2. **Model-mask growth.** Compilation enumerates models per connected
   component: 64 and 400 today. If SymPy ever links the number and matrix
   predicates, the product (25600 models) would be enumerated but is still
   only ~150 KB of masks; if new facts explode the number component's model
   count, compile time and memory grow. The `_compiled` LRU (maxsize 3) pays
   ~5 ms once per process for the current templates.
3. **Learned clauses during propagation.** Every implied literal adds its
   explanation clause to the solver and bumps VSIDS scores via
   `_simple_add_learned_clause`, even under `clause_learning='none'`. Only
   27–36 clauses were added in the benchmark cases, but a pathological query
   could add many. A budget or a separate storage path is a possible
   follow-up.
4. **Protocol is duck-typed at runtime.** `_theory_propagate` uses
   `getattr(theory, "propagate", None)`; the `PropagatingTheory` protocol is
   only a typing aid. A theory with an incompatible `propagate` would fail at
   runtime with a confusing error.
5. **Check-only is order-sensitive and slower in the worst case** (3.4–18.5 ms
   across processes before sorting; 4.7–5.4 ms after). Keep propagation on for
   any future opt-in switch.
6. **Solver core changed on the default path.** The hook is inert without a
   propagating theory and the suite/benchmarks show no regression, but it is
   still a change to `_simplify` that upstream-style review should look at
   (sentinels, occurrence counts, clause growth).
7. **Interaction coverage.** LRA+unary was smoke-tested only
   (`use_lra_theory=True, use_unary_theory=True` answers correctly on
   `Q.real(x)|Q.positive(x)` and `Q.gt`); the `add-mul-pow-and-function-facts`
   branch (richer handler facts) was not tested at all. More subjects mean
   more theory mappings; expect the same behavior but verify.
8. **`db.data` and memory.** The clause database shrinks, but learned
   explanation clauses live only in `SATSolver.clauses`; `benchmarks.satask`'s
   `clauses` metric still reports the small `db.data` count, which is the
   right "encoding size" number but understates runtime clauses.

## 7. Recommendation

1. **Do not land a check-only unary theory as a default-path optimization.**
   It is sound and behavior-preserving, but it can be slower than the clauses
   it replaces and its performance is order-sensitive.
2. **If the theory is pursued, land it as an opt-in mode (as prototyped) with
   the `propagate` hook.** The hook is additive, theories without
   `propagate()` are unaffected (LRA, the toy `Exclude` theory), the unit
   suites and the 2500-query differential are clean, and the clause/variable
   reduction is real: sum10 is 270 clauses / 92 variables instead of 1161 /
   367, and 1.35x faster; the other four benchmark cases are 1.37–3.45x
   faster. The validation suites keep the same outcomes.
3. **Keep the default `use_unary_theory=False` until there is an explicit
   policy decision**, mirroring the LRA prototype. The natural next experiment
   is to force it on in the SymPy-side harness the same way the LRA report
   suggests, once the handler branch is merged.
4. **Before enabling by default**, remove the template-selection duplication,
   decide the clause-growth policy for propagation explanations, and rerun
   the differential on the merged handler branch.

## 8. Files changed in the worktree (not committed)

- New: `reasoning/unary_theory.py`, `reasoning/unary_adapter.py`,
  `reasoning/tests/test_unary_theory.py`
- Modified: `reasoning/theory.py`, `reasoning/solver.py`,
  `reasoning/satask.py`, `benchmarks/satask.py`
- Report: `agent-reports/2026-09-22-unary-known-facts-theory.md`

## 9. Sources

- Background: `agent-reports/2026-09-21-theory-solver-research.md` (§2 on
  sympy/sympy#27835, §7 insertion points),
  `agent-reports/2026-09-21-lra-theory-prototype.md`,
  `agent-reports/2026-09-21-sathandlers-validation-triage.md`.
- Code: `reasoning/sympy_adapter.py:109-162` (`_known_template`,
  `add_known_facts`), `reasoning/solver.py:650-690,837`,
  `reasoning/theory.py:50`, `reasoning/satask.py:32,61-79,118`.
- Measurements: `python -m benchmarks.satask --repeat 25 [--unary]`,
  `python -m pytest reasoning/tests -q`,
  `python -m pytest validation/test_query.py validation/test_matrices.py -q`,
  randomized differential (2500 queries) and Horn-only experiment scripts
  (kept out of the worktree).
