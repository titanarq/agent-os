"""Which closed test sessions were already ingested.

`<cache>/test-sessions/ingested.jsonl`, one line per ingested session:
`{"schema": 1, "session": "<id>", "ingested_at": "<UTC ISO-8601>", "answers": 1, "accepted": 2,
"rework_issues": [41]}`.

It lives in the cache and not in git on purpose: every effect of an ingestion is idempotent by
itself (an answered question is not answered twice, an acceptance is recorded once per session, a
rework issue is found by its `<!-- key: -->` before another is opened), so the registry only spares
the plan from repeating what is done. Losing it costs a longer plan and no duplicate; keeping it in
git would make the bookkeeping itself a pull request on the tree.
"""

from __future__ import annotations

import pathlib

from agent_os.product.records import append_json_line, read_json_lines

REGISTRY_FILE = "ingested.jsonl"


def _path(cache_directory: pathlib.Path) -> pathlib.Path:
    return cache_directory / "test-sessions" / REGISTRY_FILE


def ingested_session_ids(cache_directory: pathlib.Path) -> set[str]:
    return {row["session"] for row in read_json_lines(_path(cache_directory))}


def record_ingested(
    cache_directory: pathlib.Path,
    *,
    session: str,
    ingested_at: str,
    answers: int,
    accepted: int,
    rework_issues: list[int],
) -> None:
    append_json_line(
        _path(cache_directory),
        {
            "schema": 1,
            "session": session,
            "ingested_at": ingested_at,
            "answers": answers,
            "accepted": accepted,
            "rework_issues": rework_issues,
        },
    )
