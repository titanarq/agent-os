"""A test session file, as the app writes it when the owner closes the session.

`<tree.test_sessions_dir>/<id>.json`; the keys are the contract of `docs/AGENT_OS.md` §4.11. A file
that does not have them is reported by name and skipped, never guessed at: ingesting a half-read
verdict into the owner's tree would be worse than ingesting nothing.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

VERDICTS = ("accept", "reject", "not_tried")
# What Agentos writes into the sessions directory for the app to read (`chat.understood`); it is not
# a session and the reader passes it by.
UNDERSTOOD_FILE_NAME = "understood.json"
# What a `<!-- key: -->` marker and a branch name can carry; the app's ids (`ts-20261009-172808-b2cf80`)
# are inside it.
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


class SessionFileError(ValueError):
    """One session file that cannot be read as the contract says; the message names it."""


@dataclass(frozen=True)
class Case:
    node: str
    title: str
    verdict: str
    note: str


@dataclass(frozen=True)
class Question:
    node: str
    question: str
    default_answer: str
    answer: str | None


@dataclass(frozen=True)
class ClosedSession:
    id: str
    branch: str
    opened_at: datetime.datetime
    closed_at: datetime.datetime
    cases: tuple[Case, ...]
    questions: tuple[Question, ...]


if TYPE_CHECKING:
    from agent_os.product.session_ingest.chat.model import ChatSession

    AnyClosedSession = ClosedSession | ChatSession


def text_of(document: dict, key: str, where: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise SessionFileError(f"{where}: `{key}` is missing or not text")
    return value


def moment_of(document: dict, key: str, where: str) -> datetime.datetime:
    try:
        moment = datetime.datetime.fromisoformat(text_of(document, key, where))
    except ValueError as error:
        raise SessionFileError(f"{where}: `{key}` is not an ISO-8601 moment") from error
    if moment.tzinfo is None:
        raise SessionFileError(
            f"{where}: `{key}` has no UTC offset, so it cannot be placed in time"
        )
    return moment


def _case(row, where: str) -> Case:
    if not isinstance(row, dict):
        raise SessionFileError(f"{where}: a case is not an object")
    verdict = text_of(row, "verdict", where)
    if verdict not in VERDICTS:
        raise SessionFileError(f"{where}: verdict {verdict!r} is not one of {', '.join(VERDICTS)}")
    return Case(
        text_of(row, "node", where),
        text_of(row, "title", where),
        verdict,
        str(row.get("note") or "").strip(),
    )


def question_of(row, where: str) -> Question:
    if not isinstance(row, dict):
        raise SessionFileError(f"{where}: a question is not an object")
    answer = row.get("answer")
    if answer is not None and not isinstance(answer, str):
        raise SessionFileError(f"{where}: `answer` is neither null nor text")
    return Question(
        text_of(row, "node", where),
        text_of(row, "question", where),
        text_of(row, "default_answer", where),
        answer.strip() if answer and answer.strip() else None,
    )


def _read_schema_1(document: dict, source: str) -> ClosedSession:
    session_id = text_of(document, "id", source)
    if not SESSION_ID_RE.fullmatch(session_id):
        raise SessionFileError(f"{source}: id {session_id!r} is not lowercase words and digits")
    cases, questions = document.get("cases"), document.get("questions")
    if not isinstance(cases, list) or not isinstance(questions, list):
        raise SessionFileError(f"{source}: `cases` and `questions` must be lists")
    return ClosedSession(
        id=session_id,
        branch=text_of(document, "branch", source),
        opened_at=moment_of(document, "opened_at", source),
        closed_at=moment_of(document, "closed_at", source),
        cases=tuple(_case(row, source) for row in cases),
        questions=tuple(question_of(row, source) for row in questions),
    )


def schema_readers() -> dict:
    """One reader per `schema` the app can write. A file with no `schema` key is schema 1: the key did
    not exist when that contract was fixed. A newer schema is added here, with its reader, and an older
    reader never guesses at what it does not know. The schema 2 reader is imported here and not at the
    top because it builds on this module's field readers."""
    from agent_os.product.session_ingest.chat.reader import read_schema_2

    return {1: _read_schema_1, 2: read_schema_2}


def parse_closed_session(document, source: str) -> AnyClosedSession | None:
    """The session, or None when it is still open: an open session is the owner's work in progress
    and is read by nobody, whatever its schema. A closed one that breaks the contract, or is written
    in a schema this version does not read, raises `SessionFileError`."""
    if not isinstance(document, dict):
        raise SessionFileError(f"{source}: not a JSON object")
    status = text_of(document, "status", source)
    if status == "open":
        return None
    if status != "closed":
        raise SessionFileError(f"{source}: status {status!r} is neither open nor closed")
    schema = document.get("schema", 1)
    readers = schema_readers()
    reader = readers.get(schema) if isinstance(schema, int) else None
    if reader is None:
        known = ", ".join(str(known_schema) for known_schema in readers)
        raise SessionFileError(
            f"{source}: schema {schema!r} is not read by this version (it reads: {known}); "
            "the session stays pending until a version that reads it ingests it"
        )
    return reader(document, source)


def read_closed_sessions(
    directory: pathlib.Path,
) -> tuple[list[AnyClosedSession], list[str]]:
    """Every closed session of the directory, oldest closing first, and one line per file that could
    not be read. A directory that does not exist is an error, not an empty answer: the key that
    names it is wrong, or the product never wrote a session, and either is for the owner to know."""
    if not directory.is_dir():
        raise SessionFileError(f"no test sessions directory at {directory}")
    sessions: list[AnyClosedSession] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
        if path.name == UNDERSTOOD_FILE_NAME:
            continue
        try:
            session = parse_closed_session(json.loads(path.read_text(encoding="utf-8")), path.name)
        except json.JSONDecodeError as error:
            problems.append(f"{path.name}: not JSON ({error})")
        except SessionFileError as error:
            problems.append(str(error))
        else:
            if session is not None:
                sessions.append(session)
    sessions.sort(key=lambda session: (session.closed_at, session.id))
    return sessions, problems
