"""A closed test session of schema 2, read: the thread, the cases, and what the interpreter made of it."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from agent_os.product.session_ingest.session_file import Question

COMMENT_STATES = ("perfect", "ok_with_improvements", "needs_work")
CASE_VERDICTS = (*COMMENT_STATES, "not_tried")
ITEM_KINDS = ("change", "decision", "question_of_what")
ROLES = ("owner", "agent")


@dataclass(frozen=True)
class Comment:
    role: str
    text: str
    state: str | None
    case: str | None
    page: str | None
    at: str | None


@dataclass(frozen=True)
class ChatCase:
    node: str
    title: str
    verdict: str


@dataclass(frozen=True)
class Item:
    """One thing the interpreter understood. `from_messages` are positions in the whole thread."""

    id: str
    kind: str
    summary: str
    node: str | None
    page: str | None
    from_messages: tuple[int, ...]
    withdrawn: bool


@dataclass(frozen=True)
class ChatSession:
    """`items` is None when the file has no `items` key: the session was closed before the chat was
    connected to the interpreter, which is not the same as an interpreter that found nothing."""

    id: str
    opened_at: datetime.datetime
    closed_at: datetime.datetime
    cases: tuple[ChatCase, ...]
    comments: tuple[Comment, ...]
    questions: tuple[Question, ...]
    items: tuple[Item, ...] | None
