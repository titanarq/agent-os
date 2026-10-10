"""The dispatchable issue a launched change of a chat session returns as.

Same shape as the rework ticket of a rejected case (`session_ingest.rework_ticket`): the seven
sections in order and the budget line (`agent_os.lib.validate_issue_body` is run before the ticket
is allowed out), the node address the planner decides from when the change belongs to a case, and a
`<!-- key: -->` line by which a second ingestion finds the issue it already opened. What differs is
the source: the interpreter's reading of the owner's messages (`from_messages`), quoted whole beside
the reading, because the reading can be wrong and the worker has to be able to check it.
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


@dataclass(frozen=True)
class TicketSubject:
    """What one issue is about, decided by the plan; the ticket only words it."""

    key: str
    title: str
    summary: str
    objective: str
    messages: str
    node_id: str | None
    is_rework: bool


def change_key(session_id: str, tail: str) -> str:
    return f"test-change.{session_id}.{tail}"


def render_change_ticket(
    subject: TicketSubject,
    node: Node | None,
    *,
    session_id: str,
    node_file: str | None,
    budget_class: str,
    task_classes: dict[str, TaskClass],
) -> tuple[str, str]:
    """`(title, body)`; raises `ReworkTicketError` when the body is not a brief an agent could start from."""
    about = f" on `{node.id}`" if node else ""
    objective = f"{subject.objective}\n\nThe owner's messages, as the session recorded them:\n\n"
    objective += quoted_owner_words(subject.messages)
    criteria = (
        f"- {JUDGED_BY_AGENT_LABEL}: what the messages above ask for is done{about}, and what the "
        "node's description says still holds"
        if node
        else f"- {JUDGED_BY_AGENT_LABEL}: what the messages above ask for is done",
        (
            "- The owner sees it in the next test session; the owner's state on it, not this "
            "ticket's closing, is what finishes it"
        ),
    )
    stages = ["- [ ] Make the change the messages ask for; verified by the behaviour they describe"]
    if node:
        trailer = "rework" if subject.is_rework else "usage"
        stages.append(
            f"- [ ] If a commit touches `{node_file}`, give it `Node-Change: {trailer}`; verified "
            "by `agent-os-tree trailers`"
        )
    where = (
        f"The node is `{node.id}` (state `{node.state}`), its file is `{node_file}`. "
        if node
        else ""
    )
    context = (
        f"Launched from test session `{session_id}` by `agent-os-sessions test-ingest`. {where}"
        "The reading above is an interpreter's, not the owner's: when it and the quoted messages "
        "disagree, the messages are right. If doing this would change what the product is for, do "
        "not guess: say so on this issue, the owner decides it in a session "
        "(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`)."
    )
    sections = [
        ("## Objective", objective),
        ("## Acceptance criteria", "\n".join(criteria)),
        ("## Stages", "\n".join(stages)),
        ("## Context", context),
        (
            "## Not included",
            (
                "- Anything the messages do not ask for.\n"
                "- Changing the what: a decision of what waits for the owner."
            ),
        ),
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
