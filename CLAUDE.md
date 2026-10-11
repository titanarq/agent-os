@AGENTS.md

## Claude Code specifics

- **Long runs in the background.** Launch the suite with `bin/dev/run_suite.sh` and the CI wait
  with `bin/dev/wait_checks.sh` detached, then read the one line each prints (or the
  `suite.summary.json` index) and check the exit code; never the raw log or a `gh pr checks --watch`
  dump, which cost context for nothing. `pytest -q` block-buffers its dots anyway.
- **Hosts are siblings of this checkout.** Reading a host's checkout is fine.
