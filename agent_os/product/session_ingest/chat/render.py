"""The plan of a chat session as the lines `test-ingest` prints; nothing here decides anything."""

from __future__ import annotations

from agent_os.product.session_ingest.chat.model import Item
from agent_os.product.session_ingest.chat.plan import ChatSessionPlan
from agent_os.product.session_ingest.render import done_suffix, render_verdict_lines

_ORIGIN_WORDS = {
    "item": "change",
    "rework": "rework (needs work, nothing interpreted it)",
    "case change": "change (ok with improvements, nothing interpreted it)",
    "general": "general change (no case, nothing interpreted it)",
}


def _item_line(label: str, item: Item, ending: str) -> str:
    return f"  {label}: {item.id}: {item.summary}{ending}"


def render_chat_plan(plan: ChatSessionPlan) -> list[str]:
    session = plan.session
    lines = [f"session {session.id} (chat, closed {session.closed_at:%Y-%m-%d})"]
    for step in plan.answers:
        verb = "answered" if step.already_written else "write answer"
        lines.append(
            f"  {verb}: {step.question.node}: {step.question.question} -> {step.question.answer}"
            f"{done_suffix(step.already_written)}"
        )
    for acceptance in plan.acceptances:
        lines.append(
            f"  accepted: {acceptance.node} -> record the owner's acceptance"
            f"{done_suffix(acceptance.already_recorded)}"
        )
    for step in plan.issues:
        existing = f" (already opened as #{step.existing_issue})" if step.existing_issue else ""
        about = f" on {step.subject.node_id}" if step.subject.node_id else ""
        lines.append(
            f"  issue: {_ORIGIN_WORDS[step.origin]}{about}{existing}: {step.subject.summary}"
        )
    for item in plan.kept_for_next_session:
        if item.kind == "decision":
            ending = " -- not launched: the owner confirms it when the next session opens"
        else:
            ending = (
                " -- not launched, no question-session issue (it has no node question with a "
                "default answer): open until the owner answers it when the next session opens"
            )
        lines.append(_item_line(item.kind.replace("_", " "), item, ending))
    lines.extend(_item_line("withdrawn", item, " -- nothing") for item in plan.withdrawn)
    lines.extend(
        f"  ok with improvements: {node} -- no change named, nothing to launch"
        for node in plan.no_change_named
    )
    if plan.not_tried:
        lines.append(f"  not tried: {len(plan.not_tried)} cases -- nothing written")
    lines.extend(render_verdict_lines(plan.verdicts))
    lines.extend(f"  problem: {problem}" for problem in plan.problems)
    return lines
