"""One interpretation, end to end: the brief, one model turn with no tool, the validation, and at
most one retry when the answer was not a valid interpretation.

    brief -> turn (no tools) -> parse -> Interpretation
                  |               |
                  | not ok        | rejected -> one retry turn with the reasons
                  v               v
               outcome        invalid_output
"""

from __future__ import annotations

import dataclasses
import os
from datetime import UTC, datetime

from agent_os.lib import write_role_run_exit_marker
from agent_os.product.config import InterpreterConfig
from agent_os.product.interpreter.brief import build_brief
from agent_os.product.interpreter.constants import (
    INTERPRETER_ROLE,
    MAX_RETRIES,
    OUTCOME_EXIT_STATUS,
    OUTCOME_INVALID_OUTPUT,
)
from agent_os.product.interpreter.interpretation import Interpretation, parse_interpretation
from agent_os.product.interpreter.request import Request
from agent_os.product.puntal.constants import PATH_FAST
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.options import Request as TelemetryRequest
from agent_os.product.puntal.results import InvocationResult
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.outcome import classify_turn, invocation_cost
from agent_os.product.puntal.telemetry.record import InvocationTrace
from agent_os.product.puntal.turn import remaining_ceilings, run_turn

ATTEMPT_TEXT_CHARS = 2000


@dataclasses.dataclass
class Outcome:
    outcome: str
    detail: str
    interpretation: Interpretation | None
    retries: int
    cost_usd: float | None
    result: InvocationResult

    @property
    def exit_status(self) -> int:
        return OUTCOME_EXIT_STATUS[self.outcome]


def interpret(
    request: Request, options: Options, settings: InterpreterConfig, clock: Clock
) -> Outcome:
    started_at = datetime.now(UTC)
    options.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"-{started_at.microsecond:06d}-{os.getpid()}"
    log_path = options.run_dir / f"{stamp}.log"
    turns, attempts = [], []
    outcome, detail, interpretation, rejection = "ok", "", None, None
    ceilings = options.ceilings
    with log_path.open("x", encoding="utf-8") as log:
        log.write(
            f"ts:        {stamp}\nrole:      {INTERPRETER_ROLE} (class {options.class_name})\n"
            f"model:     {options.model}\nsession:   {request.session_id or '(none)'}\n"
            f"invocation: {request.invocation_id}\n"
        )
        for attempt in range(MAX_RETRIES + 1):
            brief = build_brief(
                request, max_thread_messages=settings.max_thread_messages, rejection=rejection
            )
            turn = run_turn(
                kind="interpret" if attempt == 0 else "retry",
                options=options,
                clock=clock,
                ceilings=ceilings,
                contract=options.fast_contract,
                brief=brief,
                with_state_tool=False,
                log=log,
            )
            turn.outcome, turn.outcome_detail = classify_turn(turn.run, turn.observer)
            turns.append(turn)
            if turn.outcome != "ok":
                outcome, detail = turn.outcome, turn.outcome_detail
                break
            text = turn.observer.final_text()
            interpretation, rejection = parse_interpretation(text, request)
            if interpretation is not None:
                break
            attempts.append(
                {
                    "turn": attempt + 1,
                    "stage": "validation",
                    "errors": rejection,
                    "text": text[:ATTEMPT_TEXT_CHARS],
                }
            )
            outcome, detail = OUTCOME_INVALID_OUTPUT, "; ".join(rejection)[:400]
            if attempt < MAX_RETRIES:
                ceilings = remaining_ceilings(options.ceilings, turns)
                if ceilings is None:
                    outcome, detail = "ceiling_cut", "earlier turns spent the ceilings"
                    break
        if interpretation is not None:
            outcome, detail = "ok", ""
    write_role_run_exit_marker(log_path)
    trace = InvocationTrace(
        started_at=started_at,
        turns=turns,
        path=PATH_FAST,
        slow_path_reason=None,
        outcome=outcome,
        outcome_detail=detail,
        response=interpretation.reply if interpretation else "",
        gap_note=None,
        declared_reads={"declared": [], "ran": 0, "failed": 0, "problems": []},
        plan={
            "operations": None,
            "applied": False,
            "retries": max(len(turns) - 1, 0),
            "attempts": attempts,
            "bindings": {},
        },
        executor={"ran": False, "ok": None, "crashed": None, "errors": []},
        pre_helper_s=None,
        executor_s=None,
        answered_at_s=clock.now(),
        spawned_at_s=None,
    )
    result = InvocationResult(
        trace=trace,
        log_path=log_path,
        answer=trace.response,
        status=OUTCOME_EXIT_STATUS[outcome],
        plan=None,
        bindings={},
        applied=False,
    )
    return Outcome(
        outcome, detail, interpretation, trace.plan["retries"], invocation_cost(turns), result
    )


def telemetry_request(request: Request) -> TelemetryRequest:
    """The puntal's request shape, so the interpretation lands in the telemetry a refiner already
    reads: the action is `interpret_feedback` and the node is the case, when there is one."""
    case = request.case
    return TelemetryRequest(
        action="interpret_feedback",
        node_id=case.id if case else "(no case)",
        node_slice=(f"{case.title}\n{case.description}" if case else ""),
        payload=request.message.text,
        relevant_state="",
        session_id=request.session_id,
        invocation_id=request.invocation_id,
        labels={**request.labels, "role": INTERPRETER_ROLE},
    )
