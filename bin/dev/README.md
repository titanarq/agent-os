# bin/dev

- `run_suite.sh`, `suite_index.py`, `suite_show.py`: the whole suite in the background and its index.
- `wait_checks.sh <repo> <PR> [max_minutes]`: CI of the PR's head; exit 0 means every check SUCCESS.
- `safe_merge.sh <repo> <PR>`: merge commit only if all checks SUCCESS and the head holds origin/main.
  `--group <integration PR> [--after <sha>]` is the mode `agent-os-integrate land` uses for a member
  of a passed group.
- `agent-os-integrate plan|build|result|land|record|report` (installed command, not a script here):
  lands two or more ready pull requests under one CI instead of one at a time; the control plane's
  Duty 4 calls it when `integrator.enabled` is true, and it merges only through `safe_merge.sh --group`.
  See `docs/adr/2026-10-11-the-integrator-*.md` and the integrator step of `docs/ADOPTION.md`.
