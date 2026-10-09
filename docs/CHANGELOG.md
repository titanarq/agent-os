# Changelog

One entry per merged task of the parent epic (titanarq/roedor#507 — the mechanism separates from
its host, extended by config, never modified per project), in the order the work landed, newest
first. Every entry names the task issue and the pull request that closed it; entries for a task
that closed several small issues at once name them all. This file starts on 2026-09-21, the day
#508 moved the mechanism into `agent_os/` — nothing from before that date describes this directory.

## Unreleased

- Rollout stage 1l (no issue; branch `fix/rollout-stage1l`) -- worker slots on demand. The owner, seeing a host
  capped at five slots: "¿por qué has limitado a 5 slots?"; the web of puntales "necesitará muchos agentes ...
  no se deben limitar" (`docs/tree/fr-independent-work-runs-in-parallel.md`); quota is the only limit.
  A fixed number of slots was itself the error: when `worker_task.sh <backend> branch|start` finds every slot
  alive it now MAKES the next one (worktree `<worktree>-N`, `.cache/worker_<backend>-N.*`, the host's
  `worktree_links`, setup command and mechanism venv, through the same function `init` uses) and goes on in it,
  instead of refusing with "every slot is busy" (a one-slot backend: "a run is alive"); a free slot is always
  reused first, and nothing is deleted. `project.backends.<name>.slots` is optional and now means how many `init`
  precreates (a floor); `planner.max_parallel_issues` is optional and absent or `null` means no cap (it
  defaulted to 1), a host that sets it keeps it. What still stops a new slot, writing nothing: that cap, and the
  backend's `exhausted` quota verdict (workers park, puntales never do); `python -m agent_os.product.dispatch
  new-slot <backend>` answers for the driver. Slots are found on disk (`<worktree>-N` holding a worktree), through
  one derivation (`agent_os.product.dispatch.slots`, re-exported by `agent_os.lib`) that the driver, the guard, the
  doctor, `planner_task.sh` and `worker_progress.sh` share; `dispatch headroom` no longer has a per-backend slot
  ceiling. `start` of an issue an alive slot already runs is refused. `bin/worker/worker_slot_selection.sh` takes
  the slot-picking out of `worker_task.sh` (which shrinks); `prompts/planner.md` stays at 300 lines. ADR
  `2026-10-09-worker-slots-are-created-on-demand.md` amends `2026-09-26-...slots-of-its-own.md` and
  `2026-09-15-...cap-enforced-by-the-driver.md`. Host follow-up: none -- after `git subtree pull` a host with
  `slots: 5` and `max_parallel_issues: 5` keeps both, and gets the sixth slot only if it deletes the cap.
- Onboarding rung 6 (no issue; branch `docs/onboarding-rung6`) -- `docs/adoption/v2-build-the-product.md` rung 6 now describes the test session the first v2 host really ran on 2026-10-09 (the header button and side panel of `dec-a-test-session-happens-inside-the-app`, the order given by `depends_on`, the owner's web kept apart from the workers', `agent-os-sessions test-ingest`) with its first-time findings and cost; the interpreter chat and the schema 2 reader are named as not built.
- Test-session design in the tree (no issue; branch `docs/test-session-design`) -- on the owner's word of 2026-10-09
  after the first test, `uc-open-a-test-session-for-a-branch` (id kept, title now "Open a test session from the app")
  and `dec-a-test-session-happens-inside-the-app` say the session opens from a "Test session" header button
  into a side panel that keeps its state when collapsed, holding one comments box with a state dropdown always at the top, the use cases prioritized by
  what the others depend on (filtered by default to the screen the owner is on), the comments box a chat with the
  agent that interprets the feedback, and a comment split into changes launched directly except decisions of
  what, shown to the owner at the start of the next session. Tree only; the session file contract is documented on
  `fix/test-session-ingest`.
- Test-session ingestion (no issue; branch `fix/test-session-ingest`) -- the half of `uc-open-a-test-session-for-a-branch`
  that Agentos owns. `agent-os-sessions test-ingest` reads the closed test sessions the app writes
  (`tree.test_sessions_dir`, contract in `docs/AGENT_OS.md` §4.11), prints the plan by default and with `--apply`
  writes each answer into its node, opens one rework issue per rejected case (keyed, so a second run opens none) and
  records the owner's acceptance on the node (new optional `acceptances` field); the verdicts of `feedback.jsonl`
  inside the session are summarised in the plan; the reader is versioned by the file's `schema` (1 today). ADR 2026-10-09.

- Rollout stage 1i (no issue; branch `fix/rollout-stage1i`) -- five defects observed on the vector host on
  2026-10-09, each with a test that failed first. (1) `worker_task.sh <backend> resume --issue N --rework`: a
  run whose every stage is committed and whose pull request the validator sent back with CHANGES_REQUESTED
  had "nothing to launch", and three times that day the fix was an extra stage added by hand to the issue's
  `## Stages` plus `resume --after manual --context`; the driver now appends the stage (`Address the changes
  requested on PR #<n>`) from the newest settling review of the branch's open pull request and launches it
  with the review as context (`bin/worker/worker_rework.sh`, `agent_os/product/tracker/rework.py`; `prompts/planner.md` still names
  the manual route and is left to the branch that edits it). (2) A worker relaunched into an exhausted quota
  window died before its first event and was recorded as `CUT_BY_GUARD reason=no_stage_commit` -- the planner
  may escalate the model after that, and may not after `reason=quota`; `stage-exit` now reads the stream's
  verdict and, for a run with no parseable event, the refusal text on stdout or stderr
  (`agent_os.lib quota-status --log --backend`). (3) The `.venv` link `init` makes in a new worktree showed as
  `?? .venv` under a `.venv/` gitignore (a symlink is a file to git) and refused `branch` and `start`; the
  exemption `.env` had since #404 now covers every `project.worktree_links` entry that is a symlink, in the
  dirty check and in the freeze. (4) `collect`, `open-pr`, `stop` and `watch` take `--issue N` to find their
  slot on a backend with `slots: 2+`, as `resume` already did. (5) Reported by the host while this branch was
  open: a stage whose commit is a merge (#39's rework was `git merge origin/main` with its conflicts resolved,
  subject `stage 2/2: ...`) was not counted -- `resolve_stage_context` and `has_wip_after_last_stage_commit`
  read the branch with `--first-parent --no-merges` -- so the driver counted 1/2 and cut the run as
  `no_stage_commit`; both now use `--first-parent` alone, which is what keeps the base's stage commits
  (a merge's second parent) out of the count.
- Rollout stage 1j (no issue; branch `fix/rollout-stage1j`) -- three edges of the first v2 host. A: `open-pr`
  runs the code-quality ratchet on the worktree before the pull request exists and refuses a branch that fails
  it (`BLOCKED reason=quality_ratchet_failed`, issue to `blocked-on-human`; a ratchet that could not run does not
  refuse), like the malformed-trailer ending; `prompts/worker.md` tells the worker to run it before closing a stage;
  `prompts/planner.md` names the ending; and `agent-os-quality` now judges the git checkout of the working directory
  (or `--root`) instead of `AGENT_OS_HOST_ROOT`, which in a worker's worktree measured `main` and gave a false green.
  B: `open-pr` lists in the pull request body the files outside the ticket's `touches` marker and the validator
  judges each (ADR 2026-10-09: listed, not refused). C: the tree doctor reports `implementation-path-missing` for
  an implemented or hardened node whose root-relative `implementation` path does not exist (`validate`, with the
  repository found from the tree root; `compile` and `slice` leave it out); on the host's five checkouts it names
  exactly the two nodes that pointed at the deleted `entry.html`. Goldens changed by exactly the sentences added
  to the worker, validator and planner prompts (read diff by diff). D and E were not done.
- Rollout stage 1h (no issue; branch `fix/rollout-stage1h`) -- the planner asks every run whether more work can
  run at once. New read-only `python -m agent_os.product.dispatch headroom [--json]` (what starts now, what waits
  and why, what waits only for the cap; the rules are `tree_dispatch_refusals`, not a copy); the planner prompt
  (`THE DISPATCH RULE`, golden `planner.md` read diff by diff) starts every issue that could start and comments
  what waits only for the cap, never pages for it (that section and the v2 one were tightened, same rules, so the
  prompt stays at the 300-line ratchet); `fr-independent-work-runs-in-parallel` records the rule, that
  quota is the only limit and that puntales and workers never limit each other (owner, 2026-10-09). The
  ticket-writing modules of `agent_os/product/dispatch/` moved to its `tickets/` subpackage (and their tests) to
  keep both folders under twelve entries.
- Onboarding v2 (no issue; branch `fix/onboarding-v2`) -- `docs/ADOPTION.md` is now the index of the
  ladder that starts a product with Agentos v2, written from the first host's real start (installing,
  the owner's goals and evaluators, the expert, `compile` in waves, foundations with a worker and a
  validator by hand, parallel slots, the test session), with per-rung baselines (time, USD, rounds), what
  failed the first time and which edges are still open. The 26-step v1 checklist moved unchanged to
  `docs/adoption/substrate.md`; the messages, comments, ADR and tests that named `docs/ADOPTION.md` step N
  now name that file, and the live-config-key test reads every adoption document.
