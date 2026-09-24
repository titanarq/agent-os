# Changelog

One entry per merged task of the parent epic (titanarq/roedor#507 — the mechanism separates from
its host, extended by config, never modified per project), in the order the work landed. Every
entry names the task issue and the pull request that closed it; entries for a task that closed
several small issues at once name them all. This file starts on 2026-09-21, the day #508 moved the
mechanism into `agent_os/` — nothing from before that date describes this directory.

## Unreleased

- agent-os#35 — in a host that vendors the mechanism under `agent_os/`, a role's worktree now runs
  the worktree's copy of the mechanism, not the main checkout's. `PYTHONPATH=<worktree>` alone
  left `<worktree>/agent_os/` as a namespace portion (it has no `__init__.py`), so the regular
  package the mechanism venv's editable `.pth` puts on `sys.path` won, and a validator testing a
  `subtree pull` certified code it never ran. The drivers now export
  `PYTHONPATH=<worktree>:<worktree>/agent_os` there (unchanged where the mechanism is the
  repository root) and link `agent_os/.venv` into the worktree beside the root `.venv` and `.env`;
  a worker's persistent worktree gets the link only where git ignores it. The mechanism's
  `.gitignore` names `.venv` without the trailing slash so that link is ignored. The worktree
  isolation test measures the mechanism's own package in such a host instead of skipping.
- agent-os#10 — the guard-timer failure `agent-os-doctor` prints no longer sends a host to
  `docs/runbooks/agent_monitor.md`, a runbook only the first host ever had. It now says what to
  run (`systemctl --user enable --now <guard_unit>.timer`, once `agent-os-install` has written the
  unit) and names `agent_os/docs/ADOPTION.md` steps 20 and 22. The same dead reference is gone
  from the rendered `override.conf`'s comment and from the `doctor`/`install` docstrings. This
  also closes the second point of agent-os#5.
- agent-os#5 — `agent-os-doctor`'s board check no longer passes on a Project that is not the
  repository's: besides the `Status` field and its options, it reads the Projects linked to
  `project.repo` (`repository.projectsV2`) and fails when `project.board_number` is not one of
  them, naming the linked ones and the `gh project link` that would fix it. A `board_number: 1`
  copied from the example used to pass against whatever the owner's Project 1 was.
- agent-os#4 — `agent-os-doctor` reports every check even when `gh` fails inside one of them:
  a failed `gh` call (a `project.repo` that does not exist, say) or a `gh`/`systemctl` that is
  not installed turns that check into a `[FAIL]` carrying the error on one line, and the run
  continues instead of exiting after the labels check.
- agent-os#22 — `worker_task.sh resume` no longer refuses to relaunch a run the guard cut over
  that run's own diary: when `.state` line 1 records `CUT_BY_GUARD` and nothing is alive, the
  dirty check leaves out `scratchpad/progress.log` (` M` when tracked, `??` when untracked, and
  the collapsed `?? scratchpad/` only while the diary is the one file inside it). The file stays
  on disk untouched, for the monitor and the resumed run. Any other dirty path, and a diary over
  any other `.state` (`STARTED`, `RESUMED`, `DONE`, `FAILED_LAUNCH`, `BLOCKED`), still refuse. A
  cut followed by `resume` no longer needs a host's `info/exclude` entry for the diary.
- agent-os#3 — `agent-os-install` and `agent-os-doctor` no longer crash with a traceback when
  `config/agents.yaml` is missing, is not YAML or does not match the schema. `install` exits 1
  with one line naming the file (and, when it is missing, `ADOPTION.md` step 8); `doctor` reports
  it as a failed `config/agents.yaml loads` check and still runs the two checks that need no
  config (python version, `gh auth status`).
- agent-os#25 — the suite no longer leaves a `.cache/` in the checkout it runs from. The
  `rules` subcommands of `worker_task.sh` and `planner_task.sh` stop creating their cache
  directories. `test_agent_task.py`'s no-verdict cache moves out of the real `.cache`, and the
  `start` refusal tests get a disposable `WORKER_CACHE_DIR`. A conftest guard now fails any test
  that creates `<root>/.cache` when the session started without one.
