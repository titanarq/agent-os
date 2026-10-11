"""The names of a worker slot and the slots a host has (#90, on demand since stage 1l).

Imported by `agent_os.lib` for its config validation, so it never imports `lib` back: the types it
reads are only named for the type checker."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_os.lib import BackendConfig, ProjectConfig


def worker_slot_key(backend: str, slot: int) -> str:
    """What one worker slot's `.cache/worker_<key>.*` files -- and its guard-side stall bookkeeping
    and planner events -- are named after (#90): the backend's own name for slot 1, which is every
    path a backend had before slots existed, and `<backend>-<slot>` for the others."""
    return backend if slot == 1 else f"{backend}-{slot}"


def worker_slot_worktree(backend: BackendConfig, slot: int) -> str:
    """One slot's worktree, relative to the host's root exactly as `worktree` is: `worktree` itself
    for slot 1 and `<worktree>-<slot>` for the others -- the sibling-directory shape a host already
    gives its backends' worktrees (`../host-claude`, `../host-claude-2`)."""
    return backend.worktree if slot == 1 else f"{backend.worktree}-{slot}"


def slot_numbers_made_on_demand(project: ProjectConfig, backend_name: str, root: Path) -> list[int]:
    """The slots of `backend_name` beyond its configured `slots:`, found where the driver puts them:
    a sibling directory `<worktree>-<N>` that holds a worktree. Whatever is on disk is the truth, so
    a host that restores or prunes a worktree by hand needs no registry to keep in step. A directory
    that is another backend's own configured worktree (a backend named `claude-2` next to `claude`)
    is that backend's, never a slot of this one."""
    backend = project.backends[backend_name]
    base = root / backend.worktree
    if not base.parent.is_dir():
        return []
    configured_worktrees = {
        (root / worker_slot_worktree(other, slot)).resolve()
        for other in project.backends.values()
        if other.worktree
        for slot in range(1, other.slots + 1)
    }
    suffix = re.compile(rf"{re.escape(base.name)}-(\d+)")
    numbers = []
    for sibling in base.parent.iterdir():
        matched = suffix.fullmatch(sibling.name)
        if not matched or int(matched.group(1)) <= backend.slots:
            continue
        if (sibling / ".git").exists() and sibling.resolve() not in configured_worktrees:
            numbers.append(int(matched.group(1)))
    return sorted(numbers)


def worker_slots(project: ProjectConfig, root: Path | None = None) -> list[tuple[str, int]]:
    """Every (backend, slot) a worker can run in: each slot of each backend with a worktree, in
    declaration order and slot order -- the unit the guard ticks and the driver counts (#90).
    Without `root` these are the slots the config precreates (`slots:`, at least one); with the
    host's `root`, the ones the driver made on demand are there too."""
    return [
        (name, slot)
        for name, backend in project.backends.items()
        if backend.worktree
        for slot in (
            *range(1, backend.slots + 1),
            *(slot_numbers_made_on_demand(project, name, root) if root else ()),
        )
    ]
