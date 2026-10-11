"""The document the host reads on stdout: one JSON object, always, whether the model answered or not."""

from __future__ import annotations

from agent_os.product.interpreter.constants import CONTRACT_SCHEMA, OUTCOME_EXIT_STATUS
from agent_os.product.interpreter.request import Request
from agent_os.product.interpreter.run import Outcome
from agent_os.product.puntal.telemetry.outcome import invocation_usage
from agent_os.product.puntal.telemetry.record import rounded_seconds


def success_envelope(request: Request, outcome: Outcome) -> dict:
    interpretation = outcome.interpretation
    trace = outcome.result.trace
    return {
        "schema": CONTRACT_SCHEMA,
        "invocation_id": request.invocation_id,
        "outcome": outcome.outcome,
        "exit_status": outcome.exit_status,
        "detail": outcome.detail,
        "message_position": request.message_position,
        "reply": interpretation.reply if interpretation else None,
        "needs_answer": interpretation.needs_answer if interpretation else False,
        "items": [item.as_json() for item in interpretation.items] if interpretation else [],
        "retries": outcome.retries,
        "cost_usd": outcome.cost_usd,
        "usage": invocation_usage(trace.turns),
        "latency_s": {"total": rounded_seconds(trace.answered_at_s)},
    }


def refusal_envelope(detail: str, request: Request | None = None) -> dict:
    """Nothing was run: the request or the config is wrong. The host shows its own "could not
    interpret it, it is noted" and keeps the owner's message."""
    return {
        "schema": CONTRACT_SCHEMA,
        "invocation_id": request.invocation_id if request else None,
        "outcome": "not_run",
        "exit_status": OUTCOME_EXIT_STATUS["not_run"],
        "detail": detail,
        "message_position": request.message_position if request else None,
        "reply": None,
        "needs_answer": False,
        "items": [],
        "retries": 0,
        "cost_usd": None,
        "usage": None,
        "latency_s": None,
    }
