"""What a role run leaves on disk beside its event stream: its log's terminal `result`, the exit
marker the driver writes when the backend returns, and the planner's `runs.tsv` line.

Pure functions over a log's text or a log's path. `agent_os.lib` re-exports every name here, which
is where the guard, the puntal and the host drivers import them from."""

from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime

RUNS_TSV_HEADER = "ts\tcontext\tmodel\tnum_turns\ttotal_cost_usd"

# A role run's exit marker (#429): `<stamp>.log.exited`, one ISO-8601 UTC timestamp, written by the
# driver the moment the backend process returns. The log itself is no clock for that moment: the
# detached half keeps appending to it after the backend's `result` -- the exit hook's `wake`, which
# runs a whole planner synchronously, and the worktree's removal -- so its mtime can be minutes
# later than the refusal it records, and later than the planner run it started.
ROLE_RUN_EXIT_MARKER_SUFFIX = ".exited"


def role_run_exit_marker(log_path: pathlib.Path | str) -> pathlib.Path:
    log_path = pathlib.Path(log_path)
    return log_path.with_name(log_path.name + ROLE_RUN_EXIT_MARKER_SUFFIX)


def write_role_run_exit_marker(
    log_path: pathlib.Path | str, *, now: datetime | None = None
) -> pathlib.Path:
    """Written once per run and never again: a second call for the same log is a driver bug, and
    it would move the observation's time, so it is refused rather than overwritten."""
    marker = role_run_exit_marker(log_path)
    with marker.open("x") as handle:
        handle.write((now or datetime.now(UTC)).isoformat() + "\n")
    return marker


def read_role_run_exit_marker(log_path: pathlib.Path | str) -> datetime | None:
    """When the run's backend exited, or None: no marker (the run is still going, it died before
    its backend returned, or it predates the marker), or one that does not read as an aware
    timestamp -- which dates nothing, and so observes nothing."""
    try:
        text = role_run_exit_marker(log_path).read_text().strip()
        exited_at = datetime.fromisoformat(text)
    except (OSError, ValueError):
        return None
    return exited_at if exited_at.tzinfo is not None else None


def last_result_event(log_text: str) -> dict | None:
    """The last `{"type":"result",...}` line of a `claude -p --output-format stream-json` log.
    The log also carries the driver's own plain-text lines (identity, model, context), so it is
    scanned line by line and anything that is not JSON is skipped rather than failing the parse."""
    result = None
    for line in log_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            result = event
    return result


def planner_run_row(log_text: str, *, ts: str, context: str, model: str) -> str:
    """One `.cache/planner/runs.tsv` line per planner run: what it was woken for and what it cost
    (agent_os/docs/adr/2026-09-14-the-planner-wakes-on-disk-events-and-an-idle-wake-is-rate-limited.md).
    A run whose log has no terminal `result` (killed, crashed, a stub backend) still gets its
    line, with empty cost fields -- a missing row would read as "the run never happened"."""
    result = last_result_event(log_text) or {}
    turns = result.get("num_turns")
    cost = result.get("total_cost_usd")
    flat = " ".join((context or "").split())[:120]
    return "\t".join(
        [
            ts,
            flat,
            model,
            "" if turns is None else str(turns),
            "" if cost is None else f"{float(cost):.4f}",
        ]
    )
