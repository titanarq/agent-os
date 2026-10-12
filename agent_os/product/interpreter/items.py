"""One interpreted item: the unit the owner's feedback is split into, as the host stores it."""

from __future__ import annotations

import dataclasses

from agent_os.product.interpreter.constants import (
    ITEM_EFFECTS,
    ITEM_KINDS,
    ITEM_ORIGINS,
    ITEM_STATUSES,
    KIND_ANSWER,
    KIND_VERDICT,
    VERDICTS,
)


@dataclasses.dataclass(frozen=True)
class Item:
    """`id` is the interpreter's (`item-N`, assigned by code, never by the model); the host stores
    the item in the session file's `items[]` and replaces one whose id it already holds."""

    id: str
    kind: str
    summary: str
    node: str | None
    page: str | None
    from_messages: tuple[int, ...]
    withdrawn: bool = False
    status: str | None = None
    origin: str | None = None
    invocations: tuple[str, ...] = ()
    verdict: str | None = None
    note: str | None = None
    question: str | None = None
    answer_text: str | None = None
    effect: str | None = None

    def as_json(self) -> dict:
        document = {
            **dataclasses.asdict(self),
            "from_messages": list(self.from_messages),
            "invocations": list(self.invocations),
        }
        for optional in (
            "status",
            "origin",
            "verdict",
            "note",
            "question",
            "answer_text",
            "effect",
        ):
            if document[optional] is None:
                del document[optional]
        if not self.invocations:
            del document["invocations"]
        return document


def _optional_text(raw: dict, key: str, problems: list[str], where: str) -> str | None:
    value = raw.get(key)
    if value is None or (isinstance(value, str) and value.strip()):
        return value.strip() if value else None
    problems.append(f"{where}: `{key}` must be text or null")
    return None


def _invocation_ids(raw: dict, problems: list[str], where: str) -> tuple[str, ...]:
    ids = raw.get("invocations", [])
    if not isinstance(ids, list) or not all(isinstance(i, str) and i.strip() for i in ids):
        problems.append(f"{where}: `invocations` must be a list of invocation ids")
        return ()
    return tuple(dict.fromkeys(i.strip() for i in ids))


def _kind_specific_problems(
    kind: object, fields: dict[str, object], invocations: tuple[str, ...], where: str
) -> list[str]:
    """What a `verdict` and an `answer` need to mean anything: the verdict is on ONE invocation,
    the answer is to a named question of a node."""
    problems: list[str] = []
    if kind == KIND_VERDICT:
        if fields["verdict"] not in VERDICTS:
            problems.append(f"{where}: `verdict` must be one of {list(VERDICTS)}")
        if len(invocations) != 1:
            problems.append(f"{where}: a verdict names exactly one id in `invocations`")
    if kind == KIND_ANSWER:
        for key in ("node", "question", "answer_text"):
            if not fields[key]:
                problems.append(f"{where}: an answer needs `{key}`")
    return problems


def parse_item(
    raw: object,
    *,
    where: str,
    message_count: int,
    id_of_new: str | None,
    require_origin: bool = False,
) -> tuple[Item | None, list[str]]:
    """An item from a JSON object. `id_of_new` is the id given when the object carries none.
    `message_count` bounds `from_messages`, which are positions in the whole thread. The model's
    own items need an `origin` unless they are withdrawn; the ones a host stored earlier may have
    none (`require_origin` is false for them)."""
    if not isinstance(raw, dict):
        return None, [f"{where}: must be an object"]
    problems: list[str] = []
    kind, summary = raw.get("kind"), raw.get("summary")
    if kind not in ITEM_KINDS:
        problems.append(f"{where}: `kind` must be one of {list(ITEM_KINDS)}")
    if not isinstance(summary, str) or not summary.strip():
        problems.append(f"{where}: `summary` must be non-empty text")
    node = _optional_text(raw, "node", problems, where)
    page = _optional_text(raw, "page", problems, where)
    sources = raw.get("from_messages")
    valid_sources = (
        isinstance(sources, list)
        and bool(sources)
        and all(
            isinstance(position, int)
            and not isinstance(position, bool)
            and 0 <= position < message_count
            for position in sources
        )
    )
    if not valid_sources:
        problems.append(
            f"{where}: `from_messages` must list at least one message position in "
            f"0..{message_count - 1}"
        )
    withdrawn = raw.get("withdrawn", False)
    if not isinstance(withdrawn, bool):
        problems.append(f"{where}: `withdrawn` must be true or false")
    status = raw.get("status")
    if status is not None and status not in ITEM_STATUSES:
        problems.append(f"{where}: `status` must be one of {list(ITEM_STATUSES)} when present")
    origin = raw.get("origin")
    if origin is None and require_origin and withdrawn is not True:
        problems.append(f"{where}: `origin` is required, one of {list(ITEM_ORIGINS)}")
    elif origin is not None and origin not in ITEM_ORIGINS:
        problems.append(f"{where}: `origin` must be one of {list(ITEM_ORIGINS)}")
    effect = raw.get("effect")
    if effect is not None and effect not in ITEM_EFFECTS:
        problems.append(f"{where}: `effect` must be one of {list(ITEM_EFFECTS)} when present")
    invocations = _invocation_ids(raw, problems, where)
    verdict = _optional_text(raw, "verdict", problems, where)
    note = _optional_text(raw, "note", problems, where)
    question = _optional_text(raw, "question", problems, where)
    answer_text = _optional_text(raw, "answer_text", problems, where)
    fields = {"verdict": verdict, "node": node, "question": question, "answer_text": answer_text}
    problems.extend(_kind_specific_problems(kind, fields, invocations, where))
    item_id = raw.get("id") or id_of_new
    if problems or not isinstance(item_id, str):
        return None, problems
    return Item(
        id=item_id,
        kind=kind,
        summary=summary.strip(),
        node=node,
        page=page,
        from_messages=tuple(sorted(set(sources))),
        withdrawn=withdrawn,
        status=status,
        origin=origin,
        invocations=invocations,
        verdict=verdict,
        note=note,
        question=question,
        answer_text=answer_text,
        effect=effect,
    ), []