- Rollout stage 1g, 2 (no issue; branch `fix/rollout-stage1g`) -- parallelising is a requirement of
  Agentos's own tree: `docs/tree/fr-independent-work-runs-in-parallel.md`, under
  `goal-product-early-grown-by-use` (the owner's choice: a requirement under that goal, not a fifth goal).
  The owner's word of 2026-10-09: "Para agentos paralelizar debería ser un objetivo", with four evaluators
  approved as trends ("ya iremos mejorando con el uso"): work items running at once when there is
  independent work grows; a wave's wall-clock time approaches that of its longest ticket; merge conflicts
  between parallel work are few; no dispatchable work waits for another run without a reason. Its
  mechanism is what the substrate already has (slots per backend, `planner.max_parallel_issues`, the start
  gate that refuses overlapping `touches`), its decision `dec-dispatch-never-runs-two-tickets-on-the-same-code`,
  its state `implemented` (so `compile` makes no ticket of it); nothing measures the evaluators yet. The
  plan counts twenty requirements now. A test holds the node, its parent and its four evaluators.
- Rollout stage 1g, 1 (no issue; branch `fix/rollout-stage1g`) -- a use case under a foundation requirement is
  no longer a foundation by inheritance. `compile` ordered with the foundations every node that had a
  `foundation: true` ancestor (`is_foundation_work`); it now counts only the flag the node carries itself,
  which the expert (`prompts/expert.md`) sets node by node when it judges the use case indispensable. The
  owner's word of 2026-10-09: "no tiene por qué, esto tiene que decidirlo algún agente, porque a lo mejor no
  todos los casos son imprescindibles". Recorded in the mechanism of `fr-a-usable-product-exists-early`
  (with the owner's words as a source), `docs/AGENT_OS.md` (field table and compile ordering) and the expert
  prompt; golden `expert.md` changed by exactly the sentence added to the prompt (read diff by diff). The
  test that asserted the inheritance now asserts its absence, and a second one asserts that a flagged use
  case is still ordered first.
- Rollout stage 1f, 6 (no issue; branch `fix/rollout-stage1f`) -- `docs/ADOPTION.md` step 16 says that the
  drivers link the mechanism's `agent_os/.venv` into every worktree (`agent_os_link_mechanism_venv`),
  where and when, and that nothing is linked by hand. A test ties the step to the function it names.
- Rollout stage 1f, 5 (no issue; branch `fix/rollout-stage1f`) -- the planner prompt says what to do with
  `open-pr`'s own endings. `BLOCKED reason=<reason>` (`malformed_node_change_trailer`, `push_rejected`,
  `workflows_permission`, `merge_failed`) reaches the planner as a `worker_cut` event, and nothing in its
  prompt described it, so it read as a cut stage to relaunch. The paragraph on a worker that asked a
  question (`status:blocked-on-human` set by the planner) now also covers it: the work is committed and no
  pull request exists; never `resume` the issue nor re-run `open-pr` blindly; make sure the issue is
  `status:blocked-on-human` and mention the human with the reason. A new test reads the reasons from
  `bin/worker_task.sh` and `bin/worker_publication_refusals.sh` and fails when the prompt does not name
  one. `prompts/planner.md` stays at 300 lines, its ratchet limit (it was 298): the addition went into an
  existing paragraph and one bullet was re-wrapped without losing a word. Golden `planner.md` changed by
  exactly those lines (read diff by diff: the heading, the new sentences, the re-wrapped bullet).
- Rollout stage 1f, 4 (no issue; branch `fix/rollout-stage1f`) -- the freeze commit carries the `Node-Change`
  trailer, so `open-pr` is no longer blocked by its own pre-merge freeze. `WIP: cut by guard (before_merge)`
  committed a run's leftover tree edits with no trailer, and since 1d, A `open-pr` refused the branch for a
  commit no agent wrote (the host CI would have failed it too). `freeze_uncommitted_work` now commits
  through `agent_os.product.tracker.freeze_commit`: when the staged work touches `tree.root` the commit
  ends with `Node-Change: <reason of the branch>` -- the nearest `usage` or `rework` among the branch's
  own commits, `usage` if none, never `owner` -- and a freeze that touches nothing in the tree has no
  trailer. The alternative of exempting freeze commits from the check was rejected: it would leave the
  nodes they changed without a recorded reason. `worker_task.sh` shrank by 2 lines.
- Rollout stage 1f, 3 (no issue; branch `fix/rollout-stage1f`) -- the agent definitions no longer send a
  host to wrapper scripts it may not have. `agents/{control-plane,task-writer,worker-runner}.md` told the
  subagent to run `scripts/worker_task.sh`, `scripts/issues.py`, `scripts/notify.sh`,
  `scripts/worker_progress.sh` and `scripts/agent_lib.py`: shims the first host wrote and a host that
  vendors the mechanism and writes none (the second one) does not have. They now name
  `__MECHANISM_DIR__/bin/<driver>.sh` and `__MECHANISM_DIR__/.venv/bin/python -m agent_os.<module>`, with
  the new render token `__MECHANISM_DIR__` (`agent_os`, the `git subtree` prefix). A host that keeps its
  shims loses nothing: they still `exec` into those files. Re-run `agent-os-install --force` to refresh
  the rendered definitions. `install.resolve_exec_start` needed no change: it already uses
  `python -m agent_os.guard tick` when `scripts/agent_guard.py` is absent.
- Rollout stage 1f, 2 (no issue; branch `fix/rollout-stage1f`) -- `worker_task.sh <backend> init`
  recreates a lost worktree. With the directory gone but `agent-os/init-<backend>` still there it died
  on git's "a branch named ... already exists". `init` now forgets the registrations of vanished
  worktrees (`git worktree prune`), reuses the branch -- moved to the tip of `origin/main` -- when it
  holds no commit `origin/main` lacks, and otherwise stops, leaves the branch alone and prints the
  `git` commands that keep or drop it (the same for a branch checked out in another worktree). The
  logic is `bin/worker_init_worktree.sh`; `worker_task.sh` shrank by 17 lines.
- Rollout stage 1f, 1 (no issue; branch `fix/rollout-stage1f`) -- a GitHub App that cannot read CI
  checks is found before the first pull request and said in one line. At the first host the validator
  failed `issues.py move N review` with GraphQL's "Resource not accessible by integration": its App
  had no Checks (read) nor Commit statuses (read). `agent-os-doctor` has a new check, "GitHub Apps
  read CI checks", that mints the installation token of the planner's and the validator's Apps and
  asks for the check runs and the commit statuses of the default branch's head
  (`agent_os/product/tracker/app_check_access.py`), failing with the App, the permissions it lacks and
  the remedy (grant them, then accept them on the installation); `move N review` now exits with that
  same sentence instead of the GraphQL error; `docs/ADOPTION.md` step 14 lists the permissions each
  App needs. `linked_boards` moved out of `doctor.py` to `agent_os/product/tracker/linked_boards.py`
  and the `prompt_extras` doctor tests to `tests/product/doctor/`, so neither file grew.
- Rollout stage 1e, F (no issue; branch `fix/rollout-stage1e`) -- a node can declare the code it
  touches. Dispatch compared the paths it guessed from the prose of `implementation` and `mechanism`,
  and the guess takes any word with a slash or an extension for a file (`http.client`, `p.ej`,
  `docs/VECTOR.md` in passing), so a ticket could be held back, or let collide, by something that is
  not the node's code. The tree format gains an optional `touches:` list. When present it decides:
  the ticket's `touches` marker is exactly that and the prose is not read; `touches: []` says "no known
  code". When absent the derivation is unchanged. An entry is one word (no whitespace, comma or `-->`,
  which the marker could not carry) naming something under the root, not the root; a bad one is a
  `schema` defect. `docs/AGENT_OS.md` §4.6 (the field table and the Tickets paragraph).
- Rollout stage 1e, E (no issue; branch `fix/rollout-stage1e`) -- the puntal's interface says who
  acts. The executor, the pre-helper's reads and the slow path's `./state` did not know who clicked,
  and the only way to tell them was to export an environment variable the mechanism never defined
  (what the shell exported reached them by inheritance, undocumented). The contract is
  now one variable, `PUNTAL_ACTOR`: the `--json` request accepts `actor` (text; anything else is a
  `not_run` refusal) and sets it for all three; without one, what the caller exported is passed on
  unchanged; without that, it is not set. The slow path's shim exports it itself. The brief and the
  telemetry do not carry it. `docs/AGENT_OS.md` §4.7 documents the variables the driver reads and
  sets (`agent_os/product/puntal/fast/actor.py`).
- Rollout stage 1e, D (no issue; branch `fix/rollout-stage1e`) -- the fast path's contract carries the
  app's data API. `puntal.persistence_api_file` was rendered into the slow path's contract only
  (`prompts/puntal_slow.md`), while the fast turn -- no tool, no `--help` -- is the one that plans the
  operations over the app's data. `prompts/puntal.md` now has a `__PERSISTENCE_API__` placeholder
  (answered with `__STATE_COMMAND__` too, like the slow one) filled with the same text under the heading
  `THE APP'S DATA API`, introduced as reference only because the turn runs none of its commands; a host
  that configures no file gets exactly the contract it had. `docs/AGENT_OS.md` §4.2 and §4.7;
  `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`.
- Rollout stage 1e, C (no issue; branch `fix/rollout-stage1e`) -- the foundation rule is said the
  way the decision says it. The comment of `Node.foundation`, `docs/AGENT_OS.md` §4.6 (the field and
  the `foundation-improvised` row) and the check's own text said a foundation is HARDENED before the
  shell goes live; `dec-tests-harden-they-do-not-build` ("foundations follow the same rule") and
  `fr-a-usable-product-exists-early` say implemented and accepted -- the essential top-down acceptance,
  then the owner's in the first test session -- with the tests later. All now say that. The check
  itself is unchanged and is documented as what it is: it reads the node's own `foundation` flag and
  does not inherit it, so a use case under a foundation requirement that is not itself flagged may be
  improvised (`compile` only orders it with the foundations). Also the plan's Phase 1 node model lists
  the state `implemented`.
- Rollout stage 1e, B (no issue; branch `fix/rollout-stage1e`) -- a ticket depends only on nodes
  that have a ticket. `compile` left in `depends-on` every node the ticket depended on, including
  those that never get a ticket (`improvised`, `implemented`, `hardened`, escalated), and dispatch
  waits only for an open ticket: a ticket could start before the foundations under such a node. A
  dependency without a ticket is now replaced, in its place, by that node's own dependencies (its
  requirements' included), through as many such nodes as there are, each ticket named once. The
  dependency helpers moved out of `compile.py` into `agent_os/product/dispatch/ticket_dependencies.py`.
  `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`; `docs/AGENT_OS.md` §4.6.
