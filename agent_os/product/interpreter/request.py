"""The request a host sends: the thread so far, the owner's new message, the case and the items."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import uuid

from agent_os.product.interpreter.constants import (
    ROLE_OWNER,
    STATUS_PROPOSED,
    THREAD_ROLES,
    InterpreterRefused,
)
from agent_os.product.interpreter.items import Item, parse_item


@dataclasses.dataclass(frozen=True)
class Message:
    role: str
    text: str
    state: str | None = None
    case: str | None = None
    page: str | None = None
    at: str | None = None


@dataclasses.dataclass(frozen=True)
class CaseContext:
    """What a node tells about itself, as the host reads it from its tree: enough for the model to
    tie a comment to what the owner was asked to try."""

    id: str
    title: str
    description: str
    verification: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Invocation:
    """One recent answer of the puntal the host carries, so that an item can name it by id."""

    invocation_id: str
    action: str
    node: str | None
    page: str | None
    at: str | None
    answer: str


@dataclasses.dataclass(frozen=True)
class OpenQuestion:
    """An open question of what with its default answer: `ask` when the interpreter is to put it,
    `pending_question` when the message may be answering it."""

    node: str
    question: str
    default_answer: str


@dataclasses.dataclass(frozen=True)
class Request:
    thread: tuple[Message, ...]
    message: Message | None
    case: CaseContext | None
    items: tuple[Item, ...]
    session_id: str
    invocation_id: str
    labels: dict[str, str]
    invocations: tuple[Invocation, ...] = ()
    pending_question: OpenQuestion | None = None
    ask: OpenQuestion | None = None

    @property
    def message_text(self) -> str:
        """What the owner typed; empty on an `ask`, which has no message."""
        return self.message.text if self.message else ""

    @property
    def message_position(self) -> int:
        """Where the new message sits in the whole thread: right after the stored ones."""
        return len(self.thread)


def _text_or_none(value: object, *, what: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InterpreterRefused(f"{what} must be text or null")
    return value


def _message(raw: object, *, where: str, require_owner: bool = False) -> Message:
    if not isinstance(raw, dict):
        raise InterpreterRefused(f"{where} must be an object")
    role = raw.get("role", ROLE_OWNER if require_owner else None)
    if role not in THREAD_ROLES or (require_owner and role != ROLE_OWNER):
        raise InterpreterRefused(
            f"{where}: `role` must be {ROLE_OWNER!r}" + ("" if require_owner else " or 'agent'")
        )
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise InterpreterRefused(f"{where}: `text` must be non-empty text")
    fields = {
        key: _text_or_none(raw.get(key), what=f"{where}: `{key}`")
        for key in ("state", "case", "page", "at")
    }
    return Message(role=role, text=text, **fields)


def case_from_object(raw: object) -> CaseContext:
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
        raise InterpreterRefused("`case` must be an object with an `id`")
    verification = raw.get("verification") or []
    if not isinstance(verification, list) or not all(isinstance(v, str) for v in verification):
        raise InterpreterRefused("`case.verification` must be a list of text lines")
    return CaseContext(
        id=raw["id"],
        title=str(raw.get("title") or raw["id"]),
        description=str(raw.get("description") or ""),
        verification=tuple(verification),
    )


def case_from_tree(case_id: str, tree_root: pathlib.Path) -> CaseContext:
    """The node the owner's message names, read from the host's tree. A case the tree does not
    have is a refusal: an interpretation tied to the wrong context is worse than none."""
    from agent_os.product.tree.loader import TreeRootError, load_tree, require_tree_root

    try:
        tree = load_tree(require_tree_root(tree_root))
    except TreeRootError as error:
        raise InterpreterRefused(f"case {case_id!r} named but {error}") from error
    node = tree.nodes.get(case_id)
    if node is None:
        raise InterpreterRefused(f"case {case_id!r} is not a node of the tree at {tree_root}")
    lines = tuple(
        f"judge: {entry.judge}"
        if entry.is_judged
        else f"command: {entry.command}" + (f" (proves: {entry.expects})" if entry.expects else "")
        for entry in node.verification
    )
    return CaseContext(node.id, node.title, node.description, lines)


def _required_text(raw: dict, key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InterpreterRefused(f"{where}: `{key}` must be non-empty text")
    return value


def invocations_from_list(raw: object) -> tuple[Invocation, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise InterpreterRefused("`invocations` must be a list")
    invocations = []
    for n, entry in enumerate(raw):
        where = f"invocations[{n}]"
        if not isinstance(entry, dict):
            raise InterpreterRefused(f"{where} must be an object")
        optional = {
            key: _text_or_none(entry.get(key), what=f"{where}: `{key}`")
            for key in ("node", "page", "at")
        }
        answer = entry.get("answer", "")
        if not isinstance(answer, str):
            raise InterpreterRefused(f"{where}: `answer` must be text")
        invocations.append(
            Invocation(
                invocation_id=_required_text(entry, "invocation_id", where),
                action=_required_text(entry, "action", where),
                answer=answer,
                **optional,
            )
        )
    if len({entry.invocation_id for entry in invocations}) != len(invocations):
        raise InterpreterRefused("`invocations` carries one invocation id twice")
    return tuple(invocations)


def open_question_from_object(raw: object, *, key: str) -> OpenQuestion | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InterpreterRefused(f"`{key}` must be an object")
    return OpenQuestion(
        node=_required_text(raw, "node", f"`{key}`"),
        question=_required_text(raw, "question", f"`{key}`"),
        default_answer=_required_text(raw, "default_answer", f"`{key}`"),
    )


def parse_request(text: str, *, tree_root: pathlib.Path) -> Request:
    try:
        document = json.loads(text)
    except ValueError as error:
        raise InterpreterRefused(f"the request is not JSON ({error})") from error
    if not isinstance(document, dict):
        raise InterpreterRefused("the request must be one JSON object")
    thread_raw = document.get("thread") or []
    if not isinstance(thread_raw, list):
        raise InterpreterRefused("`thread` must be a list")
    thread = tuple(_message(raw, where=f"thread[{n}]") for n, raw in enumerate(thread_raw))
    ask = open_question_from_object(document.get("ask"), key="ask")
    if ask is not None:
        if document.get("message") is not None:
            raise InterpreterRefused("an `ask` request carries no `message`: nobody has written")
        message = None
    else:
        message = _message(document.get("message"), where="message", require_owner=True)
    if document.get("case") is not None:
        case = case_from_object(document["case"])
    elif message and message.case:
        case = case_from_tree(message.case, tree_root)
    elif ask:
        case = case_from_tree(ask.node, tree_root)
    else:
        case = None
    items = []
    for n, raw in enumerate(document.get("items") or []):
        item, problems = parse_item(
            raw, where=f"items[{n}]", message_count=len(thread) + 1, id_of_new=None
        )
        if item is None:
            raise InterpreterRefused("; ".join(problems))
        items.append(item)
    labels = document.get("labels") or {}
    if not isinstance(labels, dict):
        raise InterpreterRefused("`labels` must be an object")
    pending = open_question_from_object(document.get("pending_question"), key="pending_question")
    if pending and ask:
        raise InterpreterRefused("`pending_question` and `ask` cannot come in the same request")
    if ask and any(item.status == STATUS_PROPOSED and not item.withdrawn for item in items):
        raise InterpreterRefused(
            "an `ask` request while a proposal waits: no open question is asked"
        )
    return Request(
        invocations=invocations_from_list(document.get("invocations")),
        pending_question=pending,
        ask=ask,
        thread=thread,
        message=message,
        case=case,
        items=tuple(items),
        session_id=str(document.get("session_id") or ""),
        invocation_id=str(document.get("invocation_id") or uuid.uuid4()),
        labels={str(key): str(value) for key, value in labels.items()},
    )
