"""The request a host sends: the thread so far, the owner's new message, the case and the items."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import uuid

from agent_os.product.interpreter.constants import ROLE_OWNER, THREAD_ROLES, InterpreterRefused
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
class Request:
    thread: tuple[Message, ...]
    message: Message
    case: CaseContext | None
    items: tuple[Item, ...]
    session_id: str
    invocation_id: str
    labels: dict[str, str]

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
    message = _message(document.get("message"), where="message", require_owner=True)
    if document.get("case") is not None:
        case = case_from_object(document["case"])
    elif message.case:
        case = case_from_tree(message.case, tree_root)
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
    return Request(
        thread=thread,
        message=message,
        case=case,
        items=tuple(items),
        session_id=str(document.get("session_id") or ""),
        invocation_id=str(document.get("invocation_id") or uuid.uuid4()),
        labels={str(key): str(value) for key, value in labels.items()},
    )