- Rollout stage 1e, A (no issue; branch `fix/rollout-stage1e`) -- a compiled ticket builds and no
  longer asks for tests. `compile` wrote "verified by ... the project's tests" and "Tests and
  documentation as the project's AGENTS.md asks" into every ticket, which `dec-tests-harden-they-do-not-build`
  rules out for an implementation or a foundation (it passes the essential top-down acceptance and then
  the owner's use; its tests come when it hardens). The implementation stage is now verified by the
  acceptance criteria and then by the owner's use, and the definition of done carries one line: no test
  is written for the node, the tests the project already has keep passing, documentation as the
  project's `AGENTS.md` asks (the blocked-hardening line no longer says "do not write hardening tests"
  next to an order to write tests). A node with no `verification` is no longer accepted by one generic
  sentence: its criteria are derived from its description (the validator's rule for such a node) and
  from the acceptance each ancestor carries, one `judged by an agent: with <node> built, <ancestor>
  still holds: <criterion>` line each, the goal's evaluators included. It is not refused: dispatch does
  not wait for a verification (`dec-tests-harden-they-do-not-build`,
  `fr-a-usable-product-exists-early`). `docs/AGENT_OS.md` §4.6.
- Rollout stage 1d, C (no issue; branch `fix/rollout-stage1d`) -- tests only. `wake` and `check`
  read the tracking epic's `status:agents-paused` label with a real `gh issue view`, and the tests of
  those paths ran it for real from a temp directory. `tests/conftest.py` now has an autouse fixture
  that answers 'not paused' for `agent_os.guard._agents_paused` by default; the tests of the pause
  keep setting their own answer (it wins), and the two tests of `_agents_paused` itself carry the
  new `real_agents_paused` marker (registered in `pyproject.toml`) and get the real function.
- Rollout stage 1d, B (no issue; branch `fix/rollout-stage1d`) -- a worker no longer records `Node-Change:
  owner`. The worker touched its own node at the end of a ticket and wrote `owner`, which is only the
  owner's own word. `prompts/worker.md` now gives the worker `usage` (what it writes while building
  its node) and `rework` (when it corrects a rejection) and says it never writes `owner`;
  `prompts/validator.md` makes a worker's commit with `owner` a request for changes and has the
  validator run the new deterministic check, `agent-os-tree trailers --agent-authored` (an agent
  wrote the range, so `owner` is `owner-word-by-agent`), which `open-pr` also runs over every
  worker branch before it opens the pull request (the 1d, A gate). Goldens `worker.md` and
  `validator.md` changed by exactly those paragraphs.
- Rollout stage 1d, A (no issue; branch `fix/rollout-stage1d`) -- a worker's branch with a malformed
  `Node-Change` trailer no longer becomes a pull request announced as ready. A worker had written
  `Node-Change: owner`, a blank line and `Co-Authored-By:`: git reads only the last paragraph as
  trailers, so the host's CI and `agent-os-tree trailers` found it absent. `open-pr` now runs the
  same check over the branch (`agent_os.product.tracker.branch_trailers`, after the pre-merge freeze,
  before the merge and the push); on a defect it opens no pull request, pushes nothing, rewrites no
  commit, ends `BLOCKED reason=malformed_node_change_trailer`, comments the output on the issue and
  moves it to `status:blocked-on-human`. The command now reports a `Node-Change:` line outside the
  last paragraph as `misplaced-node-change` instead of `missing-node-change`. The diary refusal moved
  with it into `bin/worker_publication_refusals.sh`, so `worker_task.sh` shrank.
- Rollout stage 1c, C (branch `fix/rollout-stage1c`) -- `worker_task.sh <backend> status` no longer
  says "no events yet" right after a stage ended: `stage-exit` archives the stage's events under
  `.cache/spend/<issue>/` and empties the live log, and `status` (token/cost report and last
  assistant text) now falls back to this backend's newest archived stage of the recorded issue,
  saying which file it shows.
- Rollout stage 1c, B (branch `fix/rollout-stage1c`) -- a pull request with a red or unfinished CI
  check can no longer be announced as ready. The validator approved a PR whose `tests` check was in
  FAILURE and the planner then said "the human merges". `issues.py move N review` (what the
  validator runs after approving) now reads the checks of the open PR whose body says `Closes #N`
  (`agent_os/product/tracker/pull_request_checks.py`) and refuses, naming the check, while any is failing or
  still running; the validator prompt now tells it to read `gh pr checks` first and request changes
  citing the failed check. An issue with no open PR is not gated.
- Rollout stage 1c, A (no issue; branch `fix/rollout-stage1c`) -- `wake` now honours
  `status:agents-paused` like `tick` does, through the same `_agents_paused` check. A worker started
  by hand ends through `check` -> `wake`, and with the epic paused it used to wake the planner, which
  launched the validator. Under the pause the events are still written and stay on disk; the first
  wake after the label is removed reads them.
- Rollout stage 1b (no issue; branch `fix/rollout-stage1b`) -- `context` and the ticket's Context now
  carry the findings of each ancestor's experiments (`kind: question -- finding`; `experiments` in
  `--json`), so the owner's answers and the decided stack reach the tickets. Also `compile`: a use case inherits the
  `depends_on` of its requirements (and a dependency on a container waits for the work under it) and
  is ordered as a foundation when a requirement above it is one; before, the use cases of a host tree
  went out together with the foundations in id order. The ticket's `depends-on` marker carries the
  effective dependencies. Dependencies that loop only once inherited are refused by `compile`.
- Agentos v2, how pass, goal B (owner design discussion of 2026-10-06; no issue, branch
  `feat/v2-how-goal-b`) -- a verification is a command or a judged criterion, and a goal without
  evaluators is a red check. A `verification` entry of a node is now exactly one of `command` (with
  its optional `expects`) or `judge`, a one-paragraph criterion in plain language that an agent
  judges against what was built; both in one entry, neither, or `expects` with a `judge` is a
  `schema` error. `hardened-needs-verification` now asks for at least one `command` (tests harden; a
  judged criterion alone is acceptance). New red check `goal-without-evaluators`: a goal whose
  `verification` is empty fails the doctor, one line with the file path (24 codes now). `context`
  (Markdown and `--json`) and a `compile` ticket's acceptance criteria render a judged criterion
  labelled "judged by an agent", for the node and for every ancestor, on one line so it cannot open
  a section of the ticket; in `--json` every `verification` entry carries a `kind` (`command` or
  `judge`) and a judged one a `label`. `compile`'s dispatch rule is unchanged: a leaf with only
  judged criteria still escalates as `missing-verification` (Stage 1 changes that). Agentos's four
  goals carry their evaluators as `judge` entries in `verification` instead of a list in the body
  (`docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`,
  `docs/tree/dec-a-goal-without-evaluators-is-a-red-check.md`,
  `docs/tree/dec-tests-harden-they-do-not-build.md`; ADR
  `2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`,
  dated paragraph; `docs/AGENT_OS.md` §4.6). Host follow-up after a `subtree pull`: a host tree
  with a goal that has no `verification` goes red -- give each goal at least one evaluator, a
  `judge` is enough; a reader of `context --json` finds the entries of `verification` with a
  `kind` now.
