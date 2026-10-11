"""Carries out the plan of one closed session: the tree edits first, then the rework tickets.

Everything that can fail before a file is touched fails first: every ticket is rendered and
validated before the tree is edited and before an issue is opened, so a missing budget class never
leaves half a session behind. Every step is idempotent (see `plan`), so a run that stops in the
middle is finished by running the command again.

The tree edits are made in the working tree and nothing else: like `agent-os-sessions apply`, a
pull request carries them to the tree, and it is a change to the what merged on the owner's word
(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).
"""

from __future__ import annotations

import datetime
import pathlib
from dataclasses import dataclass, field
from typing import Protocol

from agent_os.lib import TaskClass
from agent_os.product.session_ingest.plan import (
    AcceptanceStep,
    AnswerStep,
    ReworkStep,
    SessionPlan,
)
from agent_os.product.session_ingest.rework_ticket import (
    render_rework_ticket,
    rework_title,
)
from agent_os.product.sessions.writeback import answer_question, record_acceptance
from agent_os.product.tree.loader import Tree


class ReworkTracker(Protocol):
    """What ingestion needs of the tracker; the tests give it a fake, `github_tracker` the real one."""

    def find(self, session_id: str, node_id: str) -> int | None: ...

    def open(self, title: str, body: str, labels: list[str]) -> int: ...


@dataclass(frozen=True)
class ReworkTicketSettings:
    budget_class: str
    task_classes: dict[str, TaskClass]
    labels: list[str]
    tree_root: str
    change_labels: list[str] = field(default_factory=list)


@dataclass
class AppliedSession:
    written_files: list[pathlib.Path] = field(default_factory=list)
    answers_written: int = 0
    acceptances_written: int = 0
    rework_issues: list[int] = field(default_factory=list)
    understood_file: pathlib.Path | None = None


def _rendered_tickets(
    plan: SessionPlan, tree: Tree, settings: ReworkTicketSettings
) -> list[tuple[ReworkStep, str, str]]:
    rendered = []
    for step in plan.reworks:
        if step.existing_issue is not None:
            continue
        node = tree.nodes[step.case.node]
        node_file = f"{settings.tree_root.rstrip('/')}/{tree.paths[node.id].relative_to(tree.root)}"
        body = render_rework_ticket(
            node,
            session_id=plan.session.id,
            note=step.case.note,
            node_file=node_file,
            budget_class=settings.budget_class,
            task_classes=settings.task_classes,
        )
        rendered.append((step, rework_title(node, plan.session.id), body))
    return rendered


def write_tree_edits(
    tree: Tree,
    *,
    session_id: str,
    closed_on: datetime.date,
    answers: list[AnswerStep],
    acceptances: list[AcceptanceStep],
) -> AppliedSession:
    """The edits of the owner's words into the nodes, which every schema of the session file shares."""
    applied = AppliedSession()
    for answer in answers:
        if not answer.already_written:
            question = answer.question
            written = answer_question(tree, question.node, question.question, question.answer or "")
            applied.written_files.append(written)
            applied.answers_written += 1
    for acceptance in acceptances:
        if not acceptance.already_recorded:
            written = record_acceptance(tree, acceptance.node, session_id, accepted_on=closed_on)
            if written is not None:
                applied.written_files.append(written)
                applied.acceptances_written += 1
    return applied


def apply_session_plan(
    plan: SessionPlan,
    tree: Tree,
    *,
    tracker: ReworkTracker,
    settings: ReworkTicketSettings | None,
) -> AppliedSession:
    """`settings` may be None only for a plan with no rework still to open."""
    pending_rework = [step for step in plan.reworks if step.existing_issue is None]
    if pending_rework and settings is None:
        raise ValueError("a plan with rework to open needs the settings of the ticket")
    tickets = _rendered_tickets(plan, tree, settings) if settings and pending_rework else []
    applied = write_tree_edits(
        tree,
        session_id=plan.session.id,
        closed_on=plan.session.closed_at.date(),
        answers=plan.answers,
        acceptances=plan.acceptances,
    )
    applied.rework_issues.extend(
        step.existing_issue for step in plan.reworks if step.existing_issue is not None
    )
    for _step, title, body in tickets:
        applied.rework_issues.append(tracker.open(title, body, settings.labels if settings else []))
    return applied
