"""The owner's verdict on a puntal's answer: accept, reject or retry, keyed by the invocation.

`docs/AGENTOS_V2_PLAN.md` ("Recording conventions"): `.cache/puntal/feedback.jsonl`, one line per
verdict, joined to the telemetry on `invocation_id`. The versions of the invocation being judged are
copied from its telemetry record -- a verdict is about THAT model and THAT prompt, not about whatever
is installed when the owner gets round to clicking.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime

from agent_os.product.puntal.constants import PuntalRefused
from agent_os.product.records import append_json_line, read_json_lines

FEEDBACK_SCHEMA = 1
VERDICTS = ("accept", "reject", "retry")
FEEDBACK_FIELDS = (
    "schema",
    "invocation_id",
    "verdict",
    "note",
    "retried_as",
    "recorded_at",
    "action",
    "node",
    "session_id",
    "versions",
)


def record_feedback(
    *,
    invocation_id: str,
    verdict: str,
    note: str,
    retried_as: str | None,
    telemetry_file: pathlib.Path,
    feedback_file: pathlib.Path,
) -> dict:
    """Appends the verdict and returns the record. Refuses, before writing, a verdict that is not one
    of `VERDICTS` and an invocation the telemetry has never heard of: a verdict that joins to nothing
    is a typo in an id, and recording it would only hide that."""
    if verdict not in VERDICTS:
        raise PuntalRefused(f"a verdict is one of {', '.join(VERDICTS)}, not {verdict!r}")
    invocation = next(
        (r for r in read_json_lines(telemetry_file) if r.get("invocation_id") == invocation_id),
        None,
    )
    if invocation is None:
        raise PuntalRefused(
            f"no invocation {invocation_id!r} in {telemetry_file}: a verdict needs the invocation "
            "it is about"
        )
    record = {
        "schema": FEEDBACK_SCHEMA,
        "invocation_id": invocation_id,
        "verdict": verdict,
        "note": note,
        "retried_as": retried_as,
        "recorded_at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "action": invocation.get("action"),
        "node": invocation.get("node"),
        "session_id": invocation.get("session_id"),
        "versions": invocation.get("versions"),
    }
    append_json_line(feedback_file, record)
    return record
