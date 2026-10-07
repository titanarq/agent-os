"""What an invocation leaves on disk besides its telemetry line: the class's `runs.tsv` row."""

from __future__ import annotations

import fcntl
import os
import pathlib
from datetime import UTC, datetime

from agent_os.lib import RUNS_TSV_HEADER, planner_run_row


def append_runs_row(
    runs_tsv: pathlib.Path, log_path: pathlib.Path, context: str, model: str
) -> None:
    """The class's own `runs.tsv` row, through the helper every role's row goes through."""
    runs_tsv.parent.mkdir(parents=True, exist_ok=True)
    row = planner_run_row(
        log_path.read_text(errors="replace"),
        ts=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        context=context,
        model=model,
    )
    with runs_tsv.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(RUNS_TSV_HEADER + "\n")
        handle.write(row + "\n")
