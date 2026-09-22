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

Routine comparisons (including ASV) exclude only
`test_query::test_known_facts_consistent`. That test regenerates SymPy's own
known-fact dictionary without exercising either substituted backend. Selection
uses normalized test identities, so it works for the temporary SymPy wrappers
and does not exclude other tests marked `slow`.

```sh
python validation/compare_backends.py --output validation.json
python validation/compare_backends.py --include-controls
```

Plain `python -m pytest validation` also retains the complete upstream suite.
The pin check verifies installation metadata; it does not replace the generated
facts consistency check. Upstream test bodies are unchanged.

The default collection now has 103 tests instead of 104, and each backend's
passed count drops by one solely because of this exclusion. ASV's pass-count
series have a new version to mark that discontinuity. The JSON report preserves
per-test outcomes and failure details for both backends, so an improvement and
a regression cannot disappear into an unchanged total. CI uploads this report.

Wall time and the slowest-test table describe **validation execution cost**.
They are diagnostic, not performance scores: a newly passing assertion can let
a test execute additional queries. ASV calls this `track_validation_wall_time`;
use the [fixed-workload benchmarks](../benchmarks/README.md) for engine speed.