- agent-os#12 — `agent-os-install` no longer renders a bare `python3` into the guard unit's
  `ExecStart=` when the host has a `scripts/agent_guard.py` shim but no root `.venv`: it uses the
  mechanism's own interpreter as `agent_os_python()` resolves it (`$AGENT_OS_PYTHON`, else the
  `.venv` `bootstrap.sh` builds), and refuses with a message naming `bootstrap.sh` and
  `AGENT_OS_PYTHON` when that is not an absolute path to an executable, in the module form too.
  Nothing is written in that case.
- agent-os#7 — `docs/ADOPTION.md` step 12 lists `wake:planner` among the labels a host creates
  by hand, next to `status:ai-completed`, `status:agents-paused` and `auto-ready`: those four are
  exactly what `agent-os-doctor` checks for, and a host that followed the old list failed the
  doctor's label check on its first run. Step 23 now says four labels, not three.
  `tests/test_adoption_doc.py` asks `doctor.check_labels` which labels it requires and fails when
  step 12 leaves one out.
- agent-os#18 — `worker_task.sh start` and `branch` no longer refuse the next dispatch over the
  previous run's diary: when `.state` records that run's ending (`DONE`, `CUT_BY_GUARD`,
  `FAILED_LAUNCH`, `BLOCKED`), nothing is alive and the untracked `scratchpad/progress.log` is the
  only dirty path, it is archived to `.cache/diaries/` and the dispatch proceeds. A diary whose run
  never recorded an end, any other leftover, and `resume` still refuse as before. A host's
  `info/exclude` entry or cleanup script for the file is no longer needed.
