"""The dispatchable issue a launched change of a chat session returns as.

Same shape as the rework ticket of a rejected case (`session_ingest.rework_ticket`): the seven
sections in order and the budget line (`agent_os.lib.validate_issue_body` is run before the ticket
is allowed out), the node address the planner decides from when the change belongs to a case, and a
`<!-- key: -->` line by which a second ingestion finds the issue it already opened. What differs is
the source: the interpreter's reading of the owner's messages (`from_messages`), quoted whole
because the reading can be wrong and the worker has to be able to check it.

The headings are the validator's seven and cannot be renamed, so what the worker is told is carried
by the first words of three of them: `## Objective` opens with "Task" and holds the one thing to
do; `## Context` opens with "Context -- background, not part of the task" and holds everything else
the messages say; `## Not included` lists what the same messages said besides, item by item, as
tracked elsewhere
(`docs/adr/2026-10-10-an-issue-from-a-test-session-keeps-its-task-apart-from-its-context.md`).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_os.issues import prefixed_title
from agent_os.lib import TaskClass, validate_issue_body
from agent_os.product.dispatch.markers import render_marker_lines
from agent_os.product.dispatch.touched_code import touched_paths_of
from agent_os.product.session_ingest.rework_ticket import (
    ReworkTicketError,
    quoted_owner_words,
)
from agent_os.product.tree.models import Node
from agent_os.product.tree.slicing import JUDGED_BY_AGENT_LABEL

TRACKED_SEPARATELY = "tracked separately, NOT part of this task"

WHAT_EACH_KIND_OF_ITEM_IS = {
    "change": "a change launched as an issue of its own",
    "decision": "a decision that waits for the owner's confirmation in a session",
    "question_of_what": "an open question of what that waits for the owner's answer in a session",
}


@dataclass(frozen=True)
class OtherItem:
    """Something the interpreter read from the same messages that this issue does not do."""

    kind: str
    summary: str


@dataclass(frozen=True)
class TicketSubject:
    """What one issue is about, decided by the plan; the ticket only words it.

    `task` is the one thing to do and nothing but it; `origin` says where it came from and goes in
    the context; `others` are the items read from the same messages that this issue does not do."""

    key: str
    title: str
    summary: str
    task: str
    origin: str
    messages: str
    node_id: str | None
    is_rework: bool
    others: tuple[OtherItem, ...] = ()


def change_key(session_id: str, tail: str) -> str:
    return f"test-change.{session_id}.{tail}"


def render_change_ticket(
    subject: TicketSubject,
    node: Node | None,
    *,
    node_file: str | None,
    budget_class: str,
    task_classes: dict[str, TaskClass],
) -> tuple[str, str]:
    """`(title, body)`; raises `ReworkTicketError` when the body is not a brief an agent could start from."""
    about = f" on `{node.id}`" if node else ""
    objective = (
        "Task -- the only work this issue asks for. Do it and nothing else:\n\n" + subject.task
    )
    criteria = (
        f"- {JUDGED_BY_AGENT_LABEL}: the Task above is done{about}, and what the node's "
        "description says still holds"
        if node
        else f"- {JUDGED_BY_AGENT_LABEL}: the Task above is done",
        (
            "- The owner sees it in the next test session; the owner's state on it, not this "
            "ticket's closing, is what finishes it"
        ),
    )
    stages = ["- [ ] Do the Task; verified by the behaviour it describes"]
    if node:
        trailer = "rework" if subject.is_rework else "usage"
        stages.append(
            f"- [ ] If a commit touches `{node_file}`, give it `Node-Change: {trailer}`; verified "
            "by `agent-os-tree trailers`"
        )
    where = (
        f" The node is `{node.id}` (state `{node.state}`), its file is `{node_file}`."
        if node
        else ""
    )
    context = (
        "Context -- background, not part of the task. Nothing in this section asks for work.\n\n"
        f"{subject.origin} Launched by `agent-os-sessions test-ingest`.{where}\n\n"
        "The Task above is an interpreter's reading of the owner's messages, which are quoted "
        "whole below so that the reading can be checked. They may mention more than the Task "
        "names; whatever they mention that the Task does not name is not asked of you here. If "
        "the Task and the messages seem to disagree, or doing the Task would change what the "
        "product is for, do not guess and do not widen the Task: say so on this issue, the owner "
        "decides it in a session "
        "(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).\n\n"
        "The owner's messages, as the session recorded them:\n\n"
        f"{quoted_owner_words(subject.messages)}"
    )
    not_included = [
        f"- {other.summary} -- {WHAT_EACH_KIND_OF_ITEM_IS[other.kind]}; {TRACKED_SEPARATELY}."
        for other in subject.others
    ] + [
        "- Anything the Task does not name, even when a quoted message mentions it.",
        "- Changing the what: a decision of what waits for the owner.",
    ]
    sections = [
        ("## Objective", objective),
        ("## Acceptance criteria", "\n".join(criteria)),
        ("## Stages", "\n".join(stages)),
        ("## Context", context),
        ("## Not included", "\n".join(not_included)),
        ("## Dependencies", "none"),
        (
            "## Definition of done",
            "- Every acceptance criterion passes.\n- Documentation as the project's AGENTS.md asks.",
        ),
    ]
    body = "\n\n".join(f"{heading}\n{text}" for heading, text in sections)
    markers = [f"<!-- budget: {budget_class} -->"]
    if node:
        markers += render_marker_lines(node.id, (), touched_paths_of(node))
    markers.append(f"<!-- key: {subject.key} -->")
    ticket = body + "\n\n" + "\n".join(markers) + "\n"
    failures = validate_issue_body(ticket, task_classes=task_classes, open_issue_numbers=set())
    if failures:
        raise ReworkTicketError(
            f"the ticket {subject.key!r} is not a dispatchable issue body: " + "; ".join(failures)
        )
    return prefixed_title(subject.title, "bug" if subject.is_rework else "task"), ticket
