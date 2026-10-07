"""The shape of what a puntal returns in its one model turn, and its validation.

The puntal PLANS and code executes (`docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`):
the response is one JSON object, the PLAN,

    {"operations": [<operation> ...], "answer": <what the app is told>, "gap": "<optional note>"}

or, when the action needs state its node did not declare, `{"needs_state": "<what and why>"}` (the
slow path). Four operations exist, the whole vocabulary an app's executor has to understand:

    {"op": "put",      "collection": C, "id": I, "document": {...}}   create or replace
    {"op": "update",   "collection": C, "id": I, "changes": {...}}    merge fields into a document
    {"op": "delete",   "collection": C, "id": I}
    {"op": "allocate", "counter": K, "bind": NAME}                    the next number of a counter

A string anywhere in an operation or in the answer may carry `{{NAME}}`, the value an EARLIER
`allocate` bound to NAME: the puntal cannot know a new id, only the app can, so it names it and the
executor fills it in. This module only defines and checks the shape; applying it is the app's code
(`executor.py` states the interface, `reference_executor.py` is one implementation).
"""

from __future__ import annotations

import dataclasses
import json
import re

from agent_os.product.puntal.stream.audit import split_gap_note

MAX_OPERATIONS = 50
OPERATION_FIELDS = {
    "put": ("collection", "id", "document"),
    "update": ("collection", "id", "changes"),
    "delete": ("collection", "id"),
    "allocate": ("counter", "bind"),
}
PLAN_KEYS = frozenset({"operations", "answer", "gap", "needs_state"})
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
BINDING_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FENCE = re.compile(r"^```[A-Za-z]*\s*\n(.*)\n```\s*$", re.DOTALL)


@dataclasses.dataclass(frozen=True)
class Plan:
    """A parsed response. Parsed is not valid: `validate_plan` says whether it is."""

    raw: dict
    operations: object
    answer: object
    gap: object
    needs_state: object

    @property
    def asks_for_state(self) -> bool:
        return "needs_state" in self.raw


def parse_plan(text: str) -> tuple[Plan | None, list[str]]:
    """`(plan, [])`, or `(None, errors)` when the response is not a JSON object at all. A markdown
    fence around the object and a trailing `GAP:` line are tolerated: they cost nothing to accept
    and a retry costs a model turn."""
    body, gap_line = split_gap_note(text)
    fenced = FENCE.match(body.strip())
    candidate = fenced.group(1) if fenced else body
    try:
        value = json.loads(candidate)
    except ValueError as error:
        return None, [f"the response is not a JSON object ({error})"]
    if not isinstance(value, dict):
        return None, ["the response is not a JSON object"]
    if gap_line and "gap" not in value:
        value = {**value, "gap": gap_line}
    return (
        Plan(
            raw=value,
            operations=value.get("operations"),
            answer=value.get("answer"),
            gap=value.get("gap"),
            needs_state=value.get("needs_state"),
        ),
        [],
    )


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings_of(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings_of(item)


def _names_used(value: object) -> list[str]:
    return [name for text in _strings_of(value) for name in PLACEHOLDER.findall(text)]


def _operation_errors(position: int, operation: object, bound: set[str]) -> list[str]:
    label = f"operation {position}"
    if not isinstance(operation, dict):
        return [f"{label} is not an object"]
    kind = operation.get("op")
    if kind not in OPERATION_FIELDS:
        return [f"{label}: op {kind!r} is not one of {', '.join(sorted(OPERATION_FIELDS))}"]
    errors = []
    expected = ("op", *OPERATION_FIELDS[kind])
    for key in operation:
        if key not in expected:
            errors.append(f"{label} ({kind}): unknown field {key!r}")
    for key in OPERATION_FIELDS[kind]:
        value = operation.get(key)
        if key in ("document", "changes"):
            if not isinstance(value, dict) or (key == "changes" and not value):
                errors.append(f"{label} ({kind}): {key} must be a non-empty JSON object")
        elif key == "bind":
            if not isinstance(value, str) or not BINDING_NAME.match(value):
                errors.append(f"{label} (allocate): bind must be a name (letters, digits, _)")
            elif value in bound:
                errors.append(f"{label} (allocate): {value!r} is already bound")
        elif not _is_name(value):
            errors.append(f"{label} ({kind}): {key} must be a non-empty string")
    for name in _names_used(operation):
        if name not in bound:
            errors.append(f"{label} uses {{{{{name}}}}}, which no earlier allocate binds")
    return errors


def validate_plan(plan: Plan) -> list[str]:
    """Every reason the plan cannot be executed, in words the puntal can act on in its retry turn.
    Empty means executable."""
    raw = plan.raw
    errors = [f"unknown key {key!r}" for key in raw if key not in PLAN_KEYS]
    if plan.gap is not None and not isinstance(plan.gap, str):
        errors.append("gap must be a string")
    if plan.asks_for_state:
        if not _is_name(plan.needs_state):
            errors.append("needs_state must say, in a sentence, what state is needed and why")
        if raw.get("operations"):
            errors.append("needs_state stands alone: send no operations with it")
        return errors
    if not isinstance(plan.operations, list):
        errors.append("operations must be a list (empty when the action changes nothing)")
        operations: list = []
    else:
        operations = plan.operations
    if "answer" not in raw:
        errors.append("answer is missing: it is what the app is told")
    if len(operations) > MAX_OPERATIONS:
        errors.append(f"at most {MAX_OPERATIONS} operations per plan, not {len(operations)}")
        return errors
    bound: set[str] = set()
    for position, operation in enumerate(operations, start=1):
        errors += _operation_errors(position, operation, bound)
        if (
            isinstance(operation, dict)
            and operation.get("op") == "allocate"
            and isinstance(operation.get("bind"), str)
        ):
            bound.add(operation["bind"])
    for name in _names_used(plan.answer):
        if name not in bound:
            errors.append(f"the answer uses {{{{{name}}}}}, which no allocate binds")
    return errors


def fill_bindings(value: object, bindings: dict) -> object:
    """`value` with every `{{name}}` of its strings replaced by the binding's value. A name nobody
    bound is a KeyError: an answer with a hole in it is worse than no answer."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in bindings:
            raise KeyError(f"no binding named {name!r}")
        return str(bindings[name])

    if isinstance(value, str):
        return PLACEHOLDER.sub(replace, value)
    if isinstance(value, dict):
        return {key: fill_bindings(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [fill_bindings(item, bindings) for item in value]
    return value


def render_answer(answer: object) -> str:
    """What the app receives: text as it is, anything else as compact JSON."""
    if isinstance(answer, str):
        return answer
    return json.dumps(answer, ensure_ascii=False, separators=(",", ":"))
