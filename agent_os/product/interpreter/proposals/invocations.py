"""The invocations of the puntal a request carries: how the brief lists them and how code checks
that an item names only ones it carried. See
`docs/adr/2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`."""

from __future__ import annotations

from agent_os.product.interpreter.constants import (
    KIND_PUNTAL_CHANGE,
    MAX_INVOCATION_ANSWER_CHARS,
)
from agent_os.product.interpreter.items import Item
from agent_os.product.interpreter.request import Invocation, Request


def _cut(answer: str) -> str:
    flattened = " ".join(answer.split())
    if len(flattened) <= MAX_INVOCATION_ANSWER_CHARS:
        return flattened
    return flattened[:MAX_INVOCATION_ANSWER_CHARS].rstrip() + "..."


def _described(invocation: Invocation) -> str:
    where = f" on page {invocation.page}" if invocation.page else ""
    when = f" at {invocation.at}" if invocation.at else ""
    case = f" (case {invocation.node})" if invocation.node else ""
    return (
        f"- {invocation.invocation_id}: the answer to «{invocation.action}»{where}{when}{case}: "
        f"{_cut(invocation.answer) or '(empty answer)'}"
    )


def invocations_section(request: Request) -> str:
    lines = [_described(invocation) for invocation in request.invocations]
    return (
        "# Recent answers of the puntal (an item's `invocations` names ids from this list only)\n"
        + ("\n".join(lines) or "(none carried: no item may name an invocation)")
    )


def invocation_problems(items: list[Item], request: Request) -> list[str]:
    """Reasons for the one retry: an item that points at an answer the request did not carry, and a
    `puntal_change` that points at none. An item the session already holds keeps the ids it had."""
    carried = {invocation.invocation_id for invocation in request.invocations}
    standing = {item.id: item for item in request.items}
    problems = []
    for item in items:
        if item.withdrawn:
            continue
        allowed = carried | set(standing[item.id].invocations if item.id in standing else ())
        for invocation_id in item.invocations:
            if invocation_id not in allowed:
                problems.append(
                    f"{item.id}: `invocations` names {invocation_id!r}, which the request did not "
                    "carry: use an id of the recent answers listed in the brief"
                )
        if item.kind == KIND_PUNTAL_CHANGE and not item.invocations:
            problems.append(
                f"{item.id}: a puntal_change names the answer it comes from in `invocations`"
            )
    return problems
