# A worker class refuses an exhausted backend and escalates its model on the same one

- Date: 2026-09-29
- Status: accepted
- Modules: worker driver (`bin/worker_task.sh`), `agent_os/lib.py` (`TaskClass`, `worker_launch`)
- Issue: agent-os#95; follows #425 (the roles' launch fallback)

## Context

A worker class carried one `backend` and one `model`. `fallback:` parsed on any class but only the
one-shot roles' drivers read it (`role_launch_plan`), so on a worker it was inert for the launch
and still made `allows_backend_fallback` true, silencing the guard's `quota_exhausted_no_fallback`
page for a run nothing could reroute. A host that moved a Claude worker class to a cheaper model
also had no way to say "retry a failed stage on the stronger one" short of a second class and a
human relabelling the issue's budget line.

The report proposed that the worker launch substitute the fallback backend the way a role's does.
That premise does not hold for a worker. A role is one process in a throwaway worktree; a worker
runs in a per-backend worktree, and its branch, pidfile, state file, event stream and stream parser
are all per backend, the guard's `check <backend>` reads them by that name, and the branch the
planner cut for the issue is checked out in that worktree (a second worktree cannot check it out).
Launching another CLI under the first backend's name would put Qwen events under the Claude parser
and the Claude quota detector.

## Decision

1. **A worker launch consults the class's declarations** through `agent_lib worker-launch`, which
   composes the roles' `role_launch_plan` (fresh `exhausted` verdict on the class's backend plus the
   class's `fallback:`) with the escalation below. Only `start` and `resume` may refuse; a chained
   stage has passed the quota gate in `stage-exit`.
2. **A substitution is a refusal that names the route, not a swap.** The driver refuses before any
   side effect and prints the fallback's backend, model and ceilings; the planner redispatches on
   that backend's own worktree, which is what `qwen_fallback_eligible` already made it do. So
   `allows_backend_fallback` stays true for a worker declaring `fallback:`: the launch does honour
   it, by routing instead of running into the wall.
3. **`escalate: {model, after}` is same-backend and per process.** After a `resume` whose previous
   process ended as `commit_cut` (a `CUT_BY_GUARD` other than `quota`, `paused`,
   `issue_unreadable`) or `stage_failed` (`CUT_BY_GUARD reason=no_stage_commit`), the next process
   runs the stronger model, logged on the `model:` line. It is read off the driver's own state
   file, never an agent's claim. A fresh `start` and a chained stage run the class's own model.
   It does not count for `allows_backend_fallback`: a stronger model on an exhausted window is no
   way round it, so a quota cut never escalates.
4. **The launched model is the issue's class's own** when that class runs on the driver's backend;
   `WORKER_MODEL` still pins it and outranks escalation.

## Consequences

- A Claude worker class on a cheaper model gets a stronger retry with no second class.
- A worker `fallback:` costs no launch into a wall and pages nobody it can reroute.
- Not done: direction rules beyond the default (no `fallback:` means the class never leaves its
  backend; only a class that declares one may). A backend with `quota: none` never has an
  `exhausted` verdict, so a `fallback:` on it never triggers.
