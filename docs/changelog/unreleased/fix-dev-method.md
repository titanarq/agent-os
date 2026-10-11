- Developer method (no issue; branch `fix/dev-method`) -- applies the owner's 2026-10-10 rule on tests to
  `AGENTS.md` ("How a task starts" 4 and "Definition of done"): a defect found in use is reproduced by a test
  that fails first; something new the owner has not used yet gets no new tests
  (`dec-tests-harden-they-do-not-build`); the existing suite keeps passing whole. `docs/AGENT_OS.md` grows only
  when a behaviour it already describes changes. Changelog notes now go in `docs/changelog/unreleased/<branch>.md`
  (one file per branch) instead of `docs/CHANGELOG.md`, which ends the conflict every parallel PR had there.
  `bin/dev/` holds the index tools the method names (`run_suite.sh`, `suite_index.py`, `suite_show.py`,
  `wait_checks.sh`, `safe_merge.sh`): read the suite's one-line index and CI's one-line result, never a log.
  `CLAUDE.md` is cut to what `AGENTS.md` does not say.
