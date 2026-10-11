"""The first message of the interpreter's one turn: everything it may use, numbered."""

from __future__ import annotations

import json

from agent_os.product.interpreter.proposals.confirmation import Confirmation
from agent_os.product.interpreter.proposals.invocations import invocations_section
from agent_os.product.interpreter.request import CaseContext, Request

RETRY_HEADING = "# Your previous answer was rejected"


def _case_section(case: CaseContext | None) -> str:
    if case is None:
        return "# Case\n(none: the owner's message is not about one use case)"
    verification = "\n".join(f"- {line}" for line in case.verification) or "(none declared)"
    return (
        f"# Case\nid: {case.id}\ntitle: {case.title}\n\n{case.description.strip()}\n\n"
        f"How it is verified:\n{verification}"
    )


def _thread_section(request: Request, max_messages: int) -> str:
    first = max(0, len(request.thread) - max_messages)
    lines = [
        f"[{position}] {message.role}"
        + "".join(
            f" {label}={value}"
            for label, value in (
                ("case", message.case),
                ("page", message.page),
                ("state", message.state),
            )
            if value
        )
        + f": {message.text}"
        for position, message in enumerate(request.thread[first:], start=first)
    ]
    omitted = f"({first} earlier message(s) omitted)\n" if first else ""
    return "# Thread so far (position in brackets)\n" + omitted + ("\n".join(lines) or "(empty)")


def _use_cases_section(confirmation: Confirmation) -> str:
    lines = [f"- {node_id}: {title}" for node_id, title in confirmation.listed]
    if confirmation.omitted:
        lines.append(f"({confirmation.omitted} more use case(s) not listed)")
    return "# Use cases of the tree (an item's `node` is the case or one of these)\n" + (
        "\n".join(lines) or "(none)"
    )


def _open_question_section(request: Request) -> str:
    ask, pending = request.ask, request.pending_question
    if ask is not None:
        return (
            "# Put this open question to the owner (nobody has written: this is YOUR message)\n"
            f"case: {ask.node}\nquestion: {ask.question}\ndefault answer: {ask.default_answer}"
        )
    if pending is not None:
        return (
            "# Your last message put this open question (the new message may answer it)\n"
            f"case: {pending.node}\nquestion: {pending.question}\n"
            f"default answer: {pending.default_answer}"
        )
    return ""


def build_brief(
    request: Request,
    *,
    max_thread_messages: int,
    rejection: list[str] | None,
    confirmation: Confirmation | None = None,
) -> str:
    message = request.message
    items = [item.as_json() for item in request.items]
    sections = [
        _case_section(request.case),
        _thread_section(request, max_thread_messages),
        invocations_section(request),
        "# Items already interpreted in this session\n"
        + (json.dumps(items, ensure_ascii=False, indent=1) if items else "(none)"),
    ]
    if message is not None:
        attributes = "".join(
            f" {label}={value}"
            for label, value in (
                ("case", message.case),
                ("page", message.page),
                ("state", message.state),
            )
            if value
        )
        sections.append(
            f"# The owner's new message (position {request.message_position}{attributes})\n"
            f"{message.text}"
        )
    open_question = _open_question_section(request)
    if open_question:
        sections.append(open_question)
    if confirmation is not None:
        sections.insert(2, _use_cases_section(confirmation))
    if rejection:
        reasons = "\n".join(f"- {reason}" for reason in rejection)
        sections.append(
            f"{RETRY_HEADING}\nNothing was kept. Send the corrected JSON object:\n{reasons}"
        )
    return "\n\n".join(sections) + "\n"
