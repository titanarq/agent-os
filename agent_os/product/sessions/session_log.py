"""The sessions already opened, so that the next digest starts where the last one ended.

`.cache/sessions/sessions.jsonl`, one line per session:
`{"schema": 1, "issue": 123, "opened_at": "<UTC ISO-8601>", "questions": 4, "digest_entries": 2}`.
"""

from __future__ import annotations

import pathlib

from agent_os.product.records import append_json_line, read_json_lines

SESSIONS_FILE = "sessions.jsonl"


def _path(cache_directory: pathlib.Path) -> pathlib.Path:
    return cache_directory / "sessions" / SESSIONS_FILE


def record_session(
    cache_directory: pathlib.Path,
    *,
    issue: int,
    opened_at: str,
    questions: int,
    digest_entries: int,
) -> None:
    append_json_line(
        _path(cache_directory),
        {
            "schema": 1,
            "issue": issue,
            "opened_at": opened_at,
            "questions": questions,
            "digest_entries": digest_entries,
        },
    )


def last_session_opened_at(cache_directory: pathlib.Path) -> str | None:
    sessions = read_json_lines(_path(cache_directory))
    return sessions[-1]["opened_at"] if sessions else None
