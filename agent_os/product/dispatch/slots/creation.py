"""When the driver makes one more worker slot, and which one
(`docs/adr/2026-10-09-worker-slots-are-created-on-demand.md`).

`python -m agent_os.product.dispatch new-slot <backend>` is `worker_task.sh`'s question when a
dispatch finds every slot of a backend busy: it answers with the slot to create (printed as the
`<backend> <slot> <key> <worktree>` line `agent_os.lib worker-slots` prints) or refuses, and the
driver creates the worktree itself. The reasons to refuse are the ones the tree names: the cap a
host chose to set and the backend's quota (`docs/tree/fr-independent-work-runs-in-parallel.md`).
Nothing else -- the number of slots is never a limit."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from agent_os import lib
from agent_os.product.dispatch.slots.naming import (
    worker_slot_key,
    worker_slot_worktree,
    worker_slots,
)


class SlotRefusal(Exception):
    """No new slot now; the message is what the driver prints, and nothing was written."""


@dataclass(frozen=True)
class NewSlot:
    backend: str
    number: int
    key: str
    worktree: Path

    def as_driver_line(self) -> str:
        return f"{self.backend}\t{self.number}\t{self.key}\t{self.worktree}"


def plan_new_slot(
    project: lib.ProjectConfig,
    backend_name: str,
    *,
    root: Path,
    alive_workers: int,
    cap: int | None,
    quota_exhausted: bool,
) -> NewSlot:
    """The slot after the highest this backend has, or why there is none to make: its quota reads
    exhausted (workers wait for the window, a new worktree would only sit idle), the host's own
    `planner.max_parallel_issues` is reached, or the derived names are already someone else's."""
    if quota_exhausted:
        raise SlotRefusal(
            f"refusing to create a slot: backend '{backend_name}' reads quota exhausted -- "
            "workers wait for the window to reopen"
        )
    if cap is not None and alive_workers >= cap:
        raise SlotRefusal(
            f"refusing to dispatch: {alive_workers} worker(s) already running "
            f"(>= planner.max_parallel_issues={cap}) -- wait for one to finish"
        )
    backend = project.backends[backend_name]
    own_slots = [slot for name, slot in worker_slots(project, root) if name == backend_name]
    number = max(own_slots, default=0) + 1
    key = worker_slot_key(backend_name, number)
    worktree = (root / worker_slot_worktree(backend, number)).resolve()
    if key in project.backends:
        raise SlotRefusal(
            f"refusing to create slot {number} of backend '{backend_name}': its state files "
            f"worker_{key}.* belong to backend '{key}' -- rename that backend"
        )
    owners = {
        (root / worker_slot_worktree(project.backends[name], slot)).resolve(): name
        for name, slot in worker_slots(project, root)
    }
    if worktree in owners:
        raise SlotRefusal(
            f"refusing to create slot {number} of backend '{backend_name}': {worktree} is "
            f"already the worktree of backend '{owners[worktree]}'"
        )
    return NewSlot(backend_name, number, key, worktree)


def new_slot_command(backend_name: str, alive_workers: int, cache_dir: str | None) -> int:
    """Exit 0 and the slot's driver line, or exit 1 and the reason on stderr; 2 for a backend
    that is not configured with a worktree."""
    project = lib.load_project()
    if not (project.backends.get(backend_name) and project.backends[backend_name].worktree):
        print(f"'{backend_name}' is not a configured backend with a worktree", file=sys.stderr)
        return 2
    verdict = lib.read_persisted_quota_verdict(backend_name, cache_dir=cache_dir)
    verdict_window = lib.load_mechanism(lib.DEFAULT_AGENTS_CONFIG).quota_verdict_ttl_minutes * 60
    try:
        slot = plan_new_slot(
            project,
            backend_name,
            root=lib.HOST_ROOT,
            alive_workers=alive_workers,
            cap=lib.load_planner_config().max_parallel_issues,
            quota_exhausted=verdict.status == "exhausted"
            and (verdict.age_seconds or 0) <= verdict_window,
        )
    except SlotRefusal as refusal:
        print(refusal, file=sys.stderr)
        return 1
    print(slot.as_driver_line())
    return 0
