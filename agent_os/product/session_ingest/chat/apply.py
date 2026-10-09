"""Carries out the plan of one closed chat session: the tree edits, the issues, the file for the app.

Every ticket is rendered and validated before anything is written or opened, so a missing budget
class never leaves half a session behind; every step is idempotent (see `plan`), so a run that stops
in the middle is finished by running the command again.
"""

from __future__ import annotations

import pathlib
from typing import Protocol

from agent_os.product.session_ingest.apply import (
    AppliedSession,
    ReworkTicketSettings,
    write_tree_edits,
)
from agent_os.product.session_ingest.chat.plan import ChatSessionPlan, IssueStep
from agent_os.product.session_ingest.chat.ticket import render_change_ticket
from agent_os.product.session_ingest.chat.understood import (
    read_understood_file,
    session_block,
    write_session_block,
)
from agent_os.product.tree.loader import Tree


class IssueTracker(Protocol):
    def find_by_key(self, key: str) -> int | None: ...

    def open(self, title: str, body: str, labels: list[str]) -> int: ...


def _render(step: IssueStep, plan: ChatSessionPlan, tree: Tree, settings: ReworkTicketSettings):
    node = tree.nodes[step.subject.node_id] if step.subject.node_id else None
    node_file = (
        f"{settings.tree_root.rstrip('/')}/{tree.paths[node.id].relative_to(tree.root)}"
        if node
        else None
    )
    return render_change_ticket(
        step.subject,
        node,
        session_id=plan.session.id,
        node_file=node_file,
        budget_class=settings.budget_class,
        task_classes=settings.task_classes,
    )


def apply_chat_plan(
    plan: ChatSessionPlan,
    tree: Tree,
    *,
    tracker: IssueTracker,
    settings: ReworkTicketSettings | None,
    understood_directory: pathlib.Path,
    ingested_at: str,
) -> AppliedSession:
    """`settings` may be None only for a plan with no issue still to open."""
    to_open = [step for step in plan.issues if step.existing_issue is None]
    if to_open and settings is None:
        raise ValueError("a plan with issues to open needs the settings of the ticket")
    tickets = [(step, *_render(step, plan, tree, settings)) for step in to_open if settings]
    read_understood_file(understood_directory)  # a damaged file refuses the run before any effect
    applied = write_tree_edits(
        tree,
        session_id=plan.session.id,
        closed_on=plan.session.closed_at.date(),
        answers=plan.answers,
        acceptances=plan.acceptances,
    )
    issues_by_key = {
        step.subject.key: step.existing_issue for step in plan.issues if step.existing_issue
    }
    for step, title, body in tickets:
        labels = (
            (settings.labels if step.subject.is_rework else settings.change_labels)
            if settings
            else []
        )
        issues_by_key[step.subject.key] = tracker.open(title, body, labels)
    applied.rework_issues.extend(issues_by_key.values())
    written = write_session_block(
        understood_directory, session_block(plan, issues_by_key, ingested_at)
    )
    applied.understood_file = written
    return applied
