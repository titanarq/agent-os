"""The append-only JSON-lines files the recording conventions name (`telemetry.jsonl`,
`feedback.jsonl`, `judgments.jsonl`)."""

from __future__ import annotations

import fcntl
import json
import pathlib


def append_json_line(path: pathlib.Path, record: dict) -> None:
    """One line, appended under an exclusive lock: invocations run in parallel (that is the point of
    a puntal) and two records must never interleave."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(line)
        handle.flush()


def read_json_lines(path: pathlib.Path) -> list[dict]:
    """Every record of the file, in order; an absent file has none. A line that is not a JSON object
    is skipped: a log being appended to by a process that died mid-line must not make it unreadable."""
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records