- agent-os#11 — the role prompts name no script under a host's own `scripts/`. The worker's
  HOW TO REPORT no longer sends every worker to `scripts/debug.py`, a file one host has: it asks
  for a breakpoint, a debugger session or a throwaway print, with the project's own debugging tool
  when the host's `project.prompt_extras` paragraph names one. The validator's evidence example
  spells the test runner as `__TEST_COMMAND__`, so it renders the host's `project.test_command`
  (the example config's `scripts/test.sh` renders word for word as before). `tests/golden/worker.md`
  changes by that one sentence. A test in `tests/test_prompt_templates.py` fails on any
  `scripts/<path>` in a template.
- agent-os#17 — the mechanism's own suite passes in a host that vendors it through `git subtree`
  whatever that host's layout: `test_agent_task.py` no longer asserts the host root holds exactly
  one top-level package and its own `.venv`. The worktree isolation test measures the first
  package the host's venv installs (of zero, one or several), and is skipped with its reason when
  the host has none, as a non-Python host does; only the mechanism's own repository still requires
  one. A host's `--deselect` workaround for the two tests can go after its next `subtree pull`.
- agent-os#8 — `docs/ADOPTION.md` names the live config keys: step 14 puts a worker's App at
  `project.backends.<name>.app` instead of the deprecated `project.worker_apps.*`, and step 18
  runs `worker_task.sh <backend> init` once per `project.backends` entry with a `worktree`
  instead of per `project.worktrees` entry. `docs/AGENT_OS.md`'s actors table and §4.3 say the
  same. A test in `tests/test_backends_config.py` walks every `project.`/`mechanism.`/`planner.`
  key ADOPTION.md mentions through the config schema and fails on one the loader does not have
  or warns about as deprecated.
- agent-os#9 — `agent-os-install` no longer prints "would create" for a file it actually
  creates. Only `--dry-run` speaks in the conditional ("would create", "would overwrite
  (--force)"); a real run reports "created" and "overwritten (--force)", printed after the write.
  "up to date -- skipped" and "refusing without --force" are true in both modes and unchanged.
- #513 (this task) — the mechanism's own docs move under `agent_os/docs/`: `AGENT_OS.md` (from
  `docs/AGENT_OS.md`), its ADRs (from `docs/adr/`, dated 2026-09-14 through 2026-09-18 and
  2026-09-21), `ADOPTION.md` (the export recipe of §5 as a numbered checklist for a second host)
  and this file.
- agent-os#13 — `docs/ADOPTION.md` step 7 spells out the `git remote add` + `git subtree add`
  commands and says when git needs a credential of its own. `titanarq/agent-os` is public now, so
  the add and every `subtree pull` need none. A `subtree push`, or any fetch from a private fork
  or mirror, needs one, and a `gh` login alone does not give it to git. The step gives
  `gh auth setup-git` as the fix, and an SSH remote as the alternative. Prose only: nothing in
  the mechanism runs this step, so there is no behaviour for a test to pin.
- agent-os#14 — `issues.py move` finds the issue's board item from the issue's own
  `projectItems` (one GraphQL query matching board number and owner) instead of listing the whole
  board with `gh project item-list`, which returned zero items for an org Project v2 that held them
  and so skipped every column mirror in silence.

Wave 3's other two tasks, #429 (which backend fallback rule to write down as an ADR) and #514
(optional), add their own entries here once their pull requests merge.

- agent-os#16 — `worker_task.sh start`'s base-branch gate accepts any lowercase `<word>` before
  `/<issue>-<slug>`, hyphens and digits included: `agent-os/37-gradle-skeleton` passes for #37,
  where `[a-z]+` refused it. The anchoring on the number is unchanged, so
  `task/387-close-the-390-gap` still fails for #390, and the refusal now names the accepted shape
  (`<word>/<issue>-<slug>`) instead of "a branch naming #N".
- agent-os#6 — `pyproject.toml` depends on `PyJWT[crypto]>=2.8` instead of a bare `PyJWT>=2.8`:
  without the extra, the interpreter `bootstrap.sh` builds has no `cryptography`, PyJWT registers
  no RS256 signer, and `gh_app_token` fails with `KeyError: 'RS256'` signing the App JWT. A host
  that installed `cryptography` by hand as a workaround can drop that step.

## 2026-09-22

- #512 (PR #525) — the mechanism's own suite (`agent_os/tests -q`) now runs from a copy made
  outside the repository, as a CI step, proving nothing under `sys.path` still resolves through
  roedor's editable install; roedor's own values, including the m2-fingerprint assertion the move
  had left unwatched, moved into `tests/test_agents_config_conformance.py` on the host side.
- #510 (PR #524) — `worker_progress.sh` and `gh_app_token.py` stop hardcoding roedor's backend
  names and `secrets_dir`; the two `.claude/agents/*.md` templates and the `status:*`/`type:*`/
  `p1..p4`/`module:` label vocabulary move to config; a walk test refuses a roedor literal inside
  `agent_os/` from landing again.
- #511 (PR #523) — `agent-os-install [--dry-run] [--force]` writes the systemd units and copies the
  first-run templates; `agent_os/bin/worker_task.sh <backend> init` creates a backend's worktree
  idempotently; `agent-os-doctor` reads the whole first-run checklist back in one pass: adopting
  the mechanism on a machine becomes three commands instead of a hand-run checklist.
- #509 (PR #522) — the four role prompts (worker, validator, refiner, planner) become template
  files under `agent_os/prompts/`, rendered by one function with a single marked extension point,
  `__PROJECT_EXTRAS__`, for a host's own text; a golden test proves all four render word for word
  what the inline strings they replaced used to.

## 2026-09-21

- #508 (PR #520, PR #521) — the mechanism becomes one directory, `agent_os/`: its own
  `pyproject.toml`, its own interpreter (`agent_os/bootstrap.sh` → `agent_os/.venv`), its own tests
  with their own `conftest.py`. roedor's old entry points under `scripts/` and the tracker CLI
  become one-line shims that `exec` into it. PR #521 lands the root `AGENTS.md` paragraph naming
  `agent_os/` separately, because that file sits inside `project.forbidden_paths` and the merge
  gate's condition 3 audits it.
- #476 (PR #516) — the merge gate's condition 3 (nothing outside a delivery directory touched)
  used to audit the whole `project.forbidden_paths` list; `project.merge_audit_exempt_paths` now
  subtracts the delivery directories from what gets audited, so a diff that only adds a file under
  one of them no longer trips the condition it was never meant to guard.
- #443, #435, #483 (PR #519) — three worker-driver bugs in one PR: a `start` that found nothing to
  launch no longer emits a `worker_finished` event; `branch` with no base fetches and forks from
  `origin/main` instead of a stale local one; the usage report reads the issue's own budget class
  instead of a fixed ceiling.
- #426, #436 (PR #518) — two planner-wake bugs: a backend rejecting a wake no longer consumes the
  `idle_dispatchable` rate-limit window it was going to use productively later; a `new_dispatchable`
  event found while every worker slot is occupied is retained instead of dropped.
- #428, #419 (PR #517) — the guard survives a worker's `cutoff=` line that fails to parse (prints
  it, keeps ticking) and judges liveness against the mtime it actually observed arriving, not the
  timestamp the worker typed into the line.
