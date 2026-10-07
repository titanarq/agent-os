"""What `compile` returns: tickets, escalations and a count of what it did not dispatch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ticket:
    node_id: str
    # The node's file, relative to the host's root when the tree sits under it.
    path: str
    title: str
    body: str
    labels: tuple[str, ...]
    budget_class: str
    # The nodes whose tickets must be closed before this one starts (the node's `depends_on`).
    depends_on: tuple[str, ...] = ()
    # The paths the node is known to touch, which dispatch never lets two running tickets share.
    touched_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Escalation:
    node_id: str
    path: str
    code: str
    message: str


@dataclass(frozen=True)
class CompileResult:
    tickets: tuple[Ticket, ...]
    escalations: tuple[Escalation, ...]
    goals: int
    containers: int
    past_pending: int
