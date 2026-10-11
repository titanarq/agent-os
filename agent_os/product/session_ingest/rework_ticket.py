"""The dispatchable issue a rejected case returns as: rework of the node the owner rejected.

The ticket has the shape `agent_os.lib.validate_issue_body` accepts (the seven sections in order,
then the budget line), the node address the planner of a v2 host decides from
(`agent_os.product.dispatch.markers`), and a `<!-- key: -->` line that is how a second ingestion of
the same session finds the issue it already opened (`agent_os.issues.find_by_key`) instead of
opening another.

Whether the note asks for the node to be fixed (rework) or to be decided (a question of what) is not
something a program can tell from free text reliably. Every rejection is therefore a rework ticket
that quotes the note whole and says so, and the expert, who reads questions before the owner does,
may reclassify it (`docs/adr/2026-10-07-the-expert-populates-the-tree-and-settles-a-how-before-the-owner-hears-it.md`).
"""

from __future__ import annotations

from agent_os.issues import prefixed_title
from agent_os.lib import TaskClass, validate_issue_body
from agent_os.product.dispatch.markers import render_marker_lines
from agent_os.product.dispatch.touched_code import touched_paths_of
from agent_os.product.tree.models import Node
from agent_os.product.tree.slicing import JUDGED_BY_AGENT_LABEL

NO_NOTE = "(the owner gave no note)"


class ReworkTicketError(ValueError):
    """The ticket rendered for a rejection is not a brief an agent could start from."""


def rework_key(session_id: str, node_id: str) -> str:
    return f"test-rework.{session_id}.{node_id}"


def rework_title(node: Node, session_id: str) -> str:
    return prefixed_title(f"Rework `{node.id}`: rejected in test session {session_id}", "bug")


def quoted_owner_words(note: str) -> str:
    """The owner's words, every line quoted so that no line of them can start a section heading, and
    with the comment delimiters defused so that none can forge a marker line."""
    safe = (note or NO_NOTE).replace("<!--", "&lt;!--").replace("-->", "--&gt;")
    return "\n".join(f"> {line}" if line else ">" for line in safe.splitlines())


def render_rework_ticket(
    node: Node,
    *,
    session_id: str,
    note: str,
    node_file: str,
    budget_class: str,
    task_classes: dict[str, TaskClass],
) -> str:
    objective = (
        f"The owner rejected `{node.id}` ({node.title}) in test session `{session_id}`. Make it "
        "do what the owner expected, as the note below says.\n\nThe owner's note:\n\n"
        f"{quoted_owner_words(note)}"
    )
    criteria = (
        (
            f"- {JUDGED_BY_AGENT_LABEL}: what the owner's note above objects to no longer "
            f"happens, and `{node.id}` still does what its description says"
        ),
        (
            "- The rejected case is tried again in the next test session; the owner's acceptance "
            "of it, not this ticket's closing, is what finishes the rework"
        ),
    )
    stages = (
        (
            f"- [ ] Reproduce what the note describes against `{node.id}` and fix it; verified by "
            "the case behaving as the note asks"
        ),
        (
            "- [ ] Record the change in the node: `Node-Change: rework` on every commit that "
            f"touches `{node_file}`; verified by `agent-os-tree trailers`"
        ),
    )
    context = (
        f"Returned from test session `{session_id}` by `agent-os-sessions test-ingest`. The node "
        f"is `{node.id}` (state `{node.state}`), its file is `{node_file}`. If the note asks to "
        "decide something rather than to fix something, do not guess: record it as a question of "
        "what on the node, with a default answer, and say so on this issue "
        "(`docs/tree/uc-open-a-test-session-for-a-branch.md`)."
    )
    not_included = (
        "- Anything outside the node: its siblings and descendants have tickets of their own.",
        "- Changing the what. The note is the owner's word about this case, not a new requirement.",
    )
    done = (
        "- Every acceptance criterion passes.",
        "- Documentation as the project's AGENTS.md asks.",
    )
    sections = [
        ("## Objective", objective),
        ("## Acceptance criteria", "\n".join(criteria)),
        ("## Stages", "\n".join(stages)),
        ("## Context", context),
        ("## Not included", "\n".join(not_included)),
        ("## Dependencies", "none"),
        ("## Definition of done", "\n".join(done)),
    ]
    body = "\n\n".join(f"{heading}\n{text}" for heading, text in sections)
    markers = [
        f"<!-- budget: {budget_class} -->",
        *render_marker_lines(node.id, (), touched_paths_of(node)),
        f"<!-- key: {rework_key(session_id, node.id)} -->",
    ]
    ticket = body + "\n\n" + "\n".join(markers) + "\n"
    failures = validate_issue_body(ticket, task_classes=task_classes, open_issue_numbers=set())
    if failures:
        raise ReworkTicketError(
            f"the rework ticket for {node.id!r} is not a dispatchable issue body: "
            + "; ".join(failures)
        )
    return ticket
