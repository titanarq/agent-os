"""What the model answers, validated: a reply, the items it adds or corrects, and whether it asks."""

from __future__ import annotations

import dataclasses
import json
import re

from agent_os.product.interpreter.constants import ITEM_ID_PREFIX, MAX_REPLY_CHARS
from agent_os.product.interpreter.items import Item, parse_item
from agent_os.product.interpreter.request import Request

QUESTION_MARKS = ("?", "？", "¿")
FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```\s*$", re.DOTALL)


@dataclasses.dataclass(frozen=True)
class Interpretation:
    reply: str
    items: tuple[Item, ...]
    needs_answer: bool


def _next_item_number(request: Request) -> int:
    numbers = [
        int(item.id.removeprefix(ITEM_ID_PREFIX))
        for item in request.items
        if item.id.removeprefix(ITEM_ID_PREFIX).isdigit()
    ]
    return max(numbers, default=0) + 1


def parse_interpretation(text: str, request: Request) -> tuple[Interpretation | None, list[str]]:
    """`(interpretation, [])` or `(None, reasons)`. An object that is not JSON, a reply that is not
    short, a question that asks nothing, an item that points at nothing: every reason is returned so
    that the one retry can fix them all."""
    stripped = text.strip()
    fence = FENCE_RE.match(stripped)
    try:
        document = json.loads(fence.group(1) if fence else stripped)
    except ValueError as error:
        return None, [f"the answer is not one JSON object ({error})"]
    if not isinstance(document, dict):
        return None, ["the answer must be one JSON object"]
    problems: list[str] = []
    reply, needs_answer = document.get("reply"), document.get("needs_answer")
    if not isinstance(reply, str) or not reply.strip():
        problems.append("`reply` must be non-empty text")
    elif len(reply) > MAX_REPLY_CHARS:
        problems.append(f"`reply` must be short (at most {MAX_REPLY_CHARS} characters)")
    if not isinstance(needs_answer, bool):
        problems.append("`needs_answer` must be true or false")
    elif (
        needs_answer
        and isinstance(reply, str)
        and not any(mark in reply for mark in QUESTION_MARKS)
    ):
        problems.append("`needs_answer` is true but `reply` asks no question")
    raw_items = document.get("items")
    if not isinstance(raw_items, list):
        problems.append("`items` must be a list (empty when nothing is to be added)")
        raw_items = []
    known = {item.id for item in request.items}
    number, seen, items = _next_item_number(request), set(), []
    for position, raw in enumerate(raw_items):
        where = f"items[{position}]"
        given = raw.get("id") if isinstance(raw, dict) else None
        if given is not None and given not in known:
            problems.append(
                f"{where}: `id` {given!r} is not an item of this session; leave it null for a new one"
            )
            continue
        if given is not None:
            if given in seen:
                problems.append(f"{where}: `id` {given!r} appears twice")
            seen.add(given)
        item, item_problems = parse_item(
            raw,
            where=where,
            message_count=request.message_position + 1,
            id_of_new=f"{ITEM_ID_PREFIX}{number}",
        )
        problems += item_problems
        if item is not None:
            number += 1 if given is None else 0
            items.append(item)
    if problems:
        return None, problems
    return Interpretation(reply.strip(), tuple(items), needs_answer), []
