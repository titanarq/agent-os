# A backend runs several workers, in slots of its own

- Date: 2026-09-26
- Status: accepted
- Modules: workers
- Issue: agent-os#90

## Context
`planner.max_parallel_issues` counts workers "across every backend", but the real ceiling was one
worker per `project.backends` entry: the backend's name was the only key a run's state was kept
under. `worker_task.sh` named its PID lock, events, state, issue and brief `.cache/worker_<backend>.*`
and read one `worktree` per backend; the guard's `worker_paths(backend)` derived the same names,
and its bookkeeping file `agent_guard_<backend>.json` held both the stall counters of the one run
and the backend's quota verdict. Two Claude workers on two `module:` areas were therefore
impossible.

The workaround since #514 -- a second entry `claude-b` with its own worktree -- works mechanically
and is wrong in three ways: the planner routes class -> backend and has no notion of two
equivalent backends, so the host load-balances by duplicating classes; quota is judged per name
while one subscription is behind both, so `claude` hitting its rate limit does not stop `claude-b`
until it hits it too; and the planner's prompt names the backends it knows.

## Decision
A **backend** is a CLI and its quota; a **slot** is one concurrent worker on it -- a PID, a
worktree and a branch. `project.backends.<name>.slots` (integer, default 1, validated at load)
says how many a backend has.

- **Slot 1 is the backend as it always was**: `worktree`, `.cache/worker_<name>.*`, and
  `agent_guard_<name>.json` for its stall bookkeeping. With `slots` omitted every path, message,
  event subject and rendered prompt is what it was, so an existing host needs no migration.
- **Slot N > 1 derives its names**: the worktree `<worktree>-N` (the sibling-directory shape a
  host already gives its backends' worktrees), the state files `.cache/worker_<name>-N.*`, and its
  own stall bookkeeping `agent_guard_<name>-N.json`. The derivation lives in one place,
  `agent_os.lib` (`worker_slot_key`, `worker_slot_worktree`, `worker_slots`, and the
  `worker-slots` CLI the drivers read), so the driver and the guard cannot name a slot's files
  differently.
- **Derived names that would collide fail at load.** `claude` with `slots: 2` derives
  `claude-2`, which is also what a backend *named* `claude-2` is called (and its quota verdict
  `agent_guard_claude-2.json` is where slot 2 would keep its stall counters); a derived worktree
  may equal another slot's. Either is refused when the config loads, naming both, because two
  runs writing one PID file is exactly the clobbering slots exist to prevent. An explicit list of
  worktrees was considered and not taken: the derivation needs no second place to keep in step
  with `slots`, and the collision check makes its one failure mode loud.
- **The quota verdict stays per backend**, in `agent_guard_<name>.json`, shared by every slot:
  the tick's reading of the backend's quota is `exhausted` when ANY live slot's stream says so, so
  the verdict does not flap between slots and an exhausted window cuts every live slot of that
  backend in the same tick. A change is reported once, by the first slot's tick that sees it. The
  lock the tick holds is the backend's verdict lock, whatever slot it checks.
- **The GitHub App stays per backend**: commits and comments are attributable to the backend; the
  branch and the pull request identify the run.
- **Dispatch stays by backend.** `worker_task.sh <backend> start <N>` picks a free slot itself --
  not alive, with a worktree -- preferring one already on a branch that names issue N (the
  planner's own `<word>/<N>-<slug>`), then a clean one holding no cut run awaiting its relaunch,
  then any clean one; `branch <name>` picks the same way, preferring a slot already on `<name>`, so
  the planner's `branch` then `start` for one issue land on the same slot. With every slot busy,
  `start` refuses and writes nothing. `planner.max_parallel_issues` stays the global cap and the
  `module:` exclusion is unchanged: both are counted over every live slot of every backend, this
  backend's other slots included.
- **Every other subcommand addresses a slot.** `--slot <n>` names one by hand; `resume --issue <N>`
  finds the slot whose recorded issue is N (the planner's prompt now passes it; on a one-slot
  backend it is also a check that the recorded issue is N); `status` and `init` without a slot
  cover every slot; `stop`, `collect`, `open-pr`, `freeze`, `watch` and the rest refuse to guess
  on a backend with several. The run's own subshell carries its slot as `WORKER_RUN_SLOT` and
  hands it on explicitly -- `WORKER_SLOT` to `stage-exit` and `open-pr`, `--slot` to the chain's
  `launch-stage` and to the guard's exit hook (`agent_os.guard check <backend> --slot N`) -- and
  the driver unsets `WORKER_SLOT` once it has read it, so the planner a finished run's exit hook
  wakes never inherits a slot it would then be pinned to. The guard's cut reaches the right run
  with `WORKER_SLOT` too.
- **The guard iterates (backend, slot) pairs** for liveness, budget, stall, drift and the cap it
  mirrors; a slot's lines and events are named by its key (the backend's name for slot 1). A
  backend's ready issues are held back as dirt only when no idle slot is clean, and each dirty
  idle slot is paged on its own. `agent-os-doctor` checks every slot's worktree.

## Consequences
- Two issues on different `module:` areas can run on one backend at once with a config edit
  (`slots: 2`, `max_parallel_issues: 2`) and one `worker_task.sh <backend> init`, which creates
  every missing slot worktree. No class is duplicated and the planner's routing is unchanged.
- One subscription is one quota verdict: a rate limit seen by one slot stops them all, and a role
  launched meanwhile reads the same verdict it always read.
- `resume` on a backend with several slots needs `--issue` (or `--slot`); a bare `resume` there is
  a usage error rather than a guess. The planner's prompt says `--issue <N>` everywhere it
  resumes, and the tick's `worker_cut` event now names the issue it cut, as the exit hook's did.
- Out of scope, as #90 says: load-balancing across *different* backends. The class keeps choosing
  the backend.
