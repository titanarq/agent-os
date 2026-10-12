"""One model turn with no tool, for the drafter or the reviewer: the text it answered, or why none."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from agent_os.lib import write_role_run_exit_marker
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.outcome import classify_turn, invocation_cost
from agent_os.product.puntal.turn import run_turn


@dataclass(frozen=True)
class TurnAnswer:
    text: str
    failure: str  # empty when the turn answered
    cost_usd: float | None


def answer_one_turn(
    *, role: str, subject: str, options: Options, brief: str, clock: Clock
) -> TurnAnswer:
    started_at = datetime.now(UTC)
    options.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"-{started_at.microsecond:06d}-{os.getpid()}"
    log_path = options.run_dir / f"{stamp}-{role}.log"
    with log_path.open("x", encoding="utf-8") as log:
        log.write(
            f"ts:        {stamp}\nrole:      {role} (class {options.class_name})\n"
            f"model:     {options.model}\nsubject:   {subject}\n"
        )
        turn = run_turn(
            kind=role,
            options=options,
            clock=clock,
            ceilings=options.ceilings,
            contract=options.fast_contract,
            brief=brief,
            with_state_tool=False,
            log=log,
        )
    write_role_run_exit_marker(log_path)
    turn.outcome, turn.outcome_detail = classify_turn(turn.run, turn.observer)
    cost = invocation_cost([turn])
    if turn.outcome != "ok":
        return TurnAnswer("", f"{role} {turn.outcome}: {turn.outcome_detail}", cost)
    return TurnAnswer(turn.observer.final_text(), "", cost)
