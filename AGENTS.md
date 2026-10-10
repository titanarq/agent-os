# agent-os — agent instructions

## What this is
Agentos lets one person build and evolve software products far beyond their individual capacity
without losing control of what gets built. It is a system of agents that turns its owner's goals
into a working product, keeps that product faithful to those goals as it grows, and improves the
way it does so with every product. Its own goals and requirements are the tree in `docs/tree/`
(`python -m agent_os.product.tree validate --root docs/tree`); the construction plan is
`docs/AGENTOS_V2_PLAN.md`.

Underneath sits the execution substrate (v1): a guard, a planner, workers and one-shot role drivers
(validator, refiner) that run a host project's GitHub backlog through headless coding agents, plus
the tracker CLI they share. It is **project-agnostic and configured, not coded**: a host extends it through its
own `config/agents.yaml` and never by editing a file in here
(`docs/adr/2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md`,
`docs/adr/2026-09-21-the-mechanism-is-one-directory-extended-by-hosts-and-never-modified.md`).
The full picture — actors, identities, state layer, triggers — is `docs/AGENT_OS.md`.

Hosts consume this repository as a `git subtree --squash` under their own `agent_os/`. A defect is
fixed **here**, as a PR on this repository, and each host brings it in with
`git subtree pull --prefix=agent_os <remote> main --squash` on a branch of its own, merged with a
merge commit — never a squash, which drops the `git-subtree-dir:` metadata the next pull needs.

## Languages
Conversation with the user: Spanish. Code, identifiers, commits, repository documentation and code
comments: English. Code must be self-explanatory — long descriptive names, comments only for a
non-obvious "why".

## How a task starts
1. Read this file.
2. Read the issue (`gh issue view N`) and whatever it links: another issue, a host's issue, a PR.
3. Read only the sections of `docs/AGENT_OS.md` and the `docs/adr/*.md` the issue touches — then
   the code. Adoption issues land in `docs/ADOPTION.md`.
4. The issue is a report, not a spec. A DEFECT found in use is reproduced with a test that fails
   first, then fixed. Something new the owner has not used yet gets no new tests
   (`docs/tree/dec-tests-harden-they-do-not-build.md`, not even when the request is about agentos
   itself), and the existing suite keeps passing whole. If the report's premise does not hold
   against the code, say so on the issue instead of building to it.

## Layout
- `agent_os/` — the Python package: `guard`, `lib`, `issues`, `install`, `doctor`, `render`, `cli`…
  `agent_os/product/` holds the v2 subsystems (`tree/`, `puntal.py`, and what Stage 1 adds); the root
  stays for the v1 substrate (`docs/adr/2026-10-07-v2-subsystems-live-under-agent-os-product.md`).
- `bin/` — the shell drivers (`worker_task.sh`, `agent_task.sh`, `planner_task.sh`, …) a host's
  `scripts/` wrappers `exec` into.
- `prompts/` — role prompt templates, rendered with host tokens (`__TEST_COMMAND__`, …).
- `agents/` — agent definitions a host installs into its own `.claude/agents/`; they are product,
  not tools for developing this repository.
- `templates/` — what `agent-os-install` writes into a host (issue templates, systemd, CI).
- `config.example.yaml` — the documented shape of a host's `config/agents.yaml`.
- `tests/` — the suite: no database, no network, no real backend; `tests/product/` mirrors
  `agent_os/product/`.

## Commands
```bash
bash bootstrap.sh                                   # own interpreter in .venv (idempotent)
.venv/bin/ruff check . && .venv/bin/ruff format --check .
bash bin/dev/run_suite.sh "$PWD" <run-dir>          # the whole suite, as CI runs it; add `-k name` for one area
python3 -I bin/dev/suite_show.py <run-dir>/suite.xml <id-fragment>   # only that failing test, truncated
bash bin/dev/wait_checks.sh "$PWD" <PR> [max_minutes]                # CI of the PR's head; exit 0 = every check SUCCESS
bash bin/dev/safe_merge.sh "$PWD" <PR>              # merge commit only if all SUCCESS and the head holds origin/main
```
The whole suite takes over ten minutes: launch `run_suite.sh` in the background and read the one
line it prints or `<run-dir>/suite.summary.json`, never `suite.raw.log` or a tail of pytest's
output; the same goes for CI (`wait_checks.sh`, not `gh pr checks --watch`). `run_suite.sh` sets
`TERM=dumb`, which matters — without it Rich wraps CLI error text in ANSI spans and message
assertions diverge from CI.

## Rules
- **Code quality, in every pull request** (`docs/tree/dec-every-pull-request-gets-a-code-quality-review.md`):
  SOLID principles; self-explanatory code with long descriptive names and comments only for a
  non-obvious why; folders organized in depth (no folder with dozens of files) and small files. A
  new file stays under 300 lines and a folder under 12 entries, and a file you touch never gets
  worse; the large files that exist are split as they are touched.
- **No host literal anywhere outside `docs/`.** `tests/test_no_host_literals.py` reads every file
  git knows (`git ls-files --cached --others --exclude-standard`, except `docs/`, `tests/golden/`,
  `config.example.yaml`) and fails on a host project's name, org, owner login or database port.
  That includes untracked files that are not ignored: a stray file you leave in the tree is
  scanned; ignored paths (`.venv`, `.cache/`, `.claude/worktrees/`) and nested worktrees are not.
- A host-specific value (a path, a label, a runbook, a test command) is a config key with a
  documented default, never a literal in code, prompts or templates.
- **Tests must never launch a real backend.** A driver test without a fake `claude`/`qwen` first in
  `PATH` starts a real, billed run; every test that calls a driver stubs the backend binary.
- A golden fixture that changes is read diff by diff before it is committed: regenerating a golden
  certifies whatever the code prints, including a broken path.
- A path helper fails loudly when its premise (a `.git`, a config file, a package) is missing
  instead of falling back to `.` or a guess.
- Never kill by pattern (`pkill -f`, `pgrep -f | xargs kill`): stop a process by its PID.
- Never mutate the working tree while a pytest is running.

## Definition of done
A defect found in use has the test that reproduced it, failing first and passing now; something new
the owner has not used yet has no new tests. Ruff is clean and the existing suite passes (the
relevant tests while iterating, the whole suite if the change is wide). `docs/AGENT_OS.md` changes
only if the change alters a behaviour it already describes, in its section, without growing it if
that can be avoided; `docs/ADOPTION.md` changes when a config key or the adoption steps changed.
The changelog note goes in its own fragment, `docs/changelog/unreleased/<branch-name-with-hyphens>.md`,
never in `docs/CHANGELOG.md` (see that folder's README). An ADR is written in `docs/adr/` if a
decision was taken; the issue, when there is one, carries the result. Work lands as a PR on a
branch, never straight on `main`: `fix/<N>-<slug>` and `Closes #N` in the body when an issue
exists; rollout and docs branches that have no issue are named by topic.
