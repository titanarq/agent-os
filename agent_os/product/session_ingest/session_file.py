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

VERDICTS = ("accept", "reject", "not_tried")
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


def _text(document: dict, key: str, where: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise SessionFileError(f"{where}: `{key}` is missing or not text")
    return value


def _moment(document: dict, key: str, where: str) -> datetime.datetime:
    try:
        moment = datetime.datetime.fromisoformat(_text(document, key, where))
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
    verdict = _text(row, "verdict", where)
    if verdict not in VERDICTS:
        raise SessionFileError(f"{where}: verdict {verdict!r} is not one of {', '.join(VERDICTS)}")
    return Case(
        _text(row, "node", where),
        _text(row, "title", where),
        verdict,
        str(row.get("note") or "").strip(),
    )


def _question(row, where: str) -> Question:
    if not isinstance(row, dict):
        raise SessionFileError(f"{where}: a question is not an object")
    answer = row.get("answer")
    if answer is not None and not isinstance(answer, str):
        raise SessionFileError(f"{where}: `answer` is neither null nor text")
    return Question(
        _text(row, "node", where),
        _text(row, "question", where),
        _text(row, "default_answer", where),
        answer.strip() if answer and answer.strip() else None,
    )


def parse_closed_session(document, source: str) -> ClosedSession | None:
    """The session, or None when it is still open: an open session is the owner's work in progress
    and is read by nobody. A closed one that breaks the contract raises `SessionFileError`."""
    if not isinstance(document, dict):
        raise SessionFileError(f"{source}: not a JSON object")
    status = _text(document, "status", source)
    if status == "open":
        return None
    if status != "closed":
        raise SessionFileError(f"{source}: status {status!r} is neither open nor closed")
    session_id = _text(document, "id", source)
    if not SESSION_ID_RE.fullmatch(session_id):
        raise SessionFileError(f"{source}: id {session_id!r} is not lowercase words and digits")
    cases, questions = document.get("cases"), document.get("questions")
    if not isinstance(cases, list) or not isinstance(questions, list):
        raise SessionFileError(f"{source}: `cases` and `questions` must be lists")
    return ClosedSession(
        id=session_id,
        branch=_text(document, "branch", source),
        opened_at=_moment(document, "opened_at", source),
        closed_at=_moment(document, "closed_at", source),
        cases=tuple(_case(row, source) for row in cases),
        questions=tuple(_question(row, source) for row in questions),
    )


def read_closed_sessions(
    directory: pathlib.Path,
) -> tuple[list[ClosedSession], list[str]]:
    """Every closed session of the directory, oldest closing first, and one line per file that could
    not be read. A directory that does not exist is an error, not an empty answer: the key that
    names it is wrong, or the product never wrote a session, and either is for the owner to know."""
    if not directory.is_dir():
        raise SessionFileError(f"no test sessions directory at {directory}")
    sessions: list[ClosedSession] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
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
