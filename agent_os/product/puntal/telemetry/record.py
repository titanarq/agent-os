"""The telemetry record: one JSON object per invocation, the contract the refiner reads.

That file is the telemetry the refiner will consume to decide which use cases deserve hardening into
code, so its shape is a contract: `TELEMETRY_SCHEMA` is bumped on any incompatible change, and
`docs/AGENT_OS.md` §4.7 documents each field. Latencies are seconds from the moment
`puntal_task.sh` was entered, which is the moment the click reaches the driver.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime

from agent_os.product.puntal.constants import AGENT_OS_DIR, PERSISTENCE_TOOL
from agent_os.product.puntal.options import Options, Request
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.stream.turn_run import TurnRun
from agent_os.product.puntal.telemetry.outcome import (
    ceilings_exceeded,
    invocation_cost,
    invocation_usage,
    turn_cost,
    turn_usage,
)
from agent_os.product.records import record_versions
from agent_os.product.records.versions import prompt_digest

TELEMETRY_SCHEMA = 2
# The top-level keys of one telemetry record, in the order they are written. Documented field by
# field in `docs/AGENT_OS.md` §4.7; a test holds this tuple, the record `build_record` returns and
# that table to the same list.
TELEMETRY_FIELDS = (
    "schema",
    "invocation_id",
    "started_at",
    "action",
    "node",
    "node_digest",
    "session_id",
    "backend_session_id",
    "labels",
    "class",
    "backend",
    "model",
    "effort",
    "path",
    "slow_path_reason",
    "versions",
    "outcome",
    "outcome_detail",
    "exit_code",
    "latency_s",
    "usage",
    "cost_usd",
    "turns",
    "declared_reads",
    "plan",
    "executor",
    "tool_calls",
    "tool_violations",
    "init",
    "permission_denials",
    "ceilings",
    "launch",
    "scratch_extra_entries",
    "response",
    "gap_note",
    "stderr_tail",
)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


@dataclasses.dataclass
class InvocationTrace:
    """Everything an invocation learned, in the order the record is made of it."""

    started_at: datetime
    turns: list[TurnRun]
    path: str
    slow_path_reason: str | None
    outcome: str
    outcome_detail: str
    response: str
    gap_note: str | None
    declared_reads: dict
    plan: dict
    executor: dict
    pre_helper_s: float | None
    executor_s: float | None
    answered_at_s: float
    spawned_at_s: float | None


def _turn_summary(number: int, turn: TurnRun) -> dict:
    result = turn.observer.result or {}
    return {
        "n": number,
        "kind": turn.kind,
        "outcome": turn.outcome,
        "outcome_detail": turn.outcome_detail,
        "started_at_s": _rounded(turn.started_s),
        "ended_at_s": _rounded(turn.ended_s),
        "total_tokens": turn_usage(turn.observer)["total_tokens"],
        "cost_usd": turn_cost(turn.observer),
        "num_turns": result.get("num_turns"),
        "prompt_digest": prompt_digest(turn.contract_text),
        "backend_session_id": result.get("session_id")
        or (turn.observer.init or {}).get("session_id"),
    }


def _tool_call_rows(turns: list[TurnRun]) -> list[dict]:
    return [
        {
            "name": call.name,
            "command": call.input.get("command") if call.name == PERSISTENCE_TOOL else None,
            "at_s": _rounded(call.first_seen_s),
            "violation": call.violation,
            "is_error": call.is_error,
            "result_chars": call.result_chars,
        }
        for turn in turns
        for call in turn.observer.tool_calls.values()
    ]


def build_record(
    *, request: Request, options: Options, trace: InvocationTrace, clock: Clock
) -> dict:
    turns = trace.turns
    first, last = turns[0], turns[-1]
    first_observer, last_result = first.observer, last.observer.result or {}
    first_init = first_observer.init or {}
    usage = invocation_usage(turns)
    cost = invocation_cost(turns)
    cli_version = next(
        (
            version
            for turn in turns
            if (version := (turn.observer.init or {}).get("claude_code_version"))
        ),
        None,
    )
    violations = [v for turn in turns for v in turn.observer.violations()]
    return {
        "schema": TELEMETRY_SCHEMA,
        "invocation_id": request.invocation_id,
        "started_at": trace.started_at.isoformat(timespec="milliseconds"),
        "action": request.action,
        "node": request.node_id,
        "node_digest": "sha256:" + hashlib.sha256(request.node_slice.encode()).hexdigest()[:16],
        "session_id": request.session_id,
        "backend_session_id": last_result.get("session_id")
        or (last.observer.init or {}).get("session_id"),
        "labels": request.labels,
        "class": options.class_name,
        "backend": options.backend,
        "model": options.model,
        "effort": options.effort or None,
        "path": trace.path,
        "slow_path_reason": trace.slow_path_reason,
        "versions": record_versions(
            model=options.model,
            cli_version=cli_version,
            prompt_text=last.contract_text,
            agent_os_dir=AGENT_OS_DIR,
        ),
        "outcome": trace.outcome,
        "outcome_detail": trace.outcome_detail,
        "exit_code": last.run.exit_code,
        "latency_s": {
            "total": _rounded(trace.answered_at_s),
            "python_startup": _rounded(clock.overhead_before_python_s),
            "pre_helper": _rounded(trace.pre_helper_s),
            "launch_overhead": _rounded(trace.spawned_at_s),
            "first_event": _rounded(first_observer.first_event_s),
            "first_message": _rounded(first_observer.first_message_s),
            "first_tool_call": _rounded(first_observer.first_tool_call_s),
            "first_text_delta": _rounded(first_observer.first_text_delta_s),
            "final_answer_first_delta": _rounded(last.observer.final_answer_first_delta_s()),
            "executor": _rounded(trace.executor_s),
            "backend_reported": {
                "duration_ms": last_result.get("duration_ms"),
                "duration_api_ms": last_result.get("duration_api_ms"),
                "ttft_ms": last_result.get("ttft_ms"),
            },
        },
        "usage": usage,
        "cost_usd": cost,
        "turns": [_turn_summary(number, turn) for number, turn in enumerate(turns, start=1)],
        "declared_reads": trace.declared_reads,
        "plan": trace.plan,
        "executor": trace.executor,
        "tool_calls": _tool_call_rows(turns),
        "tool_violations": violations,
        "init": {
            "tools": first_init.get("tools"),
            "mcp_servers": first_init.get("mcp_servers"),
            "permission_mode": first_init.get("permissionMode"),
            "claude_code_version": cli_version,
        },
        "permission_denials": sum(
            len((turn.observer.result or {}).get("permission_denials") or []) for turn in turns
        ),
        "ceilings": {
            **dataclasses.asdict(first_observer.ceilings),
            "exceeded": ceilings_exceeded(options.ceilings, turns, usage, cost),
        },
        "launch": {
            "flags": first.flags,
            "persistence_command": options.persistence_command,
            "executor_command": options.executor_command or None,
        },
        "scratch_extra_entries": sorted({e for turn in turns for e in turn.scratch_extra}),
        "response": trace.response,
        "gap_note": trace.gap_note,
        "stderr_tail": (
            [line for turn in turns for line in turn.observer.non_event_lines]
            if trace.outcome != "ok"
            else []
        ),
    }