- #132, #135 -- rollout fixes for the first v2 host (batch 1). An expert launch that gets no
  worktree (origin's default branch cannot be fetched) now exits non-zero and launches nothing,
  instead of starting in the main checkout: the expert writes a branch, unlike the validator, which
  still degrades to reading the diff. The expert prompt no longer says what goes into the tree
  "stays in English": it follows the language rule of the host's own AGENTS.md. `docs/ADOPTION.md`:
  the App an expert signs as needs Contents read/write (`project.role_apps.expert` can point at one
  that has it); "Pull request reviews" is part of "Pull requests: write" for a GitHub App; a
  private host needs a git credential helper before the first fetch (`init`); the guard-timer
  doctor check is red until step 22.
  The expert, worker and refiner prompts now teach that `Node-Change:` and any `Co-Authored-By:`
  sit in ONE trailer block (no blank line between them): git reads only the last paragraph as
  trailers, so a blank line hid `Node-Change` from `agent-os-tree trailers` on the first host.
- #133 -- the first v2 host's adoption PR was red in both workflows. `agent-os-quality` now always
  skips the config file it loaded when that file is inside the repository (a host's
  `config/agents.yaml`, generated from the 466-line example), next to `tree.root` and the vendored
  mechanism directory, so a host replacing `quality.excluded_paths` cannot lose it. The puntal bench
  test resolved the generated `persistence_api_file` against the mechanism's directory although the
  config (and `options.py`) resolve it against the host root; under `agent_os/` in a host the two
  differ, so the test now resolves against the host root and runs for both layouts (the code was
  right, the test assumed the mechanism is the repository root).

- Stage 1 loose ends (#130): agent-os's own CI now runs `agent-os-tree trailers --base
  origin/<base> --root docs/tree` on pull requests, so a commit touching `docs/tree/` without a
  `Node-Change` trailer fails there as it does in a host. The standing instruction for a reply to a
  question session moved from the session issue's body into `prompts/planner.md` (its own block);
  the issue body keeps a pointer to it. Host follow-up: none beyond the `subtree pull`.
- #118 -- Agentos v2, Stage 1: the expert role. A one-shot role in the validator/refiner pattern:
  class `expert` in `config.example.yaml` (`role: expert`, Sonnet, no fallback), prompt
  `prompts/expert.md` (rendered with `__TREE_ROOT__`, the new placeholder for `tree.root`; `expert`
  is in `PROMPT_ROLES`, golden `tests/golden/expert.md`), and `agent_task.sh expert <issue>`. Unlike
  the refiner it writes: the driver makes a throwaway worktree off the default branch of origin,
  starts the backend inside it, and the expert opens one pull request on the host's tree --
  requirements and use cases as small nodes under the owner's goals (never a goal, an evaluator or a
  decision), experiments, questions with `scope` and `default_answer`, challenges -- with a
  `Node-Change` trailer (`usage` by default, `rework` for revising its own earlier node, never
  `owner`). It receives every question before the owner: a `how` it settles itself or by an open
  spike, a `what` goes to the owner with its default; one summary comment (`<!-- expert-summary -->`)
  carries what is for the owner and a digest of what it decided without them. The guard accepts
  `expert_finished` and watches expert runs for death (`ONE_SHOT_ROLES`); the planner's prompt says
  it never launches the expert. Launched by command only; nothing runs it unattended (ADR
  `2026-10-07-the-expert-populates-the-tree-and-settles-a-how-before-the-owner-hears-it.md`,
  `docs/AGENT_OS.md` §4.9). Host follow-up after a `subtree pull`: add the `expert` class to
  `config/agents.yaml` before launching it.
- Agentos v2, Stage 1, compile and dispatch (#117, branch `fix/117-compile-and-dispatch`) -- a
  ticket dispatches without a verification, carries its address and its place in the order, and a v2
  host never runs two tickets on the same code
  (`docs/tree/dec-tests-harden-they-do-not-build.md`,
  `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`,
  `docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`; ADR
  `2026-10-07-a-v2-host-dispatches-by-node-address-dependencies-first-and-never-on-the-same-code.md`).
  `compile` no longer escalates `missing-verification` (the code is gone; `mechanism-unresolvable`
  is the only escalation): a leaf with a command, with only a judged criterion or with nothing is a
  ticket, and one with nothing is accepted by an agent's judgment against its description and its
  ancestors' acceptance. A ticket's definition of done leaves the node `state: implemented` and never
  asks for `hardened`; when `hardening_blockers` finds an open `what` question or a challenge on the
  node or upstream, the ticket says why the node cannot be hardened yet. Every ticket ends with the
  markers `<!-- node: <id> -->`, `<!-- depends-on: <ids> -->` and `<!-- touches: <paths> -->` (the last
  two only when there is something to say; the touched code is the paths named in `implementation`
  and a written `mechanism`), its `## Dependencies` names the nodes it waits for, and tickets come
  ordered by dependencies in the text, the JSON (`depends_on`, `touched_paths`) and the files. New
  config key `tree.dispatch_by_node` (default `false`) makes a host a v2 host: the guard's
  `dispatchable_scan` then leaves out a ready issue with no node address or with an open
  `depends-on` ticket, `worker_task.sh start` calls `python -m agent_os.product.dispatch start-gate`
  and refuses one that has no address, an open dependency or `touches` paths overlapping a running
  ticket's, and `agent_os.issues brief` appends the slice of the node (`agent-os-tree context`) to
  a worker's brief. Nothing changes in a host that leaves the key off. The worker, refiner,
  validator and planner prompts gain a block each (write-back discipline and the slice; keeping a
  ticket's markers; validating against the node's verification in a separate context and judging
  every pull request of the branch against its goals and use cases; the planner never works around
  a refusal), and goldens `worker.md`, `refiner.md`, `validator.md` and `planner.md` changed by
  those additions only (read diff by diff). Code: `agent_os/product/tree/compile.py` (376 lines) is
  split into `compile.py` and the new `agent_os/product/dispatch/` (body, markers, touched code,
  rules, start gate, output). Docs: `docs/AGENT_OS.md` §4.6, `docs/ADOPTION.md` step 24. Host
  follow-up after a `subtree pull`: nothing, until the host sets `tree.dispatch_by_node: true`; a
  caller that matched `missing-verification` finds none now.
- #120 -- Agentos v2, Stage 1: the progress board generated from the tree. New `agent-os-tree board
  sync [--dry-run] [--json]` writes one draft item per functional requirement into a GitHub Project
  (v2) through `gh`: its parts (use cases) by state, the open `what` questions with their default
  answer, the challenges and `depends_on`, plus a `Progress` text field; idempotent (an unchanged
  tree makes no write), an item whose requirement left the tree is reported as an orphan and kept.
  `board order [--out FILE]` reads back the owner's order of the backlog from the Project's `Order`
  number field, for the planner (#117 consumes it). New `board:` config section (`owner`, `number`,
  `title`, `progress_field`, `order_field`, all with defaults). The finishing reliability per branch
  is left to Stage 2. A host that wants it needs `gh auth refresh -s project` and nothing else
  (`docs/AGENT_OS.md` §4.6, `docs/ADOPTION.md` step 24; `uc-watch-progress-and-order-the-backlog`).
- Agentos v2, Stage 1, config and recording (#116, branch `fix/116-config-and-trailer`) -- one
  backend, Sonnet defaults, and the `Node-Change` trailer
  (`docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`,
  `docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`). `config.example.yaml`
  and the install templates describe ONE backend, Claude Code: the worker classes are now
  `mechanical-sonnet` and `complex-sonnet`, the refiner class is on Sonnet like every other role,
  `project.agent_models.task_writer` defaults to `sonnet`, and `project.agent_models` gains
  `custodian` and `consolidator`, default `opus` -- the keys and their defaults only; the two roles
  arrive in Stage 2 and nothing reads them yet. The multi-backend machinery (`fallback:`,
  `escalate:`, `slots:`, the Qwen stream parser) is untouched, and its tests run against
  `tests/fixtures/multi_backend_config.yaml`, the shape the example had before. New command
  `agent-os-tree trailers --base REF [--head REF] [--root DIR] [--json]`
  (`agent_os/product/tree/trailers.py`): every non-merge commit of the range that touches the tree
  root must carry exactly one `Node-Change: usage | rework | owner` trailer, one line per offender
  (`missing-node-change`, `multiple-node-change`, `unknown-node-change`), exit 1; an unresolvable
  range is an error, never a pass. `templates/ci-host.yml` runs it on every pull request, and the
  worker and refiner prompts say when each value applies (goldens `worker.md`, `refiner.md` and
  `planner.md` changed: the trailer paragraph and the class names, read diff by diff). Host
  follow-up after a `subtree pull`: nothing is forced -- an existing `config/agents.yaml` keeps the
  models and backends it names; re-run `agent-os-install --force` to take the new CI step, and give
  commits that touch the tree their trailer from then on (`docs/AGENT_OS.md` §4.6,
  `docs/ADOPTION.md` step 20).
- #119 -- Agentos v2, Stage 1: question sessions and the guard on the what (`agent-os-sessions`,
  `agent_os/product/sessions/`). A judgments log (`.cache/judgments/judgments.jsonl` and
  `outcomes.jsonl`, stamped with the versions helper); `open` creates ONE `status:blocked-on-human`
  issue freezing the open `what` questions (numbered, grouped by branch, ordered by what they block,
  each with its default), the challenges and a digest of judgments since the last session; the
  owner's reply (`1: yes; 3: no, rather X`, `reclaim N`) is parsed against the frozen batch and
  `apply` writes each answer into its node and each reclaim into a new question, recording a
  `reclaimed` outcome. New `guard-what PR` (exit 1 when a pull request touches a goal node or a
  `tree.owner_only_paths` file) is condition 6 of the control plane's merge gate, so the gate is now
  six conditions; `verify-answer PR --session N` is what the validator runs on a pull request that
  says `Session-Answer: #N`. New optional config key `tree.owner_only_paths` (default empty). ADR
  `2026-10-07-the-reply-to-a-question-session-is-a-short-numbered-list.md`; `docs/AGENT_OS.md` §4.10.
  Host follow-up after a `subtree pull`: re-render the installed `.claude/agents/control-plane.md`
  (`agent-os-install --force`) to get condition 6, and set `project.human_login`.
- #113 -- Agentos v2, Stage 1: the tree format. New node state `implemented` (between `improvised` and
  `hardened`). `experiments` replaces `spikes` (kind `spike | demand-probe | question | lookup`,
  outcome may be `open`; a `question` carries its `scope` `what | how` and its `default_answer`);
  a node still using `spikes` is now a `schema` error, so a host tree migrates the field name and
  adds a `kind` to each entry after its next subtree pull. New `depends_on:` (a list of node ids)
  with the doctor codes `dangling-dependency` and `dependency-cycle`, and `challenge:` (`reason`
  `no-solution | no-verification | over-cost`). "Not hardenable" (an open `what` question, or a
  challenge on the node or on what it depends on) is `agent_os.product.tree.hardening`; `compile` does
  not use it yet. `context` shows state, dependencies, hardenability, experiments and the challenge,
  and `--json` carries them. See the dated note of ADR
  `2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md` and
  `docs/AGENT_OS.md` §4.6 (26 codes now).
- Agentos v2, Stage 1 (#114) -- code-quality checks on every pull request. A deterministic ratchet,
  `agent-os-quality --base REF` (`agent_os/quality/`), blocks in CI: new files and folders must be
  within `quality.max_lines_per_file` (300) and `quality.max_entries_per_folder` (12), and a touched
  one over a limit may not get worse than on the merge-base (a file may not grow, a folder may not
  gain an entry); git-tracked entries only. New optional `quality:` config section with
  `excluded_paths` (default `docs/`, `tests/golden/`, `config.example.yaml`, `uv.lock`; the tree
  root and a vendored `agent_os/` are always excluded). Wired into `.github/workflows/ci.yml`
  (checkout with `fetch-depth: 0`) and `templates/ci-host.yml`; `templates/ci-agent-os.yml` leaves
  it to `ci-host.yml`. The validator prompt gains a "code quality of the diff" review (SOLID, long
  names, comments only for a non-obvious why) that requests changes like any finding.
- #112 -- the v2 subsystems move under `agent_os/product/` (`git mv`, no behaviour change):
  `agent_os.tree` is now `agent_os.product.tree` and `agent_os.puntal` is `agent_os.product.puntal`;
  their tests move to `tests/product/`. `agent-os-tree` and `bin/puntal_task.sh` keep their names.
  A host that imported the old modules directly updates the import after its next subtree pull.
  See `docs/adr/2026-10-07-v2-subsystems-live-under-agent-os-product.md`.
- #115 -- the puntal's contract v2 (Agentos v2, Stage 1; `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`).
  `agent_os/product/puntal.py` becomes the package `agent_os/product/puntal/` (no file over 300
  lines); `bin/puntal_task.sh` keeps its flags. A click is now a **pre-helper** (the state the node
  declares in its frontmatter `reads:` is loaded by code), **one model turn with no tool** that returns
  a plan -- `{"operations": [...], "answer": ...}`, four operations (`put`, `update`, `delete`,
  `allocate`) with `{{name}}` placeholders for ids only the app can allocate -- an **executor** (the
  app's command, `puntal.executor_command`, applies the operations atomically and reports bindings or
  errors; one retry turn on a refusal) and **post-helpers** that run after the response is released.
  A plan that says it needs undeclared state costs one **slow turn**, the old tool loop under
  `prompts/puntal_slow.md`, marked in the telemetry; `--path slow` forces it. Telemetry schema **2**
  (adds `path`, `slow_path_reason`, `versions`, `turns`, `declared_reads`, `plan`, `executor`; outcomes
  `invalid_plan` and `executor_failed`, exit statuses `5` and `6`). New: `puntal_task.sh feedback`
  (accept, reject, retry in `.cache/puntal/feedback.jsonl`, keyed by `invocation_id`), the versions on
  every record (model, CLI version, agent-os commit and prompt digest; `agent_os/product/records/`,
  reusable by the judgments log), and `puntal_task.sh --json [--plan-only]`, one JSON-in/JSON-out entry
  independent of the app's stack. New optional config keys `puntal.executor_command`,
  `puntal.read_subcommands`, `puntal.executor_timeout_seconds`; new tree node field `reads`
  (`docs/AGENT_OS.md` §4.6, §4.7; ADR
  `2026-10-04-a-puntal-is-a-one-shot-headless-process-under-its-own-class-and-cannot-write-code.md`,
  dated paragraph). Host follow-up after a `subtree pull`: set `puntal.executor_command` (the fast
  path refuses without one) or call with `--json --plan-only`; a caller that read the telemetry as
  schema 1 reads `schema` first. The bench's `measure.py` takes `--puntal-path slow|fast` (default
  `slow`, the Phase 0 baseline) and has an executor for its store.
- agent-os#90 — a backend runs more than one worker at once: slots, separate from backends. The
  backend's name was the only key a run's state was kept under, so the real ceiling was one worker
  per `project.backends` entry whatever `planner.max_parallel_issues` said. New
  `project.backends.<name>.slots` (integer, default 1, validated at load). Slot 1 is exactly what a
  backend had -- `worktree`, `.cache/worker_<name>.*`, `agent_guard_<name>.json` -- so a host that
  sets nothing sees byte-identical paths, events and prompts; slot N > 1 is `<worktree>-N` and
  `.cache/worker_<name>-N.*`, with its own stall bookkeeping `agent_guard_<name>-N.json`. A derived
  name or worktree another slot already has (a backend literally named `claude-2`, say) fails the
  load. `worker_task.sh <backend> start` picks a free slot itself (one already on a branch naming
  the issue first, so the planner's `branch` + `start` land on the same one) and refuses, writing
  nothing, when every slot is busy; the cap and the `module:` exclusion now count every other slot,
  this backend's included. Every subcommand takes `--slot N`; `resume --issue N` finds the slot that
  recorded issue N (and, on a one-slot backend, refuses when the recorded issue is another);
  `status`/`init` without a slot cover every slot; the rest refuse to guess. The run's subshell
  carries its slot to `stage-exit`, `open-pr`, the chain and the exit hook (`agent_os.guard check
  <backend> --slot N`). The guard ticks (backend, slot) pairs; the quota verdict stays per backend,
  read as exhausted when any live slot's stream says so, so an exhausted window cuts every live slot
  and is reported once. The tick's `worker_cut` event names the issue it cut. `agent-os-doctor`
  checks every slot's worktree, `planner_task.sh` adds every slot's worktree to the planner's
  `--add-dir`, `worker_progress.sh` reports per slot. `prompts/planner.md` resumes with
  `--issue <N>` and says a backend may have several slots. The worker class's launch gate (#95)
  keeps both its behaviours on a slot: the refusal reads the backend's quota verdict (so it is the
  same on every slot), and `escalate:` reads how the previous process ended off the launching
  slot's own state file (ADR
  `2026-09-26-a-backend-runs-several-workers-in-slots-of-its-own.md`). Host follow-up: none to keep
  today's behaviour. To run two workers on one backend: set `slots: 2` on it, raise
  `planner.max_parallel_issues`, and run `worker_task.sh <backend> init` to create `<worktree>-2`.
