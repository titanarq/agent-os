"""What an open question of what adds to the interpreter, decided by code and never by the prompt:
the `answer` item carries the owner's own words (or the default they accepted), bound to the
question the request carried, and an `ask` turn only puts the question. See
`docs/adr/2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`."""

from __future__ import annotations

import dataclasses

from agent_os.product.interpreter.constants import KIND_ANSWER
from agent_os.product.interpreter.items import Item
from agent_os.product.interpreter.request import Request


def bind_answers(items: list[Item], request: Request) -> tuple[list[Item], list[str]]:
    """The new `answer` items with node, question and `answer_text` set by code. The model only
    says WHETHER the owner answered: an `answer_text` equal to the default means an explicit yes to
    it; anything else means the owner's message, which is stored verbatim."""
    carried = {item.id for item in request.items}
    pending = request.pending_question
    bound, problems, answers = [], [], 0
    for item in items:
        if item.kind != KIND_ANSWER or item.withdrawn or item.id in carried:
            bound.append(item)
            continue
        answers += 1
        if pending is None:
            problems.append(f"{item.id}: an `answer` needs a `pending_question` in the request")
            bound.append(item)
            continue
        accepted_default = (item.answer_text or "").strip() == pending.default_answer.strip()
        bound.append(
            dataclasses.replace(
                item,
                node=pending.node,
                question=pending.question,
                answer_text=pending.default_answer if accepted_default else request.message_text,
            )
        )
    if answers > 1:
        problems.append("one message answers the pending question once: emit ONE `answer` item")
    return bound, problems


def ask_problems(request: Request, items: list[Item], needs_answer: bool) -> list[str]:
    """An `ask` turn writes one message that waits for the owner and records nothing."""
    if request.ask is None:
        return []
    problems = []
    if items:
        problems.append("an `ask` request records nothing: `items` must be empty")
    if not needs_answer:
        problems.append("an `ask` request puts a question: `needs_answer` must be true")
    return problems
