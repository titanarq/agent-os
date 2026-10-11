# Worker slots are created on demand, and a number of slots is never a limit

- Date: 2026-10-09
- Status: accepted
- Modules: workers, dispatch
- Amends: `2026-09-26-a-backend-runs-several-workers-in-slots-of-its-own.md` (a slot count was the
  backend's ceiling), `2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md` (the
  cap defaulted to one)
- Tree: `docs/tree/fr-independent-work-runs-in-parallel.md`,
  `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`,
  `docs/tree/dec-puntales-run-as-headless-processes.md`

## Context
The owner, 2026-10-09: "¿por qué has limitado a 5 slots?" and, of a web that works through puntales,
"necesitará muchos agentes y a lo mejor hay agentes trabajando en partes de la web que están
desbloqueadas mientras tanto, no se deben limitar". The owner's only limit is the account's quota.

Two settings made a number the limit anyway: `project.backends.<name>.slots` (default 1) -- with
every slot busy `start` refused, "every slot of backend 'claude' is busy", and a one-slot backend
refused with "a run is alive" -- and `planner.max_parallel_issues` (default 1). A host had to
guess, before the work existed, how many workers it would need at once, and the guess was a cap. What
actually keeps two workers from colliding is not the number of slots: it is the start gate by
`touches` (`dec-dispatch-never-runs-two-tickets-on-the-same-code`), which refuses a ticket whose
dependencies are open or whose code overlaps a running ticket, whatever slot is free.

## Decision
**A number of slots is never a reason to refuse a dispatch.** When `worker_task.sh <backend> branch`
or `start` finds no free slot -- every slot alive -- the driver makes the next one and the dispatch
goes on in it. The planner asks no permission and raises no cap; it only records what
`dispatch headroom` says.

- **What is made.** The slot after the highest the backend has: worktree `<worktree>-N`, state files
  `.cache/worker_<backend>-N.*`, stall bookkeeping `agent_guard_<backend>-N.json`, branch
  `agent-os/init-<backend>-N` until the dispatch moves it onto the ticket's own. It is made by the
  same function `init` uses (`agent_os_init_worktree`): fetch `origin/main`, `git worktree add`, the
  host's `project.worktree_links` (the `.venv` link stage 1i made safe against the dirty check),
  `project.worktree_setup_command` and the mechanism venv link; a slot whose provisioning fails is
  removed with its branch, so the next dispatch starts from nothing.
- **When one is reused instead.** Never made while a slot is free: the order of the ADR of
  2026-09-26 is unchanged -- a free slot already on the branch the work belongs on, then a clean one
  holding no cut run awaiting its relaunch, then any clean one. A slot is free when its worker is not
  alive and its worktree exists; one that is only dirty is not "no free slot", so the existing
  `worktree is dirty` refusal and the guard's page for it stay as they were. Because the planner calls `branch` and then `start`, the slot is
  made at `branch`; if the start gate then refuses the ticket the slot stays, idle, and the next
  dispatch reuses it. `start` of an issue that an alive slot already runs is refused ("already
  alive ... in slot N") instead of making a slot to fail the base-branch check in.
- **Which slots exist.** The configured ones (`slots:`, at least one) and every sibling directory
  `<worktree>-N` (N above the configured count) that holds a worktree, read from disk -- no registry
  to drift from the worktrees, so a worktree restored or pruned by hand just is or is not a slot. One
  derivation, `agent_os.product.dispatch.slots.naming.worker_slots(project, root)`, re-exported by
  `agent_os.lib`, serves the driver (`agent_os.lib worker-slots`), the guard's tick and exit hook, the
  doctor, `planner_task.sh`'s `--add-dir` and `worker_progress.sh`. The driver walks slot numbers and
  not `1..N`, so a gap (slot 3 removed by hand) breaks nothing. A directory that is another
  backend's own configured worktree is never taken for a slot.
- **`slots:` is a floor.** Optional, default 1, meaning how many slots `init` precreates; a host that
  sets it keeps exactly the slots it had and gains the ones beyond. `planner.max_parallel_issues` is
  optional and absent (or `null`) means **no cap**; a host that sets it keeps the ceiling it set, and
  it still counts every live slot of every backend. The planner's prompt, `dispatch headroom` (no
  per-backend slot ceiling any more; its summary line says `no cap` when there is none), the guard's
  `new_dispatchable` suppression and the driver all read the same optional value.
- **What still stops a worker.** Only what the tree names: a cap the host chose, and quota. The
  `exhausted` verdict of a backend (the guard's persisted one, fresh within
  `mechanism.quota_verdict_ttl_minutes`; an older one reads as unknown, as the launch gate reads it)
  stops a new slot from being made -- `python -m agent_os.product.dispatch new-slot` refuses, writing
  nothing -- and, as before, cuts every live slot of the backend and refuses a launch whose class
  declares a fallback. Workers park; a puntal never does: it takes no slot, reads no cap
  (`tests/product/puntal/contract/test_puntal_never_asks_the_worker_cap.py` still holds).
- **Names that collide.** A backend literally named `claude-2` next to `claude` made the derived key
  `claude-2` ambiguous; the load-time check only covers the slots a config precreates, so a slot
  made later that would collide is refused when it would be made, naming both ("rename that
  backend"), nothing written. A derived worktree that is another backend's is refused the same way.
- **Two dispatches at once.** Creation holds `.cache/worker_slots.lock` (`flock`) and reads the slot
  tables again under it, so two dispatches that both found nothing free make slots N and N+1, never
  the same one. The lock file is the one thing a refused dispatch may leave behind.
- **`WORKER_WORKTREE`** (a test's, the run's own subshell's) pins every slot to one tree: there is
  nothing to make, and the slot's own refusal answers as it always did.
- **`doctor`** names the slots found on disk with the precreated ones in `worktrees exist`; it
  cannot flag an on-demand slot as missing, since the disk is what defines it.
- **Nothing is deleted.** A slot, once made, stays; this decision only reuses. Pruning idle slots is
  the host's, `git worktree remove` plus the slot's `.cache/worker_<backend>-N.*` files, and the
  slot is gone for every reader at once.

## Consequences
- A host that sets neither key runs as many workers at once as it has independent tickets and quota.
  The first host (five slots, `max_parallel_issues: 5`) keeps both until it deletes them from its
  `config/agents.yaml`; after a `git subtree pull` nothing else is needed -- no migration, no step
  by hand: its five slots exist, a sixth is made when needed.
- The planner sees a slot created during its own run only in the next run's `--add-dir`; it never
  needs to read a slot's tree.
- The per-backend line of `dispatch headroom` now counts running workers (`qwen 2`), not `2/N`; the
  JSON's `max_parallel_issues` is `null` without a cap.
- A ticket the start gate refuses after its slot was made leaves one idle worktree: bounded by the
  planner reading `headroom` before it dispatches, and reused by the next dispatch.
- Out of scope, as in 2026-09-26: balancing across different backends; the class still chooses the
  backend.
