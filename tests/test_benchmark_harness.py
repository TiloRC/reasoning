"""Protect benchmark selection and correctness guards, without timing assertions."""
import json
import sys

import pytest

from asvbench import pipeline
from asvbench._workloads import NAMES
from validation import compare_backends as harness


@pytest.mark.parametrize("backend", harness.BACKENDS)
@pytest.mark.parametrize("include_controls", [False, True])
def test_named_control_selection(tmp_path, monkeypatch, backend, include_controls):
    # An unrelated slow test must still run. The control fails if executed,
    # making this check independent of measured duration or the upstream body.
    source = '''import pytest
@pytest.mark.slow
def test_known_facts_consistent():
    assert False, "control executed"
@pytest.mark.slow
def test_backend_slow():
    pass
def test_regular():
    pass
'''
    suite = tmp_path / "test_query.py"
    suite.write_text(source)

    def write_sympy_suite(directory, original):
        target = directory / f"{original.stem}_sympy.py"
        target.write_text(source)
        return target

    monkeypatch.setattr(harness, "write_sympy_suite", write_sympy_suite)
    outcomes, _, _, _ = harness.run_backend(
        backend, [suite], [], include_controls=include_controls)
    expected = {"test_query::test_backend_slow": "PASSED",
                "test_query::test_regular": "PASSED"}
    if include_controls:
        expected["test_query::test_known_facts_consistent"] = "FAILED"
    assert outcomes == expected


def test_pytest_collection_failure_is_not_progress(tmp_path):
    suite = tmp_path / "test_broken.py"
    suite.write_text("raise RuntimeError('broken collection')\n")
    with pytest.raises(RuntimeError, match="pytest failed with exit code 2"):
        harness.run_backend("reasoning", [suite], [])


def test_cli_preserves_per_test_outcomes(tmp_path, monkeypatch):
    report = tmp_path / "outcomes.json"
    monkeypatch.setattr(sys, "argv", ["compare_backends", "--output", str(report),
                                     "--timings", "0"])

    def run(backend, suites, args, *, include_controls):
        assert not include_controls
        outcomes = {"test_query::test_a": "PASSED", "test_query::test_b": "FAILED"}
        if backend == "sympy":
            outcomes = {"test_query::test_a": "FAILED", "test_query::test_b": "PASSED"}
        return outcomes, {}, {"test_query::test_b": "failure detail"}, 1.0

    monkeypatch.setattr(harness, "run_backend", run)
    with pytest.raises(SystemExit) as result:
        harness.main()
    # Both backends have one pass, but the regression must remain visible.
    assert result.value.code == 1
    saved = json.loads(report.read_text())
    assert saved["backends"]["reasoning"]["outcomes"]["test_query::test_b"] == "FAILED"
    assert saved["backends"]["sympy"]["outcomes"]["test_query::test_b"] == "PASSED"
    assert saved["excluded_controls"] == list(harness.CONTROL_TESTS)


@pytest.mark.parametrize("name", NAMES)
def test_pipeline_answer_contracts(name):
    benchmark = pipeline.Pipeline()
    benchmark.setup(name)
    benchmark.time_satask(name)


def test_lost_answer_fails_timing_but_is_recorded(monkeypatch):
    benchmark = pipeline.Pipeline()
    benchmark.setup("simple")
    monkeypatch.setattr(pipeline, "satask", lambda *args: None)
    with pytest.raises(AssertionError, match="answer changed"):
        benchmark.time_satask("simple")
    with pytest.raises(AssertionError, match="answer changed"):
        benchmark.setup("simple")
    outcomes = pipeline.Outcomes()
    outcomes.setup("simple")
    assert outcomes.track_answer("simple") == -1


def test_solve_repeats_start_with_fresh_engine():
    benchmark = pipeline.Solve()
    benchmark.setup("upstream_integer")
    first = benchmark.engine
    assert first._model_values is None
    benchmark.time_solve("upstream_integer")
    assert first._model_values is not None
    benchmark.setup("upstream_integer")
    assert benchmark.engine is not first
    assert benchmark.engine._model_values is None
    benchmark.time_solve("upstream_integer")
    assert benchmark.number == 1
    assert benchmark.warmup_time == 0
