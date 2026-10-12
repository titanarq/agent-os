"""When a use case has to be consolidated into one definition, and the job that asks for it
(`docs/adr/2026-10-12-a-use-case-that-an-amendment-contradicts-is-consolidated-into-one-definition.md`, point 1).

The amendment of a use case is the `decision` items of a chat session that are about it. The
interpreter writes the `effect` of each one on what the case already says:

- `adds` (or no effect at all, as in a file from before): the amendment only adds, nothing is raised;
- `contradicts` or `qualifies`: the case stops reading as one definition, so it is consolidated.

The consolidation is raised once the LAST decision of the amendment is settled: while any decision
on the same use case still waits for the owner's confirmation (it is `proposed`), nothing is raised.
A withdrawn decision is not part of the amendment. The job is one issue per use case, keyed
`consolidate.<node>`, and a job still open for the case is reused, never doubled. The consolidator
that does the work (Sonnet drafts, Opus reviews) is `agent-os-consolidate`; this one only raises the job.
"""

from __future__ import annotations

from agent_os.product.interpreter.constants import (
    EFFECT_CONTRADICTS,
    EFFECT_QUALIFIES,
    KIND_DECISION,
)
from agent_os.product.session_ingest.chat.model import ChatSession, Item
from agent_os.product.session_ingest.chat.proposals import is_awaiting_approval
from agent_os.product.session_ingest.chat.ticket import TicketSubject, one_safe_line, thread_text
from agent_os.product.tree.loader import Tree

CONSOLIDATION_ORIGIN = "consolidation"
USE_CASE_TYPE = "use-case"
EFFECTS_THAT_TRIGGER = (EFFECT_CONTRADICTS, EFFECT_QUALIFIES)

TASK = (
    "Consolidate the use case named below into ONE definition that reads as true today, with the "
    "decisions of the Context applied. Delete the lines they withdraw, keep the section "
    "`Probado y descartado` last and pruned, and propose in the same pull request the tests the new "
    "definition makes obsolete, each with the line of the old definition that justified it."
)

EXCLUSIONS = (
    "Adding a test: a consolidation never adds tests.",
    "Changing a goal, another use case or an evaluator: only this use case and its dependencies.",
)


def consolidation_key(node_id: str) -> str:
    return f"consolidate.{node_id}"


def consolidation_subjects(session: ChatSession, tree: Tree) -> list[TicketSubject]:
    """One subject for each use case this session's decisions contradict or qualify, whose
    decisions are all settled."""
    decisions_by_node: dict[str, list[Item]] = {}
    for item in session.items or ():
        if item.kind == KIND_DECISION and not item.withdrawn and item.node in tree.nodes:
            decisions_by_node.setdefault(item.node, []).append(item)
    subjects = []
    for node_id, decisions in decisions_by_node.items():
        if tree.nodes[node_id].type != USE_CASE_TYPE:
            continue
        if any(is_awaiting_approval(item, confirm_before_dispatch=False) for item in decisions):
            continue
        triggering = [item for item in decisions if item.effect in EFFECTS_THAT_TRIGGER]
        if triggering:
            subjects.append(_subject(session, node_id, decisions, triggering))
    return subjects


def _subject(
    session: ChatSession, node_id: str, decisions: list[Item], triggering: list[Item]
) -> TicketSubject:
    positions = sorted({position for item in decisions for position in item.from_messages})
    decision_lines = "\n".join(
        f"- `{item.id}` ({item.effect or 'adds'}): {one_safe_line(item.summary)}"
        for item in decisions
    )
    return TicketSubject(
        key=consolidation_key(node_id),
        title=f"Consolidate use case {node_id} after the amendment of test session {session.id}",
        summary=f"Consolidate {node_id}",
        task=TASK,
        origin=(
            f"The owner amended `{node_id}` in test session `{session.id}` with "
            f"{len(triggering)} decision(s) that contradict or qualify what it says, and every "
            f"decision of the amendment is settled. The decisions, as the interpreter read them:\n\n"
            f"{decision_lines}"
        ),
        messages=thread_text(session, positions),
        node_id=node_id,
        is_rework=False,
        is_consolidation=True,
        exclusions=EXCLUSIONS,
    )
