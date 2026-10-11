"""The verdicts the owner gave in the chat, carried into the puntal's `feedback.jsonl`
(`docs/adr/2026-10-10-a-verdict-a-correction-and-an-open-question-go-through-the-chat.md`, point 6).

An approved `verdict` item, not withdrawn, becomes the same record `puntal_task.sh feedback` writes
(`versions`, `action` and `node` copied from the invocation's telemetry), plus the `key`
`chat-verdict.<session>.<item>` by which a second run finds it already written and adds nothing.
An invocation the telemetry has never heard of is a problem, as it is for that command.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from agent_os.product.puntal.telemetry.feedback import VERDICTS, record_feedback
from agent_os.product.records import read_json_lines
from agent_os.product.session_ingest.chat.model import Item
from agent_os.product.session_ingest.chat.verdict_keys import chat_verdict_key

TELEMETRY_FILE_NAME = "telemetry.jsonl"


@dataclass(frozen=True)
class VerdictStep:
    key: str
    item: Item
    invocation_id: str
    verdict: str
    note: str
    already_recorded: bool


def telemetry_file_beside(feedback_file: pathlib.Path) -> pathlib.Path:
    """The puntal keeps both files in one directory, as `puntal_task.sh feedback` assumes."""
    return feedback_file.with_name(TELEMETRY_FILE_NAME)


def verdict_step_for(
    session_id: str, item: Item, *, feedback_file: pathlib.Path
) -> VerdictStep | str:
    """The step, or the problem that keeps the item from being recorded."""
    if len(item.invocations) != 1:
        return (
            f"{item.id}: a verdict is about ONE invocation, this one names {len(item.invocations)}"
        )
    if item.verdict not in VERDICTS:
        return f"{item.id}: the verdict {item.verdict!r} is not one of {', '.join(VERDICTS)}"
    invocation_id = item.invocations[0]
    telemetry = read_json_lines(telemetry_file_beside(feedback_file))
    if not any(row.get("invocation_id") == invocation_id for row in telemetry):
        return (
            f"{item.id}: no invocation {invocation_id!r} in {telemetry_file_beside(feedback_file)}, "
            "its verdict cannot be recorded"
        )
    key = chat_verdict_key(session_id, item.id)
    recorded = any(row.get("key") == key for row in read_json_lines(feedback_file))
    return VerdictStep(key, item, invocation_id, item.verdict, item.note or "", recorded)


def record_verdict_step(step: VerdictStep, *, feedback_file: pathlib.Path) -> bool:
    """True when a line was appended; a step already recorded writes nothing."""
    if step.already_recorded:
        return False
    record_feedback(
        invocation_id=step.invocation_id,
        verdict=step.verdict,
        note=step.note,
        retried_as=None,
        telemetry_file=telemetry_file_beside(feedback_file),
        feedback_file=feedback_file,
        key=step.key,
    )
    return True
