"""Worker slots: where one concurrent worker of a backend lives, and when a new one is made.

A slot is one worker on a backend -- a PID, a worktree and a branch
(`docs/adr/2026-09-26-a-backend-runs-several-workers-in-slots-of-its-own.md`). Since stage 1l the
number of slots is not a setting a host has to get right: the driver creates the next one when a
dispatch finds none free (`docs/adr/2026-10-09-worker-slots-are-created-on-demand.md`).

- `agent_os.product.dispatch.slots.naming` -- the names a slot's files and worktree derive, and the
  slots a host has: the ones its config precreates plus the ones the driver made since.
- `agent_os.product.dispatch.slots.creation` -- whether the driver may make one more, and which.
"""
