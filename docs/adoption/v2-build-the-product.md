# Onboarding v2, rungs 4-6: foundations, parallel slots, the test session

Continues [`v2-start-the-product.md`](v2-start-the-product.md); same shape per rung. Times are the first
host's local clock on 09-10 unless a date says otherwise; USD is what `runs.tsv` recorded for workers and
validators (not the control thread's tokens).

## Rung 4 - Foundations, one ticket at a time, worker and validator by hand

**What.** The tickets every other one stands on, built serially while a person watches: a way to run the
product, its persistence, the log of events from minute zero, the shell that routes each user action to
code or to a puntal, the executor that applies a puntal's operations, the progress signal, the owner's
verdict on an improvised answer. One worker, then one validator, then a merge, per ticket.
**Why.** `dec-a-puntal-plans-in-one-turn-and-code-executes` (the shell and the executor are what lets a
puntal answer a click), `dec-puntales-run-as-headless-processes`, `dec-tests-harden-they-do-not-build`
(foundations are built without tests first, then accepted), `dec-top-down-acceptance-is-essential-even-when-judged`
(the validator judges every pull request against the goals' acceptance, in a context apart from the
worker's), `dec-every-pull-request-gets-a-code-quality-review`, `fr-a-usable-product-exists-early`.
**How.** For ticket `<N>` (the order is the wave order; the route to puntales first, the rest later):
1. `git pull` the host's checkout; `python -m agent_os.product.dispatch start-gate <N> [<running>]` is 0.
2. The backend's worktree is clean; `agent_os/bin/worker_task.sh claude branch <branch>`.
3. `agent_os/bin/worker_task.sh claude start <N>` in the background; `... status` every few minutes (stage,
   cost); `... collect` at the end (its "deliverables" lists only `scratchpad/`: "none" is normal for code).
4. Read the pull request's diff: scope = the ticket's `touches`, the node's `state` changed with
   `Node-Change: usage`, no secret, nothing outside the host's quality ratchet.
5. `agent_os/bin/agent_task.sh validator <PR> --no-wake`; read the verdict. `python -m agent_os.issues move
   <N> review` refuses while a check is red or unfinished.
6. Merge only when every check is SUCCESS and the head contains `origin/main`
   (`gh pr view <PR> --json headRefOid,statusCheckRollup,mergeable`; `git fetch`; `git merge-base
   --is-ancestor origin/main <head>`), as a merge commit: `gh pr merge <PR> --merge --match-head-commit
   <sha>`; then `python -m agent_os.issues move <N> done`. A rejected pull request is reworked once
   (step 7); a second rejection goes to a person (the shell took three rounds, each decided by one).
7. Rework after `CHANGES_REQUESTED`: `agent_os/bin/worker_task.sh claude resume --issue <N> --rework`
   appends the stage `Address the changes requested on PR #<n>` to the issue's `## Stages` and launches it
   with the newest settling review as context (a plain `resume` refuses a run whose every stage is done);
   check the event stream grows in two minutes. The planner's prompt says the same and counts two such
   stages as the attempts before a person decides.
**Check.** Smoke the product with no spend after each ticket that touches the web (the host's run script,
then `curl` its health route); the validator's verdict and the merge sha are on the issue.
**First time.** The first worker (08-10, 0.59 USD) opened a pull request with CI red and the validator
approved it -- fixed: `issues move review` now judges the checks, the validator asks for changes, and a
malformed `Node-Change` trailer blocks `open-pr` (#138, #139). The worker did not run the host's quality
ratchet before opening the pull request, so ratchet failures arrived as rework (#26 cost a second
round) -- fixed: `open-pr` refuses a branch that fails the ratchet (agent-os#145). `open-pr` with
`merge_failed` wrote BLOCKED without moving the issue to `status:blocked-on-human` -- fixed: it comments
what was in the way and moves it (agent-os#150). Ticket nodes that named files a later ticket deleted were
not caught by the tree doctor -- fixed: it reports an `implementation` path that does not exist
(agent-os#145). `status` and `collect` sometimes take over 100 s (open). A pull request opened before
the branch contains `origin/main` goes red against a moved main: the driver merges `origin/main` first,
and the merge rule above is the guard.
**Baseline.** Eleven tickets, 15 rounds in all, merged for 43.5 USD in 5 h 25 min of the first host's
clock, serial from 11:53 to 13:22 (about 22 min per ticket),
two slots from 16:02. Per ticket (worker + validator): wave 0 web up 1.45; event log 1.56; persistence 5.23;
web skeleton 2.69; executor 3.26; register 1.65; log in and out 1.54; shell 13.22 over 3 rounds; progress
signal 2.61; one-command tests 2.42 over 2 rounds; owner verdict 7.88 over 2 rounds. Eight were approved in
round 1 (mean 2.5 USD); the three that were not cost 7.8 USD on average. The first real puntal answer
(a list view over seeded data) took 9.8 s, then 3.4 s, 5.5 s and about 4 s on later actions; the progress
signal appears in 1.4 ms. These are single measurements, not a distribution.
**First host.** The shell and executor live under `web/app/shell` with a puntal contract file named by
`project.prompt_extras`; the test command is `web/scripts/test.sh` (tree validation plus pytest).

## Rung 5 - Slots in parallel

**What.** Several workers at once, each in a worktree and branch of its own, as long as their tickets share
no code.
**Why.** `fr-independent-work-runs-in-parallel`; `dec-dispatch-never-runs-two-tickets-on-the-same-code`.
**How.**
1. Nothing to size: leave `project.backends.claude.slots` and `planner.max_parallel_issues` out. When a
   dispatch finds every slot busy, `worker_task.sh claude branch`/`start` makes the next one
   (`<worktree>-N`, with the host's `worktree_links` and setup command), so the number of workers follows the
   number of independent tickets and the quota is the only limit. `slots: N` only precreates slots with
   `worker_task.sh claude init`; set `max_parallel_issues` only if you want a ceiling anyway.
2. Before each launch ask the gate: `python -m agent_os.product.dispatch start-gate <N> <live issues>`;
   launch if it is 0 with `worker_task.sh claude branch ...` then `start <N>` (they land on the same slot).
   With more than one slot `collect`, `open-pr`, `stop`, `watch` and `resume` take `--issue <N>`. Ask the
   question after every finished worker: does more fit? (`agent_os.product.dispatch headroom` answers it
   read-only.) A free slot is reused before another is made.
3. Merge with step 6 of rung 4, one pull request at a time; when another slot merged first, merge
   `origin/main` into the branch, wait for CI, then merge.
4. Watch the shared quota: it belongs to the backend, so an exhausted window cuts every live slot and no new
   slot is made until it reopens. Park workers first; never the puntales the owner is trying.
**Check.** `status` without `--slot` lists every slot; `start-gate` refuses two tickets whose `touches`
overlap; each slot's worktree is clean before it starts.
**First time.** `worktree_links` symlinks the root `.venv` into each slot, and `.gitignore` `.venv/`
does not cover a symlink, so the worktree was dirty and the branch step refused (first host's workaround:
a virtualenv of its own per slot, built by hand) -- fixed: the driver's own links are not dirt
(agent-os#146). A quota cut with no events was recorded as `no_stage_commit` -- fixed: it is a quota cut
(#146). `collect`, `open-pr`, `stop` and `watch` demanded `--slot` although one run owns the issue --
fixed: they take `--issue` (#146). A rework after rejection needed a hand-made stage -- fixed:
`resume --rework` (#146). The planner did not page by the cap, only recorded it -- fixed: every run asks
`dispatch headroom` whether more can start, and starts all of it (agent-os#144). Slots were a fixed number,
not on demand -- fixed: the driver makes the next one (#152); a slot made for a ticket the start gate then
refused stays idle and is reused, never deleted, so prune the extra worktrees by hand when the work is done.
**Baseline.** Two slots from 16:02 (PR #30), five from 17:22 (PR #44); merges in the 17:18-17:33 window:
three, against one per 22 minutes serial.
**First host.** Five slots on one backend, `max_parallel_issues` 5, venvs `...-claude-2` to `-5`: delete the two
keys from its `config/agents.yaml` after the `subtree pull` and it grows past five on demand; the five stay.

## Rung 6 - The test session

**What.** A session the owner opens from the running product itself, whatever branch it is on, not one opened
for a branch. A "Test session" button in the app's header collapses and expands a side panel that keeps its
state (chosen case, half-written comment, scroll) across collapsing and navigating; the app's own pages are
not altered. At the top of the panel, always, even with nothing to try, one comments box with a state
dropdown beside it (perfect, ok with improvements, needs work, none); below it a "this screen only" checkbox,
on by default, the use cases to try prioritized by what the others depend on, and the guide of the chosen
one. The puntales' pending questions are answered in the same panel, in context. The box will be a chat
with the feedback interpreter (a later pull request, not described here as done); until then it records the
owner's message in the session file.
**Why.** `uc-open-a-test-session-for-a-branch`; `dec-a-test-session-happens-inside-the-app` (both rewritten
on the owner's word of 09-10 after the first test, below); `fr-the-owner-is-asked-only-in-sessions-they-open`;
`dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners` (the order of trying is a how, decided
by Agentos); `dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check` (what the owner accepts is kept as
evidence and hardens the node).
**How.**
1. Build it as tickets of rung 4, after the owner's verdict on an improvised answer: the panel and its header
   button in the shell, the session file the app writes as the owner sends each message (no close button: it closes by
   inactivity; `<tree.test_sessions_dir>/<id>.json`, the contract of `docs/AGENT_OS.md` section 4.11), and one command
   that starts the product with test data.
2. When the expert compiles the tree, give every `uc-*` node the `depends_on` of its use (register, sign in,
   create, ...): the list is ordered by it, and a node without it falls back to file-name order.
3. Keep the owner's web apart from the workers'. It runs from the main checkout, frozen while the owner
   tests; a newer version is offered on another port from a separate worktree over a copy of the owner's data
   (a SQLite backup), never over the live file. A worker stops only what it launched, by PID, never by pattern (`pkill -f`). The quota is shared with the workers: park workers
   first, never the puntales (rung 5, step 4).
4. While the owner tests and after, `agent-os-sessions test-ingest` prints the plan and writes nothing;
   read it, then `--apply` (an open session of schema 2 is read as it goes, and again on every run): an
   answered question goes into its node in the owner's words, a change the interpreter understood becomes one
   keyed issue, a decision is kept for the next session in `understood.json`, a rejected case of schema 1
   becomes one keyed rework issue with the note quoted whole, an accepted case is recorded on the node as
   `acceptances`; the owner's text no item covers waits until the session closes. A worker commits the tree edits with `Node-Change: usage` and a body line
   `Test-Session: <id>`; as it changes the what, it merges on the owner's word, not the validator's.
**Check.** The owner opens the panel from the header on any page and finds the comments box with no case
chosen; the list starts with what the others depend on; collapsing and navigating keep the draft; a rejected
case ends as an issue and then a pull request that names the owner's words; `test-ingest` without `--apply`
exits 0 on a closed session of schema 1.
**First time.** The first session (schema 1, per branch, PR #47 of the host; worker and validator 4.39 USD)
was opened for a branch with no cases and no questions; the owner closed it in 35 s and found nowhere to
comment. That is what rewrote the two tree nodes above in the owner's words (agent-os PR #147). The owner's
first rejection (20:09, "create an ad") went by hand from rejection to issue #62 to PR #63, merged: a single
ticket from verdict to fix, the loop `test-ingest` automates for a session of schema 1. The session was rebuilt (issue #64, PR #65,
one round of changes) as the panel above, with the file at `schema: 2` and a thread whose messages carry
`role: owner`. The list came out wrong ("Register" seventh) because the `uc-*` nodes declared no
`depends_on`; the host fixed it in PR #66 (step 2). The owner's web died during the test: a worker's smoke
test killed it by pattern (`pkill -f`); step 3 is the consequence. `test-ingest` now reads schema 2, open or
closed (`fix/test-session-ingest-v2`). Open: the verdicts on improvised answers are summarised in the plan and nothing is written from
them yet; the interpreter chat is not built.
**Baseline.** Session ticket 4.39 USD (worker and validator), the rebuilt one 10.15 (worker 5.48, validator
4.67, one round of changes), the first rejection fixed for 2.40. Single measurements, as in rung 4.
**First host.** The panel is `web/app/shell/sessions/` with its detail in `web/docs/sesion-de-pruebas.md`;
the owner's web runs from the main checkout, the new versions on a second port.
