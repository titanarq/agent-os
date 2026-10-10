"""How much room a host has for one more worker: the cap it chose to set, if any, as the driver counts it.

Workers alive are read as the issues in the doing state, which is what the driver's own count
(`worker_task.sh start`) and the guard's tick keep in step with.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from agent_os.lib import AgentsConfig, TaskClass, parse_budget_line

IssueRow = Mapping[str, object]


def backend_of(row: IssueRow, task_classes: Mapping[str, TaskClass]) -> str | None:
    """The backend the issue's budget class runs on; `None` when its body names no class this host has."""
    task_class = task_classes.get(parse_budget_line(str(row.get("body") or "")) or "")
    return task_class.backend if task_class else None


@dataclass
class SlotLedger:
    max_parallel_issues: int | None
    task_classes: Mapping[str, TaskClass]
    running_total: int = 0
    running_by_backend: Counter[str] = field(default_factory=Counter)

    @classmethod
    def of_host(cls, config: AgentsConfig, running_rows: Iterable[IssueRow]) -> SlotLedger:
        ledger = cls(
            max_parallel_issues=config.planner.max_parallel_issues,
            task_classes=config.classes,
        )
        for row in running_rows:
            ledger.take(row)
        return ledger

    def copy(self) -> SlotLedger:
        return replace(self, running_by_backend=Counter(self.running_by_backend))

    def take(self, row: IssueRow) -> None:
        self.running_total += 1
        backend = backend_of(row, self.task_classes)
        if backend is not None:
            self.running_by_backend[backend] += 1

    def refusal_for(self, row: IssueRow) -> str | None:
        """Why one more worker on `row` cannot start now for lack of room; `None` when it can. The
        only room there is is the cap a host chose to set: a backend with every slot busy makes
        the next one (docs/adr/2026-10-09-worker-slots-are-created-on-demand.md)."""
        if self.max_parallel_issues is not None and self.running_total >= self.max_parallel_issues:
            return (
                f"{self.running_total} worker(s) running or about to start in this pass "
                f"(>= planner.max_parallel_issues={self.max_parallel_issues})"
            )
        return None

    def summary(self) -> str:
        per_backend = ", ".join(
            f"{name} {count}" for name, count in self.running_by_backend.items()
        )
        cap = (
            "no cap (planner.max_parallel_issues unset)"
            if self.max_parallel_issues is None
            else f"planner.max_parallel_issues={self.max_parallel_issues}"
        )
        return f"{self.running_total} worker(s) running, {cap}" + (
            f" ({per_backend})" if per_backend else ""
        )
