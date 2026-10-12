"""One judgment: the brief, one model turn with no tool, the validation. No retry: an answer that
does not validate means every pull request solo, which costs speed and never a wrong merge."""

from __future__ import annotations

import dataclasses
import os
import pathlib
from datetime import UTC, datetime

from agent_os.lib import write_role_run_exit_marker
from agent_os.product.integrator.judge.index import GroupIndex, build_brief
from agent_os.product.integrator.judge.options import INTEGRATOR_ROLE
from agent_os.product.integrator.judge.verdict import (
    JudgedGroup,
    every_one_solo,
    final_groups,
    parse_verdict,
)
from agent_os.product.puntal.constants import (
    EXIT_ANSWERED,
    EXIT_BACKEND_FAILED,
    EXIT_CEILING_CUT,
    EXIT_CONTRACT_VIOLATION,
    EXIT_INVALID_PLAN,
    EXIT_NOT_RUN,
    EXIT_TIMEOUT,
)
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.outcome import classify_turn, invocation_cost
from agent_os.product.puntal.turn import run_turn

OUTCOME_INVALID_OUTPUT = "invalid_output"
OUTCOME_EXIT_STATUS = {
    "ok": EXIT_ANSWERED,
    "error": EXIT_BACKEND_FAILED,
    "not_run": EXIT_NOT_RUN,
    "contract_violation": EXIT_CONTRACT_VIOLATION,
    "ceiling_cut": EXIT_CEILING_CUT,
    OUTCOME_INVALID_OUTPUT: EXIT_INVALID_PLAN,
    "timeout": EXIT_TIMEOUT,
}


@dataclasses.dataclass(frozen=True)
class Judgment:
    outcome: str
    detail: str
    groups: tuple[JudgedGroup, ...]
    model: str
    cost_usd: float | None
    log_path: pathlib.Path | None = None

    @property
    def exit_status(self) -> int:
        return OUTCOME_EXIT_STATUS[self.outcome]

    def as_json(self) -> dict:
        return {
            "outcome": self.outcome,
            "exit_status": self.exit_status,
            "detail": self.detail,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "groups": [group.as_json() for group in self.groups],
        }


def not_judged(index: GroupIndex, outcome: str, detail: str, model: str = "") -> Judgment:
    return Judgment(
        outcome, detail, every_one_solo(index.numbers, f"not judged: {detail}"), model, None
    )


def judge_group(index: GroupIndex, options: Options, clock: Clock) -> Judgment:
    started_at = datetime.now(UTC)
    options.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"-{started_at.microsecond:06d}-{os.getpid()}"
    log_path = options.run_dir / f"{stamp}.log"
    with log_path.open("x", encoding="utf-8") as log:
        log.write(
            f"ts:        {stamp}\nrole:      {INTEGRATOR_ROLE} (class {options.class_name})\n"
            f"model:     {options.model}\ngroup:     {' '.join(map(str, index.numbers))}\n"
        )
        turn = run_turn(
            kind="judge",
            options=options,
            clock=clock,
            ceilings=options.ceilings,
            contract=options.fast_contract,
            brief=build_brief(index),
            with_state_tool=False,
            log=log,
        )
    write_role_run_exit_marker(log_path)
    turn.outcome, turn.outcome_detail = classify_turn(turn.run, turn.observer)
    cost = invocation_cost([turn])
    if turn.outcome != "ok":
        detail = turn.outcome_detail
        return dataclasses.replace(
            not_judged(index, turn.outcome, detail, options.model),
            cost_usd=cost,
            log_path=log_path,
        )
    groups, problems = parse_verdict(turn.observer.final_text(), index.numbers)
    if groups is None:
        detail = "; ".join(problems)[:400]
        return dataclasses.replace(
            not_judged(index, OUTCOME_INVALID_OUTPUT, detail, options.model),
            cost_usd=cost,
            log_path=log_path,
        )
    return Judgment("ok", "", final_groups(groups), options.model, cost, log_path)
