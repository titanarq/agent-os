"""One interpreted item: the unit the owner's feedback is split into, as the host stores it."""

from __future__ import annotations

import dataclasses

from agent_os.product.interpreter.constants import ITEM_KINDS


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

    def as_json(self) -> dict:
        return {**dataclasses.asdict(self), "from_messages": list(self.from_messages)}


def _optional_text(raw: dict, key: str, problems: list[str], where: str) -> str | None:
    value = raw.get(key)
    if value is None or (isinstance(value, str) and value.strip()):
        return value.strip() if value else None
    problems.append(f"{where}: `{key}` must be text or null")
    return None


def parse_item(
    raw: object, *, where: str, message_count: int, id_of_new: str | None
) -> tuple[Item | None, list[str]]:
    """An item from a JSON object. `id_of_new` is the id given when the object carries none.
    `message_count` bounds `from_messages`, which are positions in the whole thread."""
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
    ), []
