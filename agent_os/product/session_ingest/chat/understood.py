"""`<tree.test_sessions_dir>/understood.json`: what Agentos understood of each ingested chat session
and where it went, for the app to show when the owner opens the next one ("lo que entendí y en qué
quedó"; `docs/tree/uc-open-a-test-session-for-a-branch.md`).

Agentos is the only writer and the app only reads; one JSON object, written whole each time:

    {"schema": 1, "sessions": [{"session": "<id>", "closed_at": "<ISO-8601>", "ingested_at": "<UTC>",
      "decisions": [<entry>], "questions": [<entry>], "changes": [<change>]}]}

    <entry>  = {"id": "item-2", "summary": "...", "node": "uc-x" | null, "page": "/p" | null,
                "from_messages": [4, 5]}      positions in the `comments` of that session's file
    <change> = {"origin": "item" | "rework" | "case change" | "general", "summary": "...",
                "node": "uc-x" | null, "issue": 123 | null}

- `decisions` are not launched: the owner confirms or corrects them in the session that opens next;
- `questions` are the interpreter's `question_of_what`: open until the owner answers;
- `changes` were launched, each with the issue that carries it.

One block per session, oldest closing first; a second ingestion of a session replaces its block, so
the file is idempotent by effect. The block is for the first session the owner opens after
`closed_at`: what the owner says about it there is a message of that session like any other. The
file is not a session, and the session reader passes it by (`session_file.UNDERSTOOD_FILE_NAME`).
"""

from __future__ import annotations

import json
import os
import pathlib

from agent_os.product.session_ingest.chat.model import Item
from agent_os.product.session_ingest.chat.plan import ChatSessionPlan
from agent_os.product.session_ingest.session_file import UNDERSTOOD_FILE_NAME

UNDERSTOOD_SCHEMA = 1


class UnderstoodFileError(ValueError):
    """The file exists and is not what this module wrote; it is never overwritten by guess."""


def _entry(item: Item) -> dict:
    return {
        "id": item.id,
        "summary": item.summary,
        "node": item.node,
        "page": item.page,
        "from_messages": list(item.from_messages),
    }


def session_block(plan: ChatSessionPlan, issues_by_key: dict[str, int], ingested_at: str) -> dict:
    return {
        "session": plan.session.id,
        "closed_at": plan.session.closed_at.isoformat(timespec="seconds"),
        "ingested_at": ingested_at,
        "decisions": [_entry(i) for i in plan.kept_for_next_session if i.kind == "decision"],
        "questions": [
            _entry(i) for i in plan.kept_for_next_session if i.kind == "question_of_what"
        ],
        "changes": [
            {
                "origin": step.origin,
                "summary": step.subject.summary,
                "node": step.subject.node_id,
                "issue": issues_by_key.get(step.subject.key),
            }
            for step in plan.issues
        ],
    }


def read_understood_file(directory: pathlib.Path) -> dict:
    return _read(directory / UNDERSTOOD_FILE_NAME)


def _read(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"schema": UNDERSTOOD_SCHEMA, "sessions": []}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UnderstoodFileError(f"{path} is not JSON ({error})") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != UNDERSTOOD_SCHEMA
        or not isinstance(document.get("sessions"), list)
    ):
        raise UnderstoodFileError(f"{path} is not an understood file of schema {UNDERSTOOD_SCHEMA}")
    return document


def write_session_block(directory: pathlib.Path, block: dict) -> pathlib.Path | None:
    """Puts the block in the file, replacing the same session's earlier one; None when the session
    left nothing to show, so that an empty block never lands in front of the owner."""
    if not (block["decisions"] or block["questions"] or block["changes"]):
        return None
    path = directory / UNDERSTOOD_FILE_NAME
    document = _read(path)
    others = [row for row in document["sessions"] if row.get("session") != block["session"]]
    document["sessions"] = sorted(
        [*others, block], key=lambda row: (str(row.get("closed_at")), str(row.get("session")))
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)
    return path
