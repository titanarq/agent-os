# The suite runs in parallel with pytest-xdist

- Date: 2026-10-11
- Status: accepted
- Modules: ci, dev tooling
- Tree: `docs/tree/dec-tests-harden-they-do-not-build.md`

## Decision
The whole suite runs with `pytest -n 6` in CI and by default in `bin/dev/run_suite.sh`; `pytest-xdist` is a dev
dependency installed by `bootstrap.sh`. A caller can override the worker count (`-n 0` is serial).

## Why
Measured on 2026-10-11 on an 8-core machine under load: serial 40.5 min, `-n 6` 9.2 and 9.4 min, 2101 passed and
0 failed in all three runs, no new failures. The suite needs no database, network or backend, so tests are
independent. The suite is not reduced: selecting tests is a separate concern (#168).

## Consequences
Worker count is a fixed 6, not derived from the core count, so CI and local runs behave alike. A test that starts
depending on shared global state would fail intermittently under xdist; fix it, do not drop `-n`.
