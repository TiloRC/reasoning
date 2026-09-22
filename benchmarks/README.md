# benchmarks

The benchmarks were made by agents that also designed the whole
repository, so they cannot be trusted to give a fair comparison. The
approach can be more flexible and help with development, though, so it
might still be useful.

## Correctness and speed in parallel

The upstream validation suites track correctness and supported behavior. ASV's
`asvbench/pipeline.py` separately measures fixed queries, regardless of which
assertion an upstream test currently reaches. No solver changes are required
to use these measurements.

| ASV benchmark | Measures |
| --- | --- |
| `pipeline.Pipeline.time_satask` | Complete query pipeline, including inconsistent assumptions |
| `pipeline.Phases.time_discovery_encoding` | Fact discovery, fact/assumption encoding, and query encoding on normalized inputs |
| `pipeline.Phases.time_engine_ctor` | Fresh engine construction from a prebuilt database |
| `pipeline.Solve.time_solve` | First query on a fresh engine, including the base consistency solve |
| `pipeline.Outcomes.track_answer` | Actual answer: -1 unknown, 0 false, 1 true, 2 inconsistent |
| `pipeline.Phases.track_clauses`, `track_variables` | Encoding size for each consistent query |
| `pipeline.SumScaling.*` | Query time and encoding size for sums of 10, 20, 40, and 80 terms |

Inputs combine the existing five handcrafted examples with individual
assertions from pinned SymPy's `test_integer` and `test_zero`. Their provenance
and expected results live in `asvbench/_workloads.py`. These are a small initial
sample, not evidence of universal performance superiority. Add representative
real workloads as performance work exposes gaps.

Timings check expected answers, including legitimate `None` results and the
specific inconsistency exception. A wrong answer fails the timing benchmark;
it cannot be recorded as a speedup. The separate answer series remains
available when a timing's contract fails. When behavior intentionally improves,
review the expected answer and bump the workload `VERSION` so the changed work
starts a new timing series. Also bump it for changed inputs or cache policy.

All timings use warm process caches: setup builds inputs and checks the answer
before measurement. Input construction is excluded. Discovery creates a fresh
database on every invocation; construction creates a fresh engine. Solve uses
`number = 1`, no warmup, and a fresh engine in each setup, avoiding accidental
measurement of an already cached base model. Inconsistent inputs are measured
end to end, rather than mixed into construction/solve phase timings.

## Running ASV

Install ASV 0.6.6 alongside the project's pinned dependencies. From a checkout:

```sh
python -m asv check --python=same
python -m asv run --python=same --quick --dry-run --show-stderr --bench 'pipeline\.'
```

The quick command is a smoke check, not a usable performance measurement. For
historical runs, `python -m asv run` manages per-commit environments. The config
sets `PYTHONHASHSEED=0` through ASV's `matrix.env_nobuild`. Keep hash seeds and
cache policy comparable; use multiple explicit seeds when checking whether a
finding generalizes. Host load warnings alone do not make measurements reliable.

On this development host, use `~/bin/bench-container` to lease and pin a CPU.
The Dockerfile installs the pinned SymPy dependency with its VCS metadata, plus
ASV and development tools. Use a standalone clone of the committed revision so
worktree Git pointers and concurrent edits do not affect the run:

```sh
bench-container build reasoning-bench:local . benchmarks/Dockerfile
git clone --no-hardlinks . /tmp/reasoning-bench-source
bench-container run reasoning-bench:local /tmp/reasoning-bench-source -- sh -ec '
    cp -a /work/. /tmp/source
    cd /tmp/source
    python -m venv --system-site-packages /tmp/venv
    /tmp/venv/bin/python -m pip install --no-deps --no-build-isolation -e .
    /tmp/venv/bin/python -m asv machine --yes
    /tmp/venv/bin/python -m asv run --python=same --bench "pipeline\." --show-stderr
    cp -a results /results/asv
'
```

The writable container copy accommodates ASV caches and the validation harness's
temporary wrappers; the host source remains read-only. For smoke checks add
`--quick --dry-run`. Keep A/B measurements within the same CPU lease or explicitly
set the same `BENCH_CPU`, hold competing load comparable, and alternate baseline
and candidate. Record the source commit and image digest with results. Runner
metadata records the allocated CPU/domain and hash seed defaults to zero.
