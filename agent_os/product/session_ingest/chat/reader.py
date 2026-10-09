"""The reader of schema 2: every key the contract names is checked, and what is wrong is named."""

from __future__ import annotations

from agent_os.product.session_ingest.chat.model import (
    CASE_VERDICTS,
    COMMENT_STATES,
    ITEM_KINDS,
    ROLES,
    ChatCase,
    ChatSession,
    Comment,
    Item,
)
from agent_os.product.session_ingest.session_file import (
    SESSION_ID_RE,
    SessionFileError,
    moment_of,
    question_of,
    text_of,
)


def _optional_text(row: dict, key: str, where: str) -> str | None:
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        raise SessionFileError(f"{where}: `{key}` is neither null nor text")
    return value


def _one_of(value: str | None, allowed: tuple[str, ...], what: str, where: str) -> None:
    if value is not None and value not in allowed:
        raise SessionFileError(f"{where}: {what} {value!r} is not one of {', '.join(allowed)}")


def _objects(document: dict, key: str, where: str) -> list[dict]:
    rows = document.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise SessionFileError(f"{where}: `{key}` must be a list of objects")
    return rows


def _comment(row: dict, where: str) -> Comment:
    role, state = text_of(row, "role", where), _optional_text(row, "state", where)
    _one_of(role, ROLES, "role", where)
    _one_of(state, COMMENT_STATES, "state", where)
    text = row.get("text")
    if not isinstance(text, str):
        raise SessionFileError(f"{where}: a comment has no `text` (it is empty text, not null)")
    return Comment(
        role,
        text.strip(),
        state,
        _optional_text(row, "case", where),
        _optional_text(row, "page", where),
        _optional_text(row, "at", where),
    )


def _case(row: dict, where: str) -> ChatCase:
    verdict = text_of(row, "verdict", where)
    _one_of(verdict, CASE_VERDICTS, "verdict", where)
    return ChatCase(text_of(row, "node", where), str(row.get("title") or ""), verdict)


def _item(row: dict, thread_length: int, where: str) -> Item:
    kind = text_of(row, "kind", where)
    _one_of(kind, ITEM_KINDS, "item kind", where)
    positions = row.get("from_messages")
    if not isinstance(positions, list) or not all(
        isinstance(p, int) and not isinstance(p, bool) and 0 <= p < thread_length for p in positions
    ):
        raise SessionFileError(
            f"{where}: item {row.get('id')!r}: `from_messages` must be positions in the thread "
            f"(0 to {thread_length - 1})"
        )
    withdrawn = row.get("withdrawn", False)
    if not isinstance(withdrawn, bool):
        raise SessionFileError(f"{where}: item {row.get('id')!r}: `withdrawn` is not true or false")
    return Item(
        text_of(row, "id", where),
        kind,
        text_of(row, "summary", where),
        _optional_text(row, "node", where),
        _optional_text(row, "page", where),
        tuple(positions),
        withdrawn,
    )


def read_schema_2(document: dict, source: str) -> ChatSession:
    session_id = text_of(document, "id", source)
    if not SESSION_ID_RE.fullmatch(session_id):
        raise SessionFileError(f"{source}: id {session_id!r} is not lowercase words and digits")
    comments = tuple(_comment(row, source) for row in _objects(document, "comments", source))
    items = (
        tuple(_item(row, len(comments), source) for row in _objects(document, "items", source))
        if "items" in document
        else None
    )
    return ChatSession(
        id=session_id,
        opened_at=moment_of(document, "opened_at", source),
        closed_at=moment_of(document, "closed_at", source),
        cases=tuple(_case(row, source) for row in _objects(document, "cases", source)),
        comments=comments,
        questions=tuple(
            question_of(row, source) for row in _objects(document, "questions", source)
        ),
        items=items,
    )