- Agentos v2, what Agentos is for (owner design discussion of 2026-10-05/06; no issue, branch
  `feat/v2-global-goals`) -- Agentos's own tree moves from `docs/ledger/` to `docs/tree/` and gains
  its goals: four goals (a usable product early, grown by real use; faithful to its owner's goals
  over months; the owner decides what, Agentos decides how; Agentos improves with every product)
  seventeen functional requirements under them and six use cases (what the owner does with
  Agentos), all `mechanism: pending` -- the what is
  written first and the how is decided later. New decision `dec-one-owner-for-now`. `AGENTS.md`
  and `docs/AGENT_OS.md` open with what Agentos is for instead of what the v1 substrate does.
  Each goal carries its evaluators, set by the owner as trends until the vector gives the first
  measurements; they are part of the what, so only the owner changes them.

- Agentos v2, Phase 0 (`docs/AGENTOS_V2_PLAN.md`) -- the puntal spike. A **puntal** answers one live
  UI action with one headless `claude -p`, reading the action's node slice and reading and writing
  state only through the app's persistence API. New `bin/puntal_task.sh` (a thin shell half) and
  `agent_os/puntal.py`: the brief is rendered from the new `prompts/puntal.md`, the run is launched
  in an empty scratch directory with `--safe-mode`, `--tools=Bash`, `--permission-mode dontAsk` and one
  allow rule for the persistence shim `./state`, the stream is audited as it arrives and the run is
  cut at the first tool call outside that contract, at a passed ceiling, or at the safety timeout.
  Every invocation appends one JSON line of telemetry (action, node, session, latencies including
  time-to-first-signal, tokens, cost, tool calls, response, gap note) and one `runs.tsv` row. New
  `TaskClass.role: puntal` (`classes.puntal`: its three ceilings bind one invocation; a `fallback:`
  on it is refused at load) and a `puntal:` config section (`persistence_command`,
  `persistence_api_file`, `timeout_seconds`, `max_tool_calls`, `effort`), all optional with the
  defaults in `config.example.yaml`; a puntal logs under `.cache/puntal/` and the guard reads those
  logs as role quota observations. `bench/puntal/`, outside the package: a toy helpdesk over a JSON
  document store, five actions (one whose node is deliberately silent, to exercise the gap note), a
  reference model of their rules, a fake `claude`, and `measure.py`, the measurement -- real calls
  need `--allow-real-calls`, never run under pytest and are capped at 30 in code by a persistent
  counter, after free `--help`/`--version` checks of the real CLI and a calibration whose second
  call proves the persistence tool ran; `summarize` computes p50/p95 latency, time-to-first-signal, cost per action and
  persisted-state coherence across three sessions from the raw files alone. Tests stub the backend
  and fail on a trap `claude` (`no_real_backend`). ADR
  `2026-10-04-a-puntal-is-a-one-shot-headless-process-under-its-own-class-and-cannot-write-code.md`;
  `docs/AGENT_OS.md` §4.7. Numbers and the go/no-go are `docs/spikes/2026-10-puntal-latency.md`
  (no-go on time-to-first-signal, go on the other three criteria). Hosts: a `subtree pull`; nothing to configure unless you run puntales.

- Agentos v2, Phase 1 (`docs/AGENTOS_V2_PLAN.md`; no issue, branch `feat/v2-phase1-tree-schema`) --
  the product tree and the decision ledger, with their doctor. New package `agent_os.tree` and
  console script `agent-os-tree`: a node (goal, functional requirement, use case) and a decision are
  each one Markdown file with YAML frontmatter under one root (`tree.root`, default `product`, or
  `--root`), validated with pydantic in the repo's strict style (an unknown field is an error).
  `validate` (alias `doctor`) is a red check the way host literals are: 23 named codes, one line per
  defect with the file path, exit 1 (orphan files, missing or unknown fields, duplicate ids, id
  and filename or prefix mismatches, dangling or mistyped or cyclic parents, a hardened node
  without implementation or verification, a node pointing at a superseded decision, a superseded
  decision without an existing successor, ...). Tests run top-down from the goals: a goal may carry
  a `verification` (acceptance, never work: it still carries no mechanism, implementation, spike,
  foundation flag or state, and is never a ticket), and a node with children is a container whether
  or not it has a verification, so an upper node's verification is the acceptance of its subtree
  and never a ticket. `context NODE [--json]` emits the slice -- the node, its ancestors up to the
  goal with the verification each carries (labelled as the acceptance the node's work serves and
  must not break), the decisions in force on that chain (an `under-review` one labelled as still
  obeyed), their sources -- deterministic, and bounded by one chain whatever the size of the tree.
  `compile [--json] [--out-dir]` renders dispatch tickets from pending leaves that have an
  executable verification (shape checked by `validate_issue_body`, address `<!-- node: <id> -->`)
  and reports an escalation for each that lacks one; it renders only, no issue is created (Phase
  2). New optional config section `tree:` (`root`, `ticket_budget_class`, `ticket_labels`). The
  plan's six founding decisions are the ledger's first entries, in `docs/ledger/`, run through the
  doctor and the slicing by a test. ADR
  `2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`.
  Hosts: a `subtree pull`; nothing to configure until a host adopts v2 (Phase 3), and then
  `agent-os-tree validate` goes in its test command.

- agent-os#95 — a worker class's launch reads its own `fallback:`, and can escalate its model. A
  worker class could declare `fallback:` (it parsed on every class) but only the one-shot roles'
  drivers read it, so it was inert for the launch and still silenced the guard's
  `quota_exhausted_no_fallback` page. Now `worker_task.sh` asks the new `agent_lib worker-launch`
  (the roles' `role_launch_plan`, applied to the issue's class) at `start`/`resume`: a fresh
  `exhausted` verdict plus a declared `fallback:` **refuses** the launch before any side effect and
  names the backend/model/ceilings for the planner to redispatch on — it cannot swap the CLI in
  place, because the worker's worktree, branch, state and event stream are per backend (the
  premise "substitutes at launch" does not hold for a worker, `docs/AGENT_OS.md` §3). New optional
  class field `escalate: {model, after: [commit_cut, stage_failed]}`: the process `resume` launches
  after a cut or commitless stage runs the stronger model on the same backend, logged as
  `model: <m> (ESCALATED: ...)`; validated at load (worker classes only, a different model, a
  non-empty list of known triggers). The launched model is now the issue's class's own when it runs
  on the driver's backend (it was the first worker class on the backend). Left for a follow-up:
  direction rules beyond the existing default (a class without `fallback:` never leaves its
  backend; `qwen_fallback_eligible` remains the Claude to Qwen switch). Hosts: a `subtree pull`;
  add `escalate:`/`fallback:` to a class when wanted.

- agent-os#96 — agent models are config, and Claude roles default to Sonnet 5.5. The `model:` of
  `agents/*.md` was a literal (`opus` in the control plane), so moving a role to another model
  meant editing a generated file that `agent-os-install --force` overwrites. New
  `project.agent_models` (`control_plane` `sonnet`, `worker_runner` `sonnet`, `task_writer` `opus`),
  rendered as `__CONTROL_PLANE_MODEL__`, `__WORKER_RUNNER_MODEL__` and `__TASK_WRITER_MODEL__`; an
  unknown key fails the load. An agent definition has a single model, so task writing (Duty 1) is
  split out of the control plane into the new `agents/task-writer.md` (default `opus`), which
  `agent-os-install` now writes too; the control plane keeps the other duties and routes "escribe la
  tarea X" to it. `config.example.yaml`: planner and validator classes move to `claude-sonnet-5-5`,
  the refiner stays on `claude-opus-5`, a commented Sonnet worker class is added, and it states
  that model ids are opaque and cost is CLI-reported. `docs/AGENT_OS.md` documents that the quota
  verdict is per backend, not per model. Golden: `tests/golden/validator.md` now reads "Reviewed by
  the validator on claude (claude-sonnet-5-5)." (the example config's class model, one line).
  ADR `2026-09-29-claude-roles-default-to-sonnet-5-5-and-agent-models-are-config.md`. Hosts: after
  the `subtree pull`, run `agent-os-install --force` to regenerate `.claude/agents/`, and set
  `classes.<role>.model` / `project.agent_models` to keep any model you do not want moved.

