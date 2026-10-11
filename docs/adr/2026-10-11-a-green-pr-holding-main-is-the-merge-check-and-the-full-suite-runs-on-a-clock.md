# A green pull request that holds main is the merge check; the full suite runs on a clock

- Date: 2026-10-11
- Status: accepted
- Modules: ci
- Tree: `docs/tree/dec-tests-harden-they-do-not-build.md`

## Context
Measured 2026-10-11: CI runs of 28-35 minutes, and every merge to `main` triggered another whole
suite (34 minutes) on the same machine, competing with the pull requests waiting to merge. That run
re-verified a tree the pull request's own run had already verified.

## Decision
`.github/workflows/ci.yml` runs on `pull_request` only; the `push: branches: [main]` trigger is
gone. The verification of a merge is the pull request's green run on a head that contains
`origin/main` (`bin/dev/safe_merge.sh` already refuses anything else). The full safety run on `main`
comes from the 4-hour clock of #166 (host template `ci-host.yml`; the agent-os variant is #168).

## Consequences
A merge no longer costs a second full suite. A regression that slips past a green pull request is
caught by the next clock run, up to four hours later, instead of on the merge itself.
