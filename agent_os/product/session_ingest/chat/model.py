"""A test session of schema 2, read: the thread, the cases, and what the interpreter made of it."""

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
    """`items` is None when the file has no `items` key: the chat was not connected to the interpreter,
    which is not the same as an interpreter that found nothing. `closed_at` is None while the session
    is open: the app has no button that closes it, so ingestion reads it as the owner goes on."""

    id: str
    opened_at: datetime.datetime
    closed_at: datetime.datetime | None
    cases: tuple[ChatCase, ...]
    comments: tuple[Comment, ...]
    questions: tuple[Question, ...]
    items: tuple[Item, ...] | None

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def acceptance_date(self) -> datetime.date:
        """The day the owner's `perfect` counts as given: the day the session ended, or opened while
        it has not ended (a session that lasts past midnight is accepted on the day it began)."""
        return (self.closed_at or self.opened_at).date()