- agent-os#97 — the refiner and planner see the worker classes from config. New optional
  `classes.<name>.description` (one line: when to choose the class), and `prompts/refiner.md` and
  `prompts/planner.md` carry a `__WORKER_CLASSES__` block rendered from `classes:` (worker classes
  only: name, backend, model, description). A host no longer names a model in its
  `prompt_extras.refiner`, so changing the model behind a class cannot leave the prompt lying;
  `config.example.yaml` describes its two classes. `agent-os-doctor` gains a warning (exit status
  untouched) when a `prompt_extras` file names a class that `classes:` does not define. Hosts: a
  `subtree pull`, then add `description:` to each worker class and drop model names from the
  prompt_extras file. `tier`/`cost_hint` were not added: nothing reads them.

- agent-os#92 — Qwen's context was double-counted. Current Qwen builds report
  `cache_read_input_tokens` as a part of `input_tokens`, and the shared Claude parser added the two,
  so the guard read every Qwen turn at about twice its size and cut Qwen stages on `max_context` at
  half their class budget (roedor's `369` stage 2: 337,636 read, 169,529 real). Qwen's parser now
  reads context from `input_tokens` alone. Hosts: a `subtree pull`; nothing to configure.

- agent-os#88 — the control plane's merge method is a host config key. `agents/control-plane.md`
  Duty 4 hardcoded `gh pr merge N --merge --delete-branch`, so a host that squashes had to
  hand-edit its installed `.claude/agents/control-plane.md`, and `agent-os-install --force` then
  overwrote the edit, leaving the host unable to take any upstream prompt change. New
  `project.merge_method` (`merge` | `squash` | `rebase`, default `merge`), validated at config load
  (any other value fails it) and rendered as `__MERGE_METHOD__`; `__REPO__` renders
  `project.repo`. The merge step is now REST, pinned to the head the five conditions were checked
  on: `gh api -X PUT repos/__REPO__/pulls/N/merge -f merge_method=__MERGE_METHOD__ -f sha=<head>`,
  then `gh api -X DELETE repos/__REPO__/git/refs/heads/<branch>` once it merged. A `409` (head
  moved) means verify again, never retry blindly; REST also stays off GraphQL's secondary rate
  limit (#70), and deleting only the remote ref no longer takes a backend's worktree with it.
  Not a goal: `install --force` keeping hand edits of the files it generates — a customization a
  host needs becomes a config key. Host follow-up: set `project.merge_method` in
  `config/agents.yaml` (a host that squashes: `squash`), run `agent-os-install --force`, and drop
  the local edit of `.claude/agents/control-plane.md`.

- agent-os#86 (PR #87) — a dirty worker worktree no longer deadlocks its backend unannounced.
  `worker_task.sh` writes `scratchpad/.gitignore` containing `*` in every worker worktree it
  touches (`hide_scratchpad_from_git`: before the dirty check in `start`, `resume` and `branch`,
  and before a cut's freeze), so an untracked diary or scratch file never refuses a dispatch in
  any run state and never lands in a `WIP: cut by guard` commit. The file lives in that worktree
  only and ignores itself; one the host tracks is left alone. A diary git tracks still shows as
  modified and #84 still covers it on `resume`. The #75 archive still empties `scratchpad/` for
  each new run under the same conditions, now listing ignored files too and keeping the
  `.gitignore`. What is still dirt is read by the guard on every tick (`backend_worktree_dirt`,
  same exclusions as the driver, nothing while a run is alive): the backend's ready issues leave
  the dispatchable set, so no planner run is woken to be refused, and the human is paged once per
  distinct listing with the new `project.messages.backend_worktree_dirty`; a clean worktree
  resets it. The issue asked for the page from the driver via `notify.sh`; the guard does it so
  the same read also ends the planner's retries (ADR
  `2026-09-25-scratch-is-invisible-to-git-and-a-dirty-idle-worktree-is-paged-by-the-guard.md`).
  `prompts/worker.md` and `prompts/planner.md` say so. Host follow-up: add
  `backend_worktree_dirty` to `project.messages` in `config/agents.yaml` (see
  `config.example.yaml`; without it the guard prints `no page for the dirty worktree`), and the
  `scratchpad/` entry in a worktree's `.git/info/exclude` can go.

- agent-os#84 (PR #85) — `worker_task.sh resume` over a run whose `.state` is `DONE` no longer
  refuses over that run's own diary. #22 left the diary out of `resume`'s dirty check only after
  `CUT_BY_GUARD`, on the premise that a finished run is never resumed; but a run that opened its
  pull request and exited is `DONE`, and it is exactly the one the planner resumes with the
  validator's request-changes review (`prompts/planner.md`, CHANGES REQUESTED). On a host with no
  ignore rule for `scratchpad/`, every request-changes loop was refused and needed a human.
  `drop_the_cut_runs_diary` is renamed `drop_the_resumed_runs_diary` and accepts `DONE` as well,
  same shapes, file untouched. Still refused: any other dirty path (another scratch file
  included), and a `.state` of `STARTED`, `RESUMED …`, `FAILED_LAUNCH …` or `BLOCKED …`. Host
  follow-up: the `scratchpad/` entry in a worktree's `.git/info/exclude` can go.

- agent-os#82 (PR #83) — `tests/test_no_host_literals.py` no longer requires `AGENT_OS_DIR` to
  hold its own `.git`. `_repository_files` demanded `root / ".git"` before ever asking git
  anything, but a host consuming this mechanism as a subtree (ADOPTION.md step 7) has no such
  file: `agent_os/` is a plain subdirectory of the host's own checkout, and only the host root
  carries `.git`. `git ls-files` resolves the enclosing repository by walking up from `cwd`,
  lists only what lies under `root` and names it relative to `root`, so the premise the test
  needs is "`root` is inside a git work tree", not "`root` is one": a `root` outside any
  repository still fails loudly, on git's own error. An empty listing now fails as well — a
  `root` its repository ignores lists nothing with exit 0 and would have passed without reading
  a file. Seen on titanarq/studentassistant#229 and in teachermovies:
  `test_no_host_literal_anywhere_under_agent_os` and `test_every_exclusion_still_applies` raised
  `RuntimeError: no .git under .../agent_os` on every subtree host. Both hosts deselected the two
  tests in their `ci-agent-os.yml`, a patch `agent-os-install` overwrites on every reinstall.
  Host follow-up: `git subtree pull`, then reinstall (or drop the `--deselect`s by hand).

- agent-os#70 (PR #81) — a GitHub rate limit is diagnosed before it is retried, and `issues.py
  validate` reads over REST. The "API rate limit already exceeded for user ID ..." a host read as a false
  positive is GitHub's answer for an empty **GraphQL** bucket, a quota separate from the REST
  `core` one that `gh api rate_limit`'s top-level `.rate` reports (read `.resources.graphql`).
  `gh_text` now asks `gh api rate_limit` (free) on a primary rate limit: a bucket at zero exits at
  once naming it, its limit and its reset time, instead of sleeping 31 s against a quota that
  refills up to an hour later; with quota left the refusal is retried as before. A secondary rate
  limit waits at least the minute GitHub asks for, and a bare 403 that is not a rate limit fails
  on its first answer instead of being retried five times. `validate` — run by `worker_task.sh
  start` before every dispatch — reads the issue with a REST `GET` and the open issues with the
  paginated REST listing (pull requests left out), so an empty GraphQL bucket no longer stops
  every dispatch. ADR `2026-09-25-a-rate-limit-is-diagnosed-against-the-logins-quotas-before-it-is-retried.md`.

- agent-os#75 (PR #80) — `worker_task.sh start` and `branch` no longer refuse the next dispatch
  over a finished run's other untracked files under `scratchpad/`, with or without a diary. #18
  archived the diary only when it was the one dirty path. A run that left an ad hoc script, a
  commit message draft and a `__pycache__/` there, with no `progress.log` at all (the reported
  case), kept every dispatch to that backend blocked until a human moved the directory out. Now,
  when `.state` records the run's ending, nothing is alive, and every dirty path is an untracked
  file under `scratchpad/`, all of them are archived to `.cache/diaries/`: the diary under #18's
  name `<run>.progress.log`, the rest under `<run>.scratchpad/` with their relative paths. These
  still refuse and move nothing: anything dirty elsewhere, a modified tracked file under
  `scratchpad/`, a run with no recorded ending, and `resume`. `retire_finished_runs_diary` is
  renamed `retire_finished_runs_scratchpad`. Host follow-up: nothing.

- (PR #79) — `templates/ci-agent-os.yml` is path-filtered to `agent_os/**` and to itself, as the
  2026-09-24 ADR, `AGENT_OS.md` §2.4, `ADOPTION.md` step 20, `install.py`, `doctor.py` and `lib.py`
  already said it was: the template had a bare `pull_request:` trigger and ran the mechanism's whole
  suite on every host PR, and `agent-os-doctor` counted it as the workflow that reports on every
  pull request, so a host without `ci-host.yml` passed the check the ADR meant it to fail. A test
  pins the filter and that the doctor does not count the file. `ADOPTION.md` step 20 adds: never
  make its job a required status check, since it does not run on a host-only PR. Host follow-up: a
  host with the old file gets the filter from `agent-os-install --force` after the subtree pull, or
  adds the `paths:` block by hand; keep `ci-host.yml` (or an unfiltered CI of your own) in place
  first.
- agent-os#72 (PR #77) — a refiner doubt the human already answered no longer comes back. The
  guard's `refine_pending` named every `status:refine` issue whose body fails the template, and a
  feature the refiner split never conforms: once the human answered its doubt and put
  `status:refine` back, every idle wake named it and the planner, never refining twice, parked the
  same answered question again. `refinable_issues` now lists the refine queue with its comments and
  drops an issue where the human commented after the latest `<!-- refiner-summary -->`
  (`agent_os.lib.refiner_pass_answered_by_the_human`); an unanswered summary is still named. The
  planner prompt says so, and the control plane's Duty 2 answers a split feature's doubt by lifting
  `blocked-on-human` only, never by restoring its refine label. Amends the 2026-09-15 refiner ADR.
- (PR #78) — `docs/ADOPTION.md` step 16 points `git subtree pull` at step 25, where the pull now is,
  instead of step 22 (arming the guard timer); every other "step N" cross-reference in `docs/`, the
  prompts, the templates and the code was checked against the current numbering (1-26) and holds.
  `templates/ci-agent-os.yml` cites `AGENT_OS.md` §5 step 7, the step that describes
  `agent-os-install`, instead of step 6. This section is reordered newest first, each entry naming
  the pull request that landed it, and the stray blank lines of parallel merges are gone.
- (PR #76) — the JavaScript actions every workflow uses move off Node 20, which GitHub is
  deprecating for actions: `actions/checkout@v4` -> `@v7` and `actions/setup-python@v5` -> `@v7`,
  both declaring `runs.using: node24` at their major tag (`checkout` runs on Node 24 from v5,
  `setup-python` from v6; v7 is the current major of each). Applies to this repository's
  `.github/workflows/ci.yml` and to `templates/ci-agent-os.yml` and `templates/ci-host.yml`, which
  `agent-os-install` writes into a host. Neither v7 removes anything these workflows use
  (`setup-python` v7 drops the `pip-install` input; `checkout` v7 refuses fork PRs only under
  `pull_request_target` and `workflow_run`). A self-hosted runner needs a runner version that ships
  Node 24. A host already installed keeps its old copies: after the subtree pull, `agent-os-install
  --dry-run` shows the diff, and `agent-os-install --force` rewrites them -- `--force` overwrites
  every file that differs, so a host that adapted its `ci-host.yml` edits the two `uses:` lines by
  hand instead.
- agent-os#52 (PR #74) — the guard's stall bookkeeping (`.cache/agent_guard_<backend>.json`) is
  scoped to the worker process it was counted in. The file now records `run_identity` (issue, start
  ref and PID of the live run); a tick whose run differs resets `commit_count`,
  `turn_count_at_commit` and `warned_at_turn_count` and keeps `last_quota_status`, so a new dispatch
  or a resumed stage is no longer measured from the previous run's anchor -- on Qwen that gave
  negative turns since commit, a late warn/cut, and a cut of a worker that had just committed. A
  file without the field counts as another run's. `turns_since_commit` also re-anchors at the
  process's start instead of going negative when the anchor is past its turn count, and a commit no
  longer drops the quota memory the same tick compares against. Claude's path counts from the live
  stream's own timestamps and never had the flaw.
- agent-os#27 (PR #73) — `issues.py move` no longer spends the user's shared GraphQL quota in
  proportion to the board. The board's `Status` field came from `gh project view` + `gh project
  field-list` on every move (~106 points on a 91-item board; one no-op move measured ~224), so a
  70-issue batch exhausted the 5000-points-an-hour quota every host shares. It is one bounded
  `gh api graphql` query now, answered once per process; the issue is read with a REST `GET`
  instead of `gh issue view`, and its one target label is checked with a REST `GET
  repos/{o}/{r}/labels/{name}` (created only on a 404) instead of `gh label list` —
  `ensure_fixed_labels` lists labels over REST too. A move costs three GraphQL requests of ~1
  point, independent of the board's size. New bulk form, backward compatible:
  `issues.py move 2 3 4 refine` resolves the label and the board field once, goes on past an
  issue that fails and exits non-zero naming it; one number prints exactly what it printed before.
- agent-os#54 (PR #69) — `agent-os-doctor`'s "labels that do not autocreate" check no longer
  requires `status:ai-completed`: it is a state label that `issues.py move` creates on first use, so
  a fresh host that has not yet completed a task passes. The check requires `status:agents-paused`,
  `auto-ready` and `wake:planner`, and `AGENT_OS.md` §4.3/§6 and `ADOPTION.md` steps 12 and 23 list
  only those three as labels to create by hand.
- agent-os#53 (PR #68) — `tests/test_no_host_literals.py` scans the files git knows (tracked, plus
  untracked-but-not-ignored) instead of walking the filesystem, and fails loudly when the root has
  no `.git` or `git ls-files` fails. Nested agent worktrees under `.claude/worktrees/` and ignored
  caches are no longer read; `.claude/worktrees/` and `.cache/` are now in `.gitignore`.
- agent-os#66 (PR #67) — the suite no longer registers worktrees in the repository that runs it. The
  launch-path tests of `tests/test_agent_task.py` ran the real driver with the checkout under test
  as its host, so every `git worktree add` wrote a registration into the real repository's gitdir,
  and a run that never reached its own removal left `/tmp/pytest-of-*/…/worktree-pr352-*` entries
  in `git worktree list` for every checkout. `launch_environment` now runs the driver out of a
  disposable git copy of the host (`AGENT_OS_HOST_ROOT` named outright), and the stand-in host of
  `tests/test_role_run_environment_isolation.py` is a repository of its own instead of a `.git`
  file naming the real gitdir; its heads are committed there too. Both files assert where the
  worktree was registered. Tests only; no driver behaviour changed.
- agent-os#50 (PR #65) — a PR whose head SHA reports zero checks now explicitly fails the control
  plane's merge condition 1 (`agents/control-plane.md` duty 4, `docs/AGENT_OS.md` §2.4): it hands
  the PR back to the human instead of merging. So that no PR lacks a check, `agent-os-install` also
  renders `.github/workflows/ci-host.yml`, running `project.test_command` on every pull request with
  no path filter (new key `project.install_host_ci`, default `true`; written only if absent,
  `--force` to overwrite), and `agent-os-doctor` fails when no workflow fires on `pull_request`
  without a path filter. `ADOPTION.md` step 23: land the host's CI before the first product PR, and
  never make the CI task depend on a skeleton. ADR
  `2026-09-24-a-pr-with-no-checks-fails-the-ci-condition-and-every-host-ships-a-ci.md`.
- (PR #59) — the mechanism is released under the MIT License (`LICENSE`).
- agent-os#39 (PR #62) — a split no longer strands the original's dependents. `issues.py supersede N
  --by A --by B [--route D=A]` rewrites every open issue's `Blocked by #N` line to the children
  (all of them unless a route narrows one dependent), comments on each dependent, then comments
  `Superseded by #A, #B` on N and closes it as `not planned`; it refuses a feature (its children
  are its parts), a child that is not open, and is idempotent. The refiner prompt calls it after
  splitting a task or bug. Before, the original stayed open and its dependents blocked forever, or
  unblocked too early when a human closed it; a host rewriting dependents by hand can stop.
- agent-os#61 (PR #64) — `worker_task.sh open-pr` classifies a rejected push. GitHub's refusal to
  let an App without the Workflows permission create or update a ref whose tree differs from the
  default branch under `.github/workflows/` -- which a stale branch hits without touching a
  workflow, typically after `open-pr`'s merge with its base conflicted -- now writes `BLOCKED
  reason=workflows_permission` instead of attempting a fast-forward onto a remote branch that does
  not exist. Every rejected push, classified or not, now comments the rejection on the issue and
  moves it to `status:blocked-on-human`; it used to stay in `status:doing` with no pull request and
  nothing visible. A later successful `open-pr` rewrites a leftover `BLOCKED` line 1 of `.state` to
  `DONE`. Hosts whose worker Apps lack Workflows permission: see `ADOPTION.md` §3.
- agent-os#41 (PR #63) — a fresh worktree is provisioned the way the host configures it, not by a
  hard-coded root `.venv`/`.env` link: `project.worktree_links` (default `[.venv, .env]`, the old
  behaviour) are symlinked from the main checkout, then `project.worktree_setup_command` (default
  empty) runs inside the worktree, for both the validator's throwaway worktree and
  `worker_task.sh <backend> init` (one shared helper, `agent_provision_worktree`). A setup that
  exits non-zero refuses the run -- no validator is launched, `init` removes the half-made tree
  and its branch -- instead of handing an agent an empty tree. The validator's prompt no longer
  claims the worktree is "already populated", its lint bullet renders from the new
  `project.lint_commands` (default empty: no bullet; `config.example.yaml` keeps the two `ruff`
  commands), and the shared-database pytest warning and the "~50 minutes" suite duration are gone
  (a host that needs the warning puts it in `never_run` or its validator `prompt_extras`). Closes
  §7 row (aa). Host follow-up: a monorepo sets `worktree_setup_command` to its own bootstrap
  (e.g. its `uv sync --frozen` / `npm ci`); a host that relied on the validator's ruff bullet sets
  `lint_commands`.
- agent-os#35 (PR #46) — in a host that vendors the mechanism under `agent_os/`, a role's worktree
  now runs the worktree's copy of the mechanism, not the main checkout's. `PYTHONPATH=<worktree>`
  alone left `<worktree>/agent_os/` as a namespace portion (it has no `__init__.py`), so the regular
  package the mechanism venv's editable `.pth` puts on `sys.path` won, and a validator testing a
  `subtree pull` certified code it never ran. The drivers now export
  `PYTHONPATH=<worktree>:<worktree>/agent_os` there (unchanged where the mechanism is the repository
  root) and link `agent_os/.venv` into the worktree beside the root `.venv` and `.env`; a worker's
  persistent worktree gets the link only where git ignores it. The mechanism's `.gitignore` names
  `.venv` without the trailing slash so that link is ignored. The worktree isolation test measures
  the mechanism's own package in such a host instead of skipping.
- agent-os#32 (PR #56) — `refine_pending` names the head of a ranked refine queue instead of the ten
  newest refine-needing issues: `guard.refinable_issues()` sorts by `lib.refine_queue_rank` —
  parent carries `labels.auto_ready` first, then the issue's best label in `labels.priorities`
  (none sorts last), then no open `Blocked by #N`, then issue number ascending. The parent's
  labels are read once per distinct parent, through the same lookup `promote_refined` now
  shares. The planner prompt says the list is in that order and to launch the refiner on the
  earliest listed issue that passes its summary check. A host that parked refine-needing issues
  to steer the order (studentassistant's `scripts/refine_window.py`) can drop that after the
  subtree pull.
- agent-os#15 (PR #60) — `issues.py create --type task|bug` (and `--template`) now puts the `title:`
  of that type's `.github/ISSUE_TEMPLATE/<type>.md` front matter (`[task] `, `[bug] `) in front of
  the given title. An issue created through the API skips GitHub's form, which is what adds the
  prefix to a hand-written one, so the refiner's sub-issues came out without it. A title that
  already starts with the prefix (case-insensitive, with or without its space) is left alone, so
  `[task] [task] ` cannot happen. A type with no template, or a template with no `title:`, keeps its
  title.
- agent-os#37 (PR #55) — `agent_guard.py tick` no longer dies on a stream event whose top-level
  `message` is a string (Claude Code's `system/permission_denied`, written when it refuses a tool
  call): the parsers, the guard's loop detector and the drivers' inline readers take `message` as an
  API message only when it is an object, and `read_events` drops any line that parses to something
  other than an object. One refused command used to stall every tick -- no promotion, no liveness,
  no quota verdict -- until its log aged out of the quota window. A host that worked around it (a
  `sanitize_role_logs.py` `ExecStartPre` rewriting the key) can drop the workaround.
- agent-os#33 (PR #58) — the planner, validator and refiner get a scratch directory of their own:
  each run is handed `AGENT_RUN_SCRATCH`, an empty `mktemp -d` directory outside `.cache/<role>/`
  and the checkout, which the driver removes when the run ends; the three prompts name it and
  forbid writing, moving or deleting anything under `.cache/`. A refiner had written its drafts
  into `.cache/refiner/` and then `rm -rf`'d it, deleting the run log, the PID file `role_died`
  detection reads and every `runs.tsv` row. A host's `prompt_extras` telling a role to use
  `mktemp -d` is no longer needed.
- agent-os#51 (PR #57) — the guard unit's `ExecStart=` no longer prefers a `.venv` at the host root
  when the host has a `scripts/agent_guard.py` shim: the shim, like the module form, now always runs
  on the mechanism's own interpreter (`unit_python()`), as AGENT_OS.md §8 already said, so the
  host's package versions cannot change how the guard behaves. The shim only re-executes
  `agent_os.guard` on that same interpreter, so nothing it needs came from the host's venv. A host
  whose unit was rendered with the host's `.venv` keeps it until it re-renders: run
  `agent-os-install --dry-run` to see the diff, then `agent-os-install --force` (which also rewrites
  the other installed templates) and `systemctl --user daemon-reload`.
- agent-os#23 (PR #47) — `issues.py create` now adds the new issue to `project.board_number`
  (`gh project item-add`) and, when it is created with a state label (`status:ready`, …), sets
  the column `project.board_columns` maps that state to on the item it just added. Before, a later
  `move` found no item to mirror onto unless the board auto-added issues. A board that refuses
  either step never fails the `create`: it prints one `board:` line saying why. `create` with
  `board_number: 0` makes no board call.
- agent-os#10 (PR #44) — the guard-timer failure `agent-os-doctor` prints no longer sends a host to
  `docs/runbooks/agent_monitor.md`, a runbook only the first host ever had. It now says what to
  run (`systemctl --user enable --now <guard_unit>.timer`, once `agent-os-install` has written the
  unit) and names `agent_os/docs/ADOPTION.md` steps 20 and 22. The same dead reference is gone
  from the rendered `override.conf`'s comment and from the `doctor`/`install` docstrings. This
  also closes the second point of agent-os#5.
- agent-os#13 (PR #49) — `docs/ADOPTION.md` step 7 spells out the `git remote add` + `git subtree
  add` commands and says when git needs a credential of its own. `titanarq/agent-os` is public now,
  so the add and every `subtree pull` need none. A `subtree push`, or any fetch from a private fork
  or mirror, needs one, and a `gh` login alone does not give it to git. The step gives `gh auth
  setup-git` as the fix, and an SSH remote as the alternative. Prose only: nothing in the mechanism
  runs this step, so there is no behaviour for a test to pin.
- agent-os#5 (PR #42) — `agent-os-doctor`'s board check no longer passes on a Project that is not
  the repository's: besides the `Status` field and its options, it reads the Projects linked to
  `project.repo` (`repository.projectsV2`) and fails when `project.board_number` is not one of them,
  naming the linked ones and the `gh project link` that would fix it. A `board_number: 1` copied
  from the example used to pass against whatever the owner's Project 1 was.
- agent-os#8 (PR #48) — `docs/ADOPTION.md` names the live config keys: step 14 puts a worker's App
  at `project.backends.<name>.app` instead of the deprecated `project.worker_apps.*`, and step 18
  runs `worker_task.sh <backend> init` once per `project.backends` entry with a `worktree` instead
  of per `project.worktrees` entry. `docs/AGENT_OS.md`'s actors table and §4.3 say the same. A test
  in `tests/test_backends_config.py` walks every `project.`/`mechanism.`/`planner.` key ADOPTION.md
  mentions through the config schema and fails on one the loader does not have or warns about as
  deprecated.
- agent-os#11 (PR #43) — the role prompts name no script under a host's own `scripts/`. The worker's
  HOW TO REPORT no longer sends every worker to `scripts/debug.py`, a file one host has: it asks
  for a breakpoint, a debugger session or a throwaway print, with the project's own debugging tool
  when the host's `project.prompt_extras` paragraph names one. The validator's evidence example
  spells the test runner as `__TEST_COMMAND__`, so it renders the host's `project.test_command`
  (the example config's `scripts/test.sh` renders word for word as before). `tests/golden/worker.md`
  changes by that one sentence. A test in `tests/test_prompt_templates.py` fails on any
  `scripts/<path>` in a template.
- agent-os#7 (PR #45) — `docs/ADOPTION.md` step 12 lists `wake:planner` among the labels a host
  creates by hand, next to `status:ai-completed`, `status:agents-paused` and `auto-ready`: those
  four are exactly what `agent-os-doctor` checks for, and a host that followed the old list failed
  the doctor's label check on its first run. Step 23 now says four labels, not three.
  `tests/test_adoption_doc.py` asks `doctor.check_labels` which labels it requires and fails when
  step 12 leaves one out.
- agent-os#4 (PR #40) — `agent-os-doctor` reports every check even when `gh` fails inside one of
  them: a failed `gh` call (a `project.repo` that does not exist, say) or a `gh`/`systemctl` that is
  not installed turns that check into a `[FAIL]` carrying the error on one line, and the run
  continues instead of exiting after the labels check.
- agent-os#22 (PR #29) — `worker_task.sh resume` no longer refuses to relaunch a run the guard cut
  over that run's own diary: when `.state` line 1 records `CUT_BY_GUARD` and nothing is alive, the
  dirty check leaves out `scratchpad/progress.log` (` M` when tracked, `??` when untracked, and the
  collapsed `?? scratchpad/` only while the diary is the one file inside it). The file stays on disk
  untouched, for the monitor and the resumed run. Any other dirty path, and a diary over any other
  `.state` (`STARTED`, `RESUMED`, `DONE`, `FAILED_LAUNCH`, `BLOCKED`), still refuse. A cut followed
  by `resume` no longer needs a host's `info/exclude` entry for the diary.
- agent-os#17 (PR #34) — the mechanism's own suite passes in a host that vendors it through `git
  subtree` whatever that host's layout: `test_agent_task.py` no longer asserts the host root holds
  exactly one top-level package and its own `.venv`. The worktree isolation test measures the first
  package the host's venv installs (of zero, one or several), and is skipped with its reason when
  the host has none, as a non-Python host does; only the mechanism's own repository still requires
  one. A host's `--deselect` workaround for the two tests can go after its next `subtree pull`.
- agent-os#6 (PR #24) — `pyproject.toml` depends on `PyJWT[crypto]>=2.8` instead of a bare
  `PyJWT>=2.8`: without the extra, the interpreter `bootstrap.sh` builds has no `cryptography`,
  PyJWT registers no RS256 signer, and `gh_app_token` fails with `KeyError: 'RS256'` signing the App
  JWT. A host that installed `cryptography` by hand as a workaround can drop that step.
- agent-os#3 (PR #38) — `agent-os-install` and `agent-os-doctor` no longer crash with a traceback
  when `config/agents.yaml` is missing, is not YAML or does not match the schema. `install` exits 1
  with one line naming the file (and, when it is missing, `ADOPTION.md` step 8); `doctor` reports it
  as a failed `config/agents.yaml loads` check and still runs the two checks that need no config
  (python version, `gh auth status`).
- agent-os#14 (PR #26) — `issues.py move` finds the issue's board item from the issue's own
  `projectItems` (one GraphQL query matching board number and owner) instead of listing the whole
  board with `gh project item-list`, which returned zero items for an org Project v2 that held them
  and so skipped every column mirror in silence.
- agent-os#12 (PR #31) — `agent-os-install` no longer renders a bare `python3` into the guard unit's
  `ExecStart=` when the host has a `scripts/agent_guard.py` shim but no root `.venv`: it uses the
  mechanism's own interpreter as `agent_os_python()` resolves it (`$AGENT_OS_PYTHON`, else the
  `.venv` `bootstrap.sh` builds), and refuses with a message naming `bootstrap.sh` and
  `AGENT_OS_PYTHON` when that is not an absolute path to an executable, in the module form too.
  Nothing is written in that case.
- agent-os#9 (PR #36) — `agent-os-install` no longer prints "would create" for a file it actually
  creates. Only `--dry-run` speaks in the conditional ("would create", "would overwrite
  (--force)"); a real run reports "created" and "overwritten (--force)", printed after the write.
  "up to date -- skipped" and "refusing without --force" are true in both modes and unchanged.
- agent-os#16 (PR #30) — `worker_task.sh start`'s base-branch gate accepts any lowercase `<word>`
  before `/<issue>-<slug>`, hyphens and digits included: `agent-os/37-gradle-skeleton` passes for
  #37, where `[a-z]+` refused it. The anchoring on the number is unchanged, so
  `task/387-close-the-390-gap` still fails for #390, and the refusal now names the accepted shape
  (`<word>/<issue>-<slug>`) instead of "a branch naming #N".
- agent-os#25 (PR #28) — the suite no longer leaves a `.cache/` in the checkout it runs from. The
  `rules` subcommands of `worker_task.sh` and `planner_task.sh` stop creating their cache
  directories. `test_agent_task.py`'s no-verdict cache moves out of the real `.cache`, and the
  `start` refusal tests get a disposable `WORKER_CACHE_DIR`. A conftest guard now fails any test
  that creates `<root>/.cache` when the session started without one.
- agent-os#18 (PR #20) — `worker_task.sh start` and `branch` no longer refuse the next dispatch over
  the previous run's diary: when `.state` records that run's ending (`DONE`, `CUT_BY_GUARD`,
  `FAILED_LAUNCH`, `BLOCKED`), nothing is alive and the untracked `scratchpad/progress.log` is the
  only dirty path, it is archived to `.cache/diaries/` and the dispatch proceeds. A diary whose run
  never recorded an end, any other leftover, and `resume` still refuse as before. A host's
  `info/exclude` entry or cleanup script for the file is no longer needed.
- #513 (this task) — the mechanism's own docs move under `agent_os/docs/`: `AGENT_OS.md` (from
  `docs/AGENT_OS.md`), its ADRs (from `docs/adr/`, dated 2026-09-14 through 2026-09-18 and
  2026-09-21), `ADOPTION.md` (the export recipe of §5 as a numbered checklist for a second host)
  and this file.

Wave 3's other two tasks, #429 (which backend fallback rule to write down as an ADR) and #514
(optional), add their own entries here once their pull requests merge.

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
