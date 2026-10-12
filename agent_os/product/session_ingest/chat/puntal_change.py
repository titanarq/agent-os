"""The issue on the mechanism's repository that an approved `puntal_change` item opens
(`docs/adr/2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`, points 2, 3 and 7).

A `puntal_change` is the owner's correction of the puntal's instructions (`prompts/puntal.md`, the node-slice
rules). It never changes a prompt: it opens ONE issue, keyed by session and item, whose task is to assess the
behaviour, reproduce it as a case of the replay battery and change the prompt only if the battery says so
(`docs/tree/dec-a-method-change-is-judged-by-evidence-from-the-products.md`). The context carries the owner's
words, the action, node, outcome and `versions` of each invocation it points at (read from the puntal's
telemetry) and the description of the case. Like any item it waits while it is `proposed` (a derived one, or
any in review mode), and with no `sessions.mechanism_repository` it is held: listed in `understood.json`, nothing opened.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

from agent_os.product.session_ingest.chat.model import ChatSession, Item
from agent_os.product.session_ingest.chat.proposals import is_awaiting_approval
from agent_os.product.session_ingest.chat.ticket import (
    TicketSubject,
    one_safe_line,
    read_from_the_same_messages,
    thread_text,
)
from agent_os.product.session_ingest.chat.verdicts import telemetry_file_beside
from agent_os.product.shared.records import read_json_lines
from agent_os.product.tree.loader import Tree

PUNTAL_CHANGE_ORIGIN = "puntal change"

TASK = (
    "Assess whether `prompts/puntal.md` (or the node-slice rules) should change for the behaviour "
    "described in the Context. Reproduce it as a case for the replay battery. Change the prompt only "
    "if the battery says so, with its evidence in the pull request: never a blind change."
)

EXCLUSIONS = (
    "Changing a goal, a requirement, a use case or an evaluator: the issue never does, the owner decides it.",
    "Changing the prompt without evidence from the battery.",
)


def puntal_change_key(session_id: str, item_id: str) -> str:
    return f"puntal-change.{session_id}.{item_id}"


def invocation_evidence(item: Item, feedback_file: pathlib.Path) -> list[dict] | str:
    """The telemetry row of each invocation the item names, or the problem that keeps the issue from opening."""
    if not item.invocations:
        return f"{item.id}: a puntal_change names the invocation it comes from, this one names none"
    rows = read_json_lines(telemetry_file_beside(feedback_file))
    evidence = []
    for invocation_id in item.invocations:
        row = next((row for row in rows if row.get("invocation_id") == invocation_id), None)
        if row is None:
            return (
                f"{item.id}: no invocation {invocation_id!r} in "
                f"{telemetry_file_beside(feedback_file)}, its puntal change cannot be opened"
            )
        evidence.append(row)
    return evidence


def _evidence_lines(rows: list[dict]) -> str:
    return "\n".join(
        f"- invocation `{row['invocation_id']}`: action `{row.get('action')}`, node `{row.get('node')}`, "
        f"outcome `{row.get('outcome')}`, versions `{json.dumps(row.get('versions'), sort_keys=True)}`"
        for row in rows
    )


@dataclass
class PuntalChangeOutcome:
    """What the plan does with one `puntal_change` item: exactly one of the four lists or the subject."""

    proposals: list[Item] = field(default_factory=list)
    held: list[Item] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    subject: TicketSubject | None = None


def decide_puntal_change(
    session: ChatSession,
    tree: Tree,
    item: Item,
    *,
    repository: str,
    feedback_file: pathlib.Path,
    confirm_before_dispatch: bool,
) -> PuntalChangeOutcome:
    if is_awaiting_approval(item, confirm_before_dispatch=confirm_before_dispatch):
        return PuntalChangeOutcome(proposals=[item])
    if not repository:
        return PuntalChangeOutcome(held=[item])
    subject = puntal_change_subject(session, tree, item, feedback_file)
    if isinstance(subject, str):
        return PuntalChangeOutcome(problems=[subject])
    return PuntalChangeOutcome(subject=subject)


def puntal_change_subject(
    session: ChatSession, tree: Tree, item: Item, feedback_file: pathlib.Path
) -> TicketSubject | str:
    """The issue's subject, or the problem that keeps it from opening."""
    evidence = invocation_evidence(item, feedback_file)
    if isinstance(evidence, str):
        return evidence
    positions = list(item.from_messages)
    case = tree.nodes.get(item.node) if item.node else None
    summary = one_safe_line(item.summary)
    case_text = f"\n\nThe case's description:\n\n{case.description}" if case else ""
    origin = (
        f"The owner said in test session `{session.id}` that the puntal's answer ignores what the case "
        "asks, and the interpreter of the feedback proposed correcting the puntal's instructions. "
        f"Summary: {summary}\n\nThe invocations it points at, from the puntal's telemetry "
        f"(the text of the answer is not recorded there):\n\n{_evidence_lines(evidence)}{case_text}"
    )
    return TicketSubject(
        key=puntal_change_key(session.id, item.id),
        title=f"Assess the puntal's instructions: {summary} (test session {session.id}, {item.id})",
        summary=summary,
        task=TASK,
        origin=origin,
        messages=thread_text(session, positions),
        node_id=None,
        is_rework=False,
        others=read_from_the_same_messages(session, positions, apart_from=item.id),
        exclusions=EXCLUSIONS,
    )
