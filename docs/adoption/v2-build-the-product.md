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
   <sha>`; then `python -m agent_os.issues move <N> done`. A rejected pull request is reworked once with
   the recipe below; a second rejection goes to a person (the shell took three rounds, each decided by one).
7. Rework after `CHANGES_REQUESTED`: `worker_task.sh claude resume --issue <N> --rework` appends the
   stage `Address the changes requested on PR #<n>` to the issue's `## Stages` and launches it with the
   newest settling review as context (a plain `resume` refuses a run whose every stage is done); check
   the event stream grows in two minutes. The planner's prompt says the same, and counts two such
   stages as the attempts before a person decides.
**Check.** Smoke the product with no spend after each ticket that touches the web (the host's run script,
then `curl` its health route); the validator's verdict and the merge sha are on the issue.
**First time.** The first worker (08-10, 0.59 USD) opened a pull request with CI red and the validator
approved it -- fixed: `issues move review` now judges the checks, the validator asks for changes, and a
malformed `Node-Change` trailer blocks `open-pr` (#138, #139). The worker does not run the host's
quality ratchet before opening the pull request, so ratchet failures arrive as rework (open: #26 cost a
second round). `open-pr` with `merge_failed` wrote BLOCKED without moving the issue to
`status:blocked-on-human` -- fixed: it comments what was in the way and moves it, like the other endings. Ticket nodes that name files a later ticket deleted are not caught by the
tree doctor (open). `status` and `collect` sometimes take over 100 s (open). A pull request opened before
the branch contains `origin/main` goes red against a moved main: the driver merges `origin/main` first,
and the merge rule above is the guard.
**Baseline.** Eleven tickets merged, 43.5 USD, serial from 11:53 to 13:22 (about 22 min per ticket),
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
1. `project.backends.claude.slots: N` and `planner.max_parallel_issues: N`; `worker_task.sh claude init`
   creates `<worktree>-2..N`. Give each slot an interpreter and `.env` of its own (below).
2. Before each launch ask the gate: `python -m agent_os.product.dispatch start-gate <N> <live issues>`;
   launch if it is 0, then `worker_task.sh claude start <N> --slot <S>`. With more than one slot every
   subcommand except `start`, `branch`, `status`, `init` and `resume --issue` needs `--slot`. Ask the question after every finished
   worker: does more fit? Free the slot when its worker ends, not when its pull request merges.
3. Merge with step 6 of rung 4, one pull request at a time; when another slot merged first, merge
   `origin/main` into the branch, wait for CI, then merge.
4. Watch the shared quota: it belongs to the backend, so an exhausted window cuts every live slot.
   Park workers first; never the puntales the owner is trying.
**Check.** `status` without `--slot` lists every slot; `start-gate` refuses two tickets whose `touches`
overlap; each slot's worktree is clean before it starts.
**First time.** `worktree_links` symlinks the root `.venv` into each slot, and `.gitignore` `.venv/`
does not cover a symlink, so the worktree is dirty and the branch step refuses (open; first host's
workaround: a virtualenv of its own per slot, built by hand). A quota cut with no events is recorded as
`no_stage_commit` (open). `collect`, `open-pr`, `stop` and `watch` demand `--slot` although one run owns
the issue (open). A rework after rejection needs the manual stage (rung 4, step 7) (open). The planner
does not page by the cap, only records it (open). Slots are a fixed number, not on demand (open).
**Baseline.** Two slots from 16:02 (PR #30), five from 17:22 (PR #44); merges in the 17:18-17:33 window:
three, against one per 22 minutes serial.
**First host.** Five slots on one backend, `max_parallel_issues` 5, venvs `...-claude-2` to `-5`.

## Rung 6 - The test session

**What.** The owner opens a test session for a branch inside the running product: it shows what changed
since the last session and the cases to try, ordered by exposure; the owner accepts, rejects or retries
each improvised answer, and the puntales ask their pending questions in context.
**Why.** `dec-a-test-session-happens-inside-the-app`; `uc-open-a-test-session-for-a-branch`;
`dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check` (what the owner accepts is kept as evidence and
hardens the node).
**How.** Build, as ordinary tickets of rung 4, the owner's verdict (accept/reject/retry per response) and
the test-session page; then hand the owner one command that starts the product with test data, a list of
what to try, and where each verdict is recorded. Answers go back into nodes by pull request
(`agent-os-sessions answers/apply`, `verify-answer`).
**Check.** A verdict recorded on a real puntal answer is recorded where the verdict ticket says and appears in the
node's history; the owner can run it without help.
**First time / baseline.** In flight when this was written: the session ticket's pull request was open
(PR #47) and its worker done; the owner had not yet tested. No baseline.

## Not yet exercised in the first host

The planner running unattended, the guard and its timer (armed only by the owner; the doctor stays red on
the notification topic and the timer on purpose), the notification topic, slots on demand (no fixed
number), question sessions through `agent-os-sessions open`, the progress board (`agent-os-tree board
sync`), a second product (the baseline that `goal-improves-with-every-product` compares against).
